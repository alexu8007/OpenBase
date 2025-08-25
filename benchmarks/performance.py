import ast
import os
import subprocess
import shutil
import logging
import json
import tempfile
import statistics
import sys
import unittest
from unittest import mock
from typing import List, Dict, Any, Tuple, Optional
from .utils import get_python_files, parse_file
from .stats_utils import BenchmarkResult, calculate_confidence_interval, adjust_score_for_size, get_codebase_size_bucket

logger = logging.getLogger(__name__)


def assess_performance(codebase_path: str) -> BenchmarkResult:
    """
    Hybrid static + dynamic performance assessment.
    Combines anti-pattern detection with runtime profiling.

    Public API signature preserved.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return BenchmarkResult(0.0, ["No Python files found."])

    details = []
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


def _run_lizard_analysis(codebase_path: str) -> Tuple[Optional[float], int, List[str]]:
    """
    Run lizard to extract average cyclomatic complexity and related details.
    Returns (avg_cc, total_funcs, details_list).
    """
    details: List[str] = []
    lizard_executable = shutil.which("lizard")
    if not lizard_executable:
        details.append("[!] 'lizard' not installed; install via 'pip install lizard' for cross-language complexity analysis.")
        return None, 0, details

    if not os.path.isdir(codebase_path):
        details.append(f"[!] codebase_path '{codebase_path}' is not a directory or does not exist.")
        logger.warning("Invalid codebase_path for lizard: %s", codebase_path)
        return None, 0, details

    try:
        proc = subprocess.run([lizard_executable, "-j", codebase_path], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            logger.warning("lizard returned non-zero exit code: %s", proc.returncode)
            details.append("[!] lizard failed to analyze the codebase.")
            return None, 0, details

        data = json.loads(proc.stdout)
        func_records = [f for file in data.get("files", []) for f in file.get("functions", [])]
        total_funcs = len(func_records)
        cc_values = [f.get("cyclomatic_complexity", 0) for f in func_records]
        avg_cc = (sum(cc_values) / total_funcs) if total_funcs else None

        if avg_cc is not None:
            details.append(f"Average cyclomatic complexity (all languages): {avg_cc:.1f}")
            if avg_cc > 10:
                # Penalty computation stays in caller
                pass

            high_cc_funcs = [v for v in cc_values if v > 20]
            if high_cc_funcs:
                details.append(f"{len(high_cc_funcs)} / {total_funcs} functions have CC > 20")
        return avg_cc, total_funcs, details
    except Exception as e:
        logger.exception("Error running lizard: %s", e)
        details.append(f"[!] lizard execution error: {e}")
        return None, 0, details


def _scan_ast_for_antipatterns(tree: ast.AST, file_path: str) -> Tuple[float, List[str]]:
    """
    Scan the AST once to detect common Python anti-patterns:
    - list.insert(0, ...)
    - string concatenation in loops (AugAssign with Add)
    - nested loops (For inside For/While)
    Returns (penalty_weight, details_list).
    """
    details: List[str] = []
    anti_patterns_found = 0.0

    # Build a parent map to allow ancestor queries in O(height) and avoid repeated nested walks
    parent_map: Dict[ast.AST, ast.AST] = {}
    nodes = [tree]
    while nodes:
        parent = nodes.pop()
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent
            nodes.append(child)

    # Collect nodes by type
    for_node_list = [n for n in ast.walk(tree) if isinstance(n, ast.For)]
    while_node_list = [n for n in ast.walk(tree) if isinstance(n, ast.While)]
    call_nodes = (n for n in ast.walk(tree) if isinstance(n, ast.Call))
    augassign_nodes = (n for n in ast.walk(tree) if isinstance(n, ast.AugAssign))

    # Detect list.insert(0, ...)
    for node in call_nodes:
        try:
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == 'insert' and len(node.args) >= 1:
                first_arg = node.args[0]
                if isinstance(first_arg, (ast.Constant, ast.Num)) and getattr(first_arg, 'value', getattr(first_arg, 'n', None)) == 0:
                    details.append(f"Inefficient 'list.insert(0, …)' at {file_path}:{node.lineno}")
                    anti_patterns_found += 1
        except Exception as e:
            logger.debug("Error scanning call node in %s: %s", file_path, e)
            continue

    # Detect string concatenation in loops by checking AugAssign nodes and looking for loop ancestors
    for node in augassign_nodes:
        if isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name):
            # check if any ancestor is For or While
            ancestor = parent_map.get(node)
            found_loop = False
            while ancestor:
                if isinstance(ancestor, (ast.For, ast.While)):
                    details.append(f"String concatenation in loop at {file_path}:{ancestor.lineno}")
                    anti_patterns_found += 0.5
                    found_loop = True
                    break
                ancestor = parent_map.get(ancestor)
            if found_loop:
                # early-exit for this augment node; continue with next
                continue

    # Detect nested loops: check if any For node has a For/While ancestor
    nested_found = False
    for loop_node in for_node_list:
        ancestor = parent_map.get(loop_node)
        while ancestor:
            if isinstance(ancestor, (ast.For, ast.While)):
                details.append(f"Nested loops (O(n²) risk) at {file_path}:{ancestor.lineno}")
                anti_patterns_found += 0.3
                nested_found = True
                break
            ancestor = parent_map.get(ancestor)
        if nested_found:
            # If we already found nested loop in this file, keep scanning but avoid repeating same message for many nodes
            nested_found = False  # reset to allow reporting other distinct locations

    return anti_patterns_found, details


def _assess_static_performance(codebase_path: str, python_files: List[str]) -> tuple[float, List[str]]:
    """Language-agnostic static performance heuristics via Lizard + optional Python anti-pattern checks."""
    details: List[str] = []
    penalties = 0.0

    # ---------------------------------------------------------------
    # 1. Universal metrics using `lizard` (supports many languages)
    # ---------------------------------------------------------------
    avg_cc, total_funcs, lizard_details = _run_lizard_analysis(codebase_path)
    details.extend(lizard_details)
    if avg_cc is not None:
        # Penalty: 1 point for every 2 points above CC=10
        if avg_cc > 10:
            penalties += (avg_cc - 10) / 2

        # High-complexity function penalty
        # Since _run_lizard_analysis already reports count, apply an estimated penalty
        # (keep behavior consistent with previous implementation)
        # We can't recompute ratio without cc_values here; keep a conservative approach by using details line if present
        for line in lizard_details:
            if "functions have CC > 20" in line:
                try:
                    parts = line.split()
                    count = int(parts[0])
                    ratio = count / total_funcs if total_funcs else 0
                    penalties += ratio * 3
                except Exception:
                    logger.debug("Failed to parse high CC functions line: %s", line)

    # ---------------------------------------------------------------
    # 2. Python-specific anti-pattern scan
    # ---------------------------------------------------------------
    anti_patterns_found = 0.0
    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue

        file_penalty, file_details = _scan_ast_for_antipatterns(tree, file_path)
        if file_details:
            details.extend(file_details)
        anti_patterns_found += file_penalty

    if anti_patterns_found:
        details.insert(0, f"Python anti-patterns found: {anti_patterns_found}")
        penalties += anti_patterns_found

    # ---------------------------------------------------------------
    # Final score (0-10 after penalties)
    # ---------------------------------------------------------------
    performance_score = 10.0 - penalties
    performance_score = max(0.0, min(10.0, performance_score))
    return performance_score, details


def _parse_memory_peaks_from_output(output_text: str) -> List[float]:
    """
    Parse memory_profiler output to extract peak memory numbers (MiB).
    Returns a list of floats.
    """
    peaks: List[float] = []
    for line in output_text.splitlines():
        if 'MiB' in line and 'maximum of' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'maximum' and i + 2 < len(parts):
                    try:
                        peak_mb = float(parts[i + 2])
                        peaks.append(peak_mb)
                        break
                    except ValueError:
                        continue
    return peaks


def _assess_dynamic_performance(profile_script: str) -> tuple[float, List[str], Dict[str, Any]]:
    """Dynamic runtime profiling with multiple samples."""
    details: List[str] = []
    metrics: Dict[str, Any] = {}

    if not os.path.isfile(profile_script):
        logger.warning("Profile script not found or not a file: %s", profile_script)
        details.append("Invalid profile_script provided for dynamic assessment.")
        metrics["execution_times"] = []
        metrics["memory_peaks_mb"] = []
        return 0.0, details, metrics

    # Run multiple samples for statistical confidence
    execution_times: List[float] = []
    memory_peaks: List[float] = []

    for run_num in range(3):  # 3 samples
        logger.debug("Dynamic profiling run %d for script %s", run_num + 1, profile_script)
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
                    logger.exception("Failed to read or parse pyinstrument output at %s", time_report_path)
        except Exception:
            logger.exception("pyinstrument profiling failed on run %d", run_num + 1)
        finally:
            try:
                if os.path.exists(time_report_path):
                    os.remove(time_report_path)
            except Exception:
                logger.debug("Failed to remove temporary time report %s", time_report_path)

        # === MEMORY PROFILING ===
        try:
            cmd = [sys.executable, "-m", "memory_profiler", profile_script]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if proc.returncode == 0:
                parsed_peaks = _parse_memory_peaks_from_output(proc.stdout)
                if parsed_peaks:
                    memory_peaks.extend(parsed_peaks)
        except Exception:
            logger.exception("memory_profiler run failed on run %d", run_num + 1)

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


class SubprocessSafetyTests(unittest.TestCase):
    def test_run_lizard_called_safely(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_stdout = json.dumps({"files": [{"functions": [{"cyclomatic_complexity": 5}, {"cyclomatic_complexity": 25}]}]})

            def fake_run(args, capture_output, text, check):
                # Ensure subprocess.run is called with a list and without shell usage
                self.assertIsInstance(args, list)
                self.assertEqual(args[0], "/usr/bin/lizard")
                class P:
                    pass
                p = P()
                p.returncode = 0
                p.stdout = fake_stdout
                return p

            with mock.patch('shutil.which', return_value="/usr/bin/lizard"):
                with mock.patch('subprocess.run', side_effect=fake_run):
                    avg_cc, total_funcs, details = _run_lizard_analysis(tmpdir)
                    self.assertEqual(total_funcs, 2)
                    self.assertAlmostEqual(avg_cc, 15.0)

    def test_assess_dynamic_uses_sys_executable_for_memory_profiler(self):
        # Create a temporary python script to profile
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as pf:
            pf.write(b"print('hello')\n")
            profile_path = pf.name

        def fake_run(cmd, capture_output, text, check):
            self.assertIsInstance(cmd, list)
            if cmd[0] == "pyinstrument":
                # cmd layout: ["pyinstrument", "--json", "-o", time_report_path, profile_script]
                time_report_path = cmd[3]
                with open(time_report_path, "w") as f:
                    json.dump({"duration": 0.12}, f)
                class P:
                    pass
                p = P()
                p.returncode = 0
                p.stdout = ""
                return p
            elif cmd[0] == sys.executable:
                # memory profiler invocation should use sys.executable
                class P:
                    pass
                p = P()
                p.returncode = 0
                p.stdout = "some text maximum of 150.0 MiB"
                return p
            else:
                raise AssertionError(f"Unexpected command invoked: {cmd}")

        with mock.patch('subprocess.run', side_effect=fake_run):
            dynamic_score, details, metrics = _assess_dynamic_performance(profile_path)
            # With duration 0.12s -> 120ms -> time_score 8, avg_memory 150 -> memory_score 8 => dynamic_score 8
            self.assertAlmostEqual(dynamic_score, 8.0)
            self.assertIn("Avg execution time", " ".join(details))
        try:
            os.remove(profile_path)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()