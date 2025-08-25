import ast
import os
import subprocess
import shutil
import logging
import sys

# Works across languages via lizard
SUPPORTED_LANGUAGES = {"any"}
import json
import tempfile
import statistics
from typing import List, Dict, Any
from .utils import get_python_files, parse_file
from .stats_utils import BenchmarkResult, calculate_confidence_interval, adjust_score_for_size, get_codebase_size_bucket

def assess_performance(codebase_path: str) -> BenchmarkResult:
    """
    Hybrid static + dynamic performance assessment.

    Combines anti-pattern detection with runtime profiling.

    Args:
        codebase_path: Path to the codebase to analyze.

    Returns:
        BenchmarkResult containing score, details, raw_metrics, and confidence_interval.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return BenchmarkResult(0.0, ["No Python files found."])

    details = []
    raw_metrics = {}
    
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
    score_samples = [static_score]
    if "execution_times" in raw_metrics:
        score_samples.extend(raw_metrics["execution_times"])
    
    confidence_interval = calculate_confidence_interval(score_samples)
    
    return BenchmarkResult(
        score=adjusted_score,
        details=details,
        raw_metrics=raw_metrics,
        confidence_interval=confidence_interval
    )


def _assess_static_performance(codebase_path: str, python_files: List[str]) -> tuple[float, List[str]]:
    """Language-agnostic static performance heuristics via Lizard + optional Python anti-pattern checks."""
    details: List[str] = []
    penalties = 0.0

    # ---------------------------------------------------------------
    # 1. Universal metrics using `lizard` (supports many languages)
    # ---------------------------------------------------------------
    lizard_executable = shutil.which("lizard")
    if not lizard_executable:
        details.append("[!] 'lizard' not installed; install via 'pip install lizard' for cross-language complexity analysis.")
        avg_cc = None
        total_funcs = 0
    else:
        if not os.path.exists(codebase_path):
            details.append("[!] lizard skipped: codebase path does not exist.")
            avg_cc = None
            total_funcs = 0
        else:
            try:
                proc = subprocess.run([lizard_executable, "-j", codebase_path], capture_output=True, text=True, check=False)
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    # Single-pass aggregation to avoid O(n) allocations for large codebases
                    total_funcs = 0
                    sum_cc = 0
                    high_cc_count = 0
                    for file_rec in data.get("files", []):
                        for func in file_rec.get("functions", []):
                            total_funcs += 1
                            cc = func.get("cyclomatic_complexity", 0)
                            sum_cc += cc
                            if cc > 20:
                                high_cc_count += 1
                    avg_cc = (sum_cc / total_funcs) if total_funcs else None

                    if avg_cc is not None:
                        details.append(f"Average cyclomatic complexity (all languages): {avg_cc:.1f}")
                        # Penalty: 1 point for every 2 points above CC=10
                        if avg_cc > 10:
                            penalties += (avg_cc - 10) / 2

                        # High-complexity function penalty
                        if high_cc_count:
                            ratio = high_cc_count / total_funcs
                            penalties += ratio * 3  # up to 3-point penalty
                            details.append(f"{high_cc_count} / {total_funcs} functions have CC > 20")
                else:
                    details.append("[!] lizard failed to analyze the codebase.")
                    avg_cc = None
                    total_funcs = 0
            except Exception as e:
                details.append(f"[!] lizard execution error: {e}")
                avg_cc = None
                total_funcs = 0

    # ---------------------------------------------------------------
    # 2. Python-specific anti-pattern scan (kept from previous logic)
    # ---------------------------------------------------------------
    class _AntiPatternVisitor(ast.NodeVisitor):
        def __init__(self, file_path: str):
            self.file_path = file_path
            self.details: List[str] = []
            self.anti_patterns_found: float = 0.0
            self.loop_stack: List[ast.AST] = []

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'insert' and len(node.args) == 2:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and first_arg.value == 0:
                    self.details.append(f"Inefficient 'list.insert(0, …)' at {self.file_path}:{node.lineno}")
                    self.anti_patterns_found += 1.0
            self.generic_visit(node)

        def visit_For(self, node: ast.For) -> None:
            if self.loop_stack:
                outer = self.loop_stack[-1]
                self.details.append(f"Nested loops (O(n²) risk) at {self.file_path}:{outer.lineno}")
                self.anti_patterns_found += 0.3
            self.loop_stack.append(node)
            self.generic_visit(node)
            self.loop_stack.pop()

        def visit_While(self, node: ast.While) -> None:
            self.loop_stack.append(node)
            self.generic_visit(node)
            self.loop_stack.pop()

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            if isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name) and self.loop_stack:
                loop_node = self.loop_stack[-1]
                self.details.append(f"String concatenation in loop at {self.file_path}:{loop_node.lineno}")
                self.anti_patterns_found += 0.5
            self.generic_visit(node)

    anti_patterns_found = 0.0
    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue

        visitor = _AntiPatternVisitor(file_path)
        visitor.visit(tree)
        if visitor.anti_patterns_found:
            details.extend(visitor.details)
            anti_patterns_found += visitor.anti_patterns_found

    if anti_patterns_found:
        details.insert(0, f"Python anti-patterns found: {anti_patterns_found}")
        penalties += anti_patterns_found

    # ---------------------------------------------------------------
    # Final score (0-10 after penalties)
    # ---------------------------------------------------------------
    performance_score = 10.0 - penalties
    performance_score = max(0.0, min(10.0, performance_score))
    return performance_score, details


def _assess_dynamic_performance(profile_script: str) -> tuple[float, List[str], Dict[str, Any]]:
    """Dynamic runtime profiling with multiple samples."""
    details = []
    metrics = {}
    
    # Validate profile script path explicitly
    if not profile_script or not os.path.isfile(profile_script):
        details.append("Invalid profile script path provided.")
        logging.error("Invalid profile script path provided to _assess_dynamic_performance: %s", profile_script)
        return 0.0, details, metrics

    # Run multiple samples for statistical confidence
    execution_times = []
    memory_peaks = []
    
    for run_num in range(3):  # 3 samples
        # === TIME PROFILING ===
        fd = None
        time_report_path = None
        try:
            fd, time_report_path = tempfile.mkstemp(suffix=".json")
            # Close the fd immediately to avoid holding an open descriptor while subprocess writes to it
            if fd is not None:
                os.close(fd)
                fd = None
            try:
                os.chmod(time_report_path, 0o600)
            except Exception:
                # Best-effort to set restrictive permissions; if it fails, continue but log
                logging.debug("Could not set restrictive permissions on temp file %s", time_report_path)

            cmd = [sys.executable, "-m", "pyinstrument", "--json", "-o", time_report_path, profile_script]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if proc.returncode == 0 and os.path.exists(time_report_path):
                with open(time_report_path) as f:
                    time_data = json.load(f)
                execution_time = time_data.get("duration", 0) * 1000  # ms
                execution_times.append(execution_time)
            else:
                logging.error("pyinstrument failed (returncode=%s) stdout=%s stderr=%s", proc.returncode, proc.stdout, proc.stderr)
        except Exception:
            logging.exception("pyinstrument profiling failed for %s", profile_script)
        finally:
            if time_report_path and os.path.exists(time_report_path):
                try:
                    os.remove(time_report_path)
                except Exception:
                    logging.exception("Failed to remove temporary profiling file %s", time_report_path)
        
        # === MEMORY PROFILING ===
        try:
            cmd = [sys.executable, "-m", "memory_profiler", profile_script]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if proc.returncode == 0:
                # Parse memory_profiler output for peak usage
                lines = proc.stdout.split('\n')
                for line in lines:
                    if 'MiB' in line and 'maximum of' in line:
                        # Extract peak memory usage
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'maximum' and i+2 < len(parts):
                                try:
                                    peak_mb = float(parts[i+2])
                                    memory_peaks.append(peak_mb)
                                    break
                                except ValueError:
                                    pass
            else:
                logging.error("memory_profiler failed (returncode=%s) stdout=%s stderr=%s", proc.returncode, proc.stdout, proc.stderr)
        except Exception:
            logging.exception("memory_profiler profiling failed for %s", profile_script)
    
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