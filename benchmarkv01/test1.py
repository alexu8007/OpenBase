import ast
import os
import subprocess
import shutil

# Works across languages via lizard
SUPPORTED_LANGUAGES = {"any"}
import json
import tempfile
import statistics
from typing import List, Dict, Any
from .utils import get_python_files, parse_file
from .stats_utils import BenchmarkResult, calculate_confidence_interval, adjust_score_for_size, get_codebase_size_bucket

def _is_valid_path(p: str) -> bool:
    """
    Basic validation for filesystem paths used as subprocess arguments.
    Ensures p is a string, contains no null bytes, and resolves to an existing path.
    """
    if not isinstance(p, str):
        return False
    if "\x00" in p:
        return False
    try:
        abs_p = os.path.abspath(p)
    except Exception:
        return False
    return os.path.exists(abs_p)

def _validate_subprocess_cmd(cmd: List[str]) -> None:
    """
    Validate a subprocess command list before execution.
    Expectations / safety:
    - cmd must be a non-empty list/tuple of strings.
    - No element may contain a null byte.
    - The list form is required to avoid shell interpretation; shell=True is not used.
    Calling code should handle exceptions raised here and avoid executing if validation fails.
    """
    if not isinstance(cmd, (list, tuple)) or len(cmd) == 0:
        raise ValueError("subprocess command must be a non-empty list")
    for i, part in enumerate(cmd):
        if not isinstance(part, str):
            raise ValueError(f"subprocess command element at index {i} is not a string")
        if "\x00" in part:
            raise ValueError("subprocess command elements must not contain null bytes")

def _safe_run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Wrapper around subprocess.run that validates the command list to avoid shell injection
    risks. This enforces using argument lists (no shell=True) and rejects invalid elements.
    """
    _validate_subprocess_cmd(cmd)
    # Explicitly avoid passing shell=True through kwargs
    if kwargs.get("shell", False):
        raise ValueError("shell=True is not allowed; use an argument list instead")
    return subprocess.run(cmd, **kwargs)

def assess_performance(codebase_path: str) -> BenchmarkResult:
    """
    Hybrid static + dynamic performance assessment.
    Combines anti-pattern detection with runtime profiling.

    Safety expectations:
    - codebase_path must be an existing directory path. This is validated to avoid
      passing user-controlled invalid paths to subprocesses later.
    """
    # Validate codebase_path early (defensive)
    if not isinstance(codebase_path, str) or "\x00" in codebase_path or not os.path.exists(codebase_path) or not os.path.isdir(codebase_path):
        return BenchmarkResult(0.0, ["Invalid codebase_path provided; must be an existing directory."])

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
    """Language-agnostic static performance heuristics via Lizard + optional Python anti-pattern checks.

    Safety expectations for subprocess usage:
    - Calls to external tool 'lizard' are executed via argument lists (no shell) and validated
      to ensure each argument is a string without null bytes. The presence of the lizard
      executable is checked before invocation.
    """
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
        try:
            # Use validated argument list to avoid shell=True and injection risks
            cmd = [lizard_executable, "-j", codebase_path]
            try:
                _validate_subprocess_cmd(cmd)
            except ValueError as ve:
                details.append(f"[!] lizard command validation failed: {ve}")
                avg_cc = None
                total_funcs = 0
            else:
                proc = _safe_run(cmd, capture_output=True, text=True, check=False)
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    func_records = [f for file in data.get("files", []) for f in file.get("functions", [])]
                    total_funcs = len(func_records)
                    cc_values = [f.get("cyclomatic_complexity", 0) for f in func_records]
                    avg_cc = (sum(cc_values) / total_funcs) if total_funcs else None

                    if avg_cc is not None:
                        details.append(f"Average cyclomatic complexity (all languages): {avg_cc:.1f}")
                        # Penalty: 1 point for every 2 points above CC=10
                        if avg_cc > 10:
                            penalties += (avg_cc - 10) / 2

                        # High-complexity function penalty
                        high_cc_funcs = [v for v in cc_values if v > 20]
                        if high_cc_funcs:
                            ratio = len(high_cc_funcs) / total_funcs
                            penalties += ratio * 3  # up to 3-point penalty
                            details.append(f"{len(high_cc_funcs)} / {total_funcs} functions have CC > 20")
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
    anti_patterns_found = 0.0
    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue

        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'insert' and len(node.args) == 2 and hasattr(node.args[0], 'value') and node.args[0].value == 0):
                details.append(f"Inefficient 'list.insert(0, …)' at {file_path}:{node.lineno}")
                anti_patterns_found += 1
            if isinstance(node, (ast.For, ast.While)):
                for sub_node in ast.walk(node):
                    if isinstance(sub_node, ast.AugAssign) and isinstance(sub_node.op, ast.Add) and isinstance(sub_node.target, ast.Name):
                        details.append(f"String concatenation in loop at {file_path}:{node.lineno}")
                        anti_patterns_found += 0.5
            if isinstance(node, ast.For):
                for sub_node in ast.walk(node):
                    if isinstance(sub_node, ast.For) and sub_node is not node:
                        details.append(f"Nested loops (O(n²) risk) at {file_path}:{node.lineno}")
                        anti_patterns_found += 0.3

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
    """Dynamic runtime profiling with multiple samples.

    Safety expectations:
    - profile_script must be an existing file path. This function validates the path
      and rejects invalid inputs to prevent accidental execution of unintended targets.
    - All subprocess invocations use argument lists (no shell=True) and the command lists
      are validated to ensure elements are strings without null bytes.
    """
    # Validate profile_script defensively
    if not isinstance(profile_script, str) or "\x00" in profile_script or not os.path.exists(profile_script) or not os.path.isfile(profile_script):
        raise ValueError("profile_script must be an existing file path")

    details = []
    metrics = {}
    
    # Run multiple samples for statistical confidence
    execution_times = []
    memory_peaks = []
    
    for run_num in range(3):  # 3 samples
        # === TIME PROFILING ===
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            time_report_path = tmp.name
        
        try:
            cmd = ["pyinstrument", "--json", "-o", time_report_path, profile_script]
            try:
                _validate_subprocess_cmd(cmd)
                proc = _safe_run(cmd, capture_output=True, text=True, check=False)
            except Exception:
                proc = None
            
            if proc and proc.returncode == 0 and os.path.exists(time_report_path):
                with open(time_report_path) as f:
                    time_data = json.load(f)
                execution_time = time_data.get("duration", 0) * 1000  # ms
                execution_times.append(execution_time)
        except Exception:
            pass
        finally:
            if os.path.exists(time_report_path):
                os.remove(time_report_path)
        
        # === MEMORY PROFILING ===
        try:
            cmd = ["python", "-m", "memory_profiler", profile_script]
            try:
                _validate_subprocess_cmd(cmd)
                proc = _safe_run(cmd, capture_output=True, text=True, check=False)
            except Exception:
                proc = None
            
            if proc and proc.returncode == 0:
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
        except Exception:
            pass
    
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