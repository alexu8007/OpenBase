import ast
import os
import subprocess
import shutil
import logging
import json
import tempfile
import statistics
from typing import List, Dict, Any, Optional, Tuple

from .utils import get_python_files, parse_file
from .stats_utils import BenchmarkResult, calculate_confidence_interval, adjust_score_for_size, get_codebase_size_bucket

logger = logging.getLogger(__name__)

# Works across languages via lizard
SUPPORTED_LANGUAGES = {"any"}


def assess_performance(codebase_path: str) -> BenchmarkResult:
    """
    Hybrid static + dynamic performance assessment.
    Combines anti-pattern detection with runtime profiling.

    Args:
        codebase_path: Path to the root of the codebase to analyze.

    Returns:
        A BenchmarkResult containing score, details, raw metrics and confidence interval.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return BenchmarkResult(0.0, ["No Python files found."])

    details: List[str] = []
    raw_metrics: Dict[str, Any] = {}

    # === STATIC ANALYSIS ===
    static_score, static_details = _assess_static_performance(codebase_path, python_files)
    details.extend(static_details)
    raw_metrics["static_score"] = static_score

    # === DYNAMIC ANALYSIS ===
    profile_script = os.getenv("BENCH_PROFILE_SCRIPT")
    if profile_script and os.path.exists(profile_script):
        dynamic_score, dynamic_details, runtime_metrics = _assess_dynamic_performance(profile_script)
        details.extend(dynamic_details)
        raw_metrics.update(runtime_metrics)

        # Combine static + dynamic (weighted)
        final_score = (0.4 * static_score) + (0.6 * dynamic_score)
    else:
        final_score = static_score
        details.append("No profile script provided (set BENCH_PROFILE_SCRIPT). Using static analysis only.")

    # === BIAS ADJUSTMENT ===
    size_bucket = get_codebase_size_bucket(codebase_path)
    adjusted_score = adjust_score_for_size(final_score, size_bucket, "performance")
    raw_metrics["size_bucket"] = size_bucket
    raw_metrics["unadjusted_score"] = final_score

    # === CONFIDENCE INTERVAL ===
    # Use variance from multiple metrics as proxy for uncertainty
    score_samples: List[float] = [static_score]
    if "execution_times" in raw_metrics:
        score_samples.extend(raw_metrics["execution_times"])

    confidence_interval = calculate_confidence_interval(score_samples)

    return BenchmarkResult(
        score=adjusted_score,
        details=details,
        raw_metrics=raw_metrics,
        confidence_interval=confidence_interval
    )


def _run_lizard_analysis(codebase_path: str) -> Tuple[Optional[float], int, List[str], float]:
    """
    Run lizard static analysis (cross-language) on the codebase.

    Returns:
        avg_cc: Average cyclomatic complexity or None if unavailable.
        total_funcs: Number of functions found.
        details: List of detail messages produced by this analysis.
        penalties: Penalty score derived from lizard results.
    """
    details: List[str] = []
    penalties = 0.0
    avg_cc: Optional[float] = None
    total_funcs = 0

    lizard_executable = shutil.which("lizard")
    if not lizard_executable:
        details.append("[!] 'lizard' not installed; install via 'pip install lizard' for cross-language complexity analysis.")
        return avg_cc, total_funcs, details, penalties

    if not os.path.isdir(codebase_path):
        details.append("[!] Provided codebase_path is not a directory; skipping lizard analysis.")
        return avg_cc, total_funcs, details, penalties

    if not os.path.isfile(lizard_executable) or not os.access(lizard_executable, os.X_OK):
        details.append("[!] 'lizard' executable not runnable; skipping lizard analysis.")
        return avg_cc, total_funcs, details, penalties

    try:
        proc = subprocess.run([lizard_executable, "-j", codebase_path], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            details.append("[!] lizard failed to analyze the codebase.")
            logger.warning("lizard returned non-zero exit code: %s, stderr: %s", proc.returncode, proc.stderr)
            return avg_cc, total_funcs, details, penalties

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            details.append("[!] lizard produced invalid JSON output.")
            logger.exception("Failed to parse lizard JSON output")
            return avg_cc, total_funcs, details, penalties

        # Collect cyclomatic complexity values without building large intermediate lists
        cc_values: List[float] = []
        for file_record in data.get("files", []):
            funcs = file_record.get("functions", [])
            total_funcs += len(funcs)
            for f in funcs:
                cc_values.append(f.get("cyclomatic_complexity", 0))

        if total_funcs:
            avg_cc = sum(cc_values) / total_funcs
        else:
            avg_cc = None

        if avg_cc is not None:
            details.append(f"Average cyclomatic complexity (all languages): {avg_cc:.1f}")
            # Penalty: 1 point for every 2 points above CC=10
            if avg_cc > 10:
                penalties += (avg_cc - 10) / 2

            # High-complexity function penalty
            high_cc_funcs_count = sum(1 for v in cc_values if v > 20)
            if high_cc_funcs_count:
                ratio = high_cc_funcs_count / total_funcs
                penalties += ratio * 3  # up to 3-point penalty
                details.append(f"{high_cc_funcs_count} / {total_funcs} functions have CC > 20")

    except Exception as e:
        logger.exception("lizard execution error")
        details.append(f"[!] lizard execution error: {e}")

    return avg_cc, total_funcs, details, penalties


class _AntiPatternVisitor(ast.NodeVisitor):
    """
    AST visitor that detects Python-specific performance anti-patterns in a single pass.

    Collected issues:
      - list.insert(0, ...) uses
      - string concatenation inside loops (AugAssign with Add)
      - nested loops (for/while inside for)
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.penalty = 0.0
        self.details: List[str] = []
        self._loop_depth = 0

    def visit_Call(self, node: ast.Call) -> None:
        # Detect list.insert(0, ...) pattern
        try:
            if isinstance(node.func, ast.Attribute) and node.func.attr == "insert" and len(node.args) == 2:
                first_arg = node.args[0]
                if hasattr(first_arg, "value") and first_arg.value == 0:
                    self.details.append(f"Inefficient 'list.insert(0, …)' at {self.file_path}:{getattr(node, 'lineno', '?')}")
                    self.penalty += 1.0
        except Exception:
            # Defensive: don't fail entire visitor on unusual AST shapes
            logger.debug("Error while inspecting Call node in %s", self.file_path, exc_info=True)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        if self._loop_depth > 0:
            # Found a nested loop
            self.details.append(f"Nested loops (O(n²) risk) at {self.file_path}:{getattr(node, 'lineno', '?')}")
            self.penalty += 0.3
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_While(self, node: ast.While) -> None:
        # While inside another loop counts as nested loop
        if self._loop_depth > 0:
            self.details.append(f"Nested loops (O(n²) risk) at {self.file_path}:{getattr(node, 'lineno', '?')}")
            self.penalty += 0.3
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # Detect string concatenation in loop contexts (x += "..." inside a loop)
        if self._loop_depth > 0:
            if isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name):
                self.details.append(f"String concatenation in loop at {self.file_path}:{getattr(node, 'lineno', '?')}")
                self.penalty += 0.5
        self.generic_visit(node)


def _scan_python_antipatterns(python_files: List[str]) -> Tuple[float, List[str]]:
    """
    Scan given Python files for common performance anti-patterns in a single-pass per-file.

    Returns:
        A tuple of (total_penalty, details_list).
    """
    total_penalty = 0.0
    details: List[str] = []

    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue
        visitor = _AntiPatternVisitor(file_path)
        try:
            visitor.visit(tree)
            if visitor.details:
                details.extend(visitor.details)
                total_penalty += visitor.penalty
        except Exception:
            logger.exception("Error scanning file for anti-patterns: %s", file_path)

    return total_penalty, details


def _assess_static_performance(codebase_path: str, python_files: List[str]) -> Tuple[float, List[str]]:
    """Language-agnostic static performance heuristics via Lizard + optional Python anti-pattern checks."""
    details: List[str] = []
    penalties = 0.0

    # ---------------------------------------------------------------
    # 1. Universal metrics using `lizard` (supports many languages)
    # ---------------------------------------------------------------
    avg_cc, total_funcs, lizard_details, lizard_penalties = _run_lizard_analysis(codebase_path)
    details.extend(lizard_details)
    penalties += lizard_penalties

    # ---------------------------------------------------------------
    # 2. Python-specific anti-pattern scan (single-pass per file)
    # ---------------------------------------------------------------
    anti_patterns_found, anti_pattern_details = _scan_python_antipatterns(python_files)
    if anti_patterns_found:
        details.insert(0, f"Python anti-patterns found: {anti_patterns_found}")
        penalties += anti_patterns_found
    details.extend(anti_pattern_details)

    # ---------------------------------------------------------------
    # Final score (0-10 after penalties)
    # ---------------------------------------------------------------
    performance_score = 10.0 - penalties
    performance_score = max(0.0, min(10.0, performance_score))
    return performance_score, details


def _assess_dynamic_performance(profile_script: str) -> Tuple[float, List[str], Dict[str, Any]]:
    """Dynamic runtime profiling with multiple samples.

    Args:
        profile_script: Path to a Python script to run and profile.

    Returns:
        (dynamic_score, details, metrics)
    """
    details: List[str] = []
    metrics: Dict[str, Any] = {}

    # Validate profile_script before running any subprocesses
    if not profile_script or not os.path.isfile(profile_script):
        raise ValueError("profile_script must be an existing file path")

    # Normalize path to avoid surprises
    profile_script = os.path.abspath(profile_script)

    # Run multiple samples for statistical confidence
    execution_times: List[float] = []
    memory_peaks: List[float] = []

    for run_num in range(3):  # 3 samples
        # === TIME PROFILING ===
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            time_report_path = tmp.name

        try:
            cmd = ["pyinstrument", "--json", "-o", time_report_path, profile_script]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if proc.returncode == 0 and os.path.exists(time_report_path):
                try:
                    with open(time_report_path) as f:
                        time_data = json.load(f)
                    execution_time = time_data.get("duration", 0) * 1000  # ms
                    execution_times.append(execution_time)
                except Exception:
                    logger.exception("Failed to read or parse pyinstrument output")
                    details.append("Failed to parse profiling output for one run")
            else:
                logger.warning("pyinstrument failed for run %s: returncode=%s, stderr=%s", run_num, getattr(proc, "returncode", None), getattr(proc, "stderr", ""))
                details.append("pyinstrument did not produce a valid report for one run")
        except Exception:
            logger.exception("Error while running pyinstrument")
            details.append("Error while running time profiler for one run")
        finally:
            try:
                if os.path.exists(time_report_path):
                    os.remove(time_report_path)
            except Exception:
                logger.exception("Failed to remove temporary profiling report: %s", time_report_path)

        # === MEMORY PROFILING ===
        try:
            cmd = ["python", "-m", "memory_profiler", profile_script]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if proc.returncode == 0:
                # Parse memory_profiler output for peak usage
                lines = proc.stdout.splitlines()
                for line in lines:
                    if 'MiB' in line and 'maximum of' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'maximum' and i + 2 < len(parts):
                                try:
                                    peak_mb = float(parts[i + 2])
                                    memory_peaks.append(peak_mb)
                                    break
                                except ValueError:
                                    continue
            else:
                logger.warning("memory_profiler failed for run %s: returncode=%s, stderr=%s", run_num, getattr(proc, "returncode", None), getattr(proc, "stderr", ""))
                details.append("memory_profiler did not produce usable output for one run")
        except Exception:
            logger.exception("Error while running memory_profiler")
            details.append("Error while running memory profiler for one run")

    # === SCORING ===
    if execution_times:
        avg_time = statistics.mean(execution_times)
        time_std = statistics.stdev(execution_times) if len(execution_times) > 1 else 0

        details.append(f"Avg execution time: {avg_time:.1f}ms (±{time_std:.1f}ms)")

        # Time-based scoring
        if avg_time < 100:
            time_score = 10.0
        elif avg_time < 500:
            time_score = 8.0
        elif avg_time < 1000:
            time_score = 6.0
        elif avg_time < 2000:
            time_score = 4.0
        else:
            time_score = 2.0

        metrics["execution_times"] = execution_times
        metrics["avg_execution_time_ms"] = avg_time
    else:
        time_score = 0.0
        details.append("Could not measure execution time")

    if memory_peaks:
        avg_memory = statistics.mean(memory_peaks)
        details.append(f"Peak memory usage: {avg_memory:.1f}MB")

        # Memory-based scoring (penalize high usage)
        if avg_memory < 50:
            memory_score = 10.0
        elif avg_memory < 200:
            memory_score = 8.0
        elif avg_memory < 500:
            memory_score = 6.0
        else:
            memory_score = 4.0

        metrics["memory_peaks_mb"] = memory_peaks
        metrics["avg_memory_mb"] = avg_memory
    else:
        memory_score = 8.0  # neutral if unmeasurable
        details.append("Could not measure memory usage")

    # Combined dynamic score
    dynamic_score = (time_score + memory_score) / 2.0

    return dynamic_score, details, metrics