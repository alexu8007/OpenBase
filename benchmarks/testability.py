import subprocess
import logging

SUPPORTED_LANGUAGES = {"python"}
import json
import os
from .utils import get_python_files
from typing import Callable, Iterable, Tuple, List, Any

logger = logging.getLogger(__name__)

def assess_testability(
    codebase_path: str,
    subprocess_run: Callable[..., Any] = subprocess.run,
    file_opener: Callable[..., Any] = open,
    path_exists: Callable[[str], bool] = os.path.exists,
    path_isdir: Callable[[str], bool] = os.path.isdir,
    path_access: Callable[[str, int], bool] = os.access,
    remove_file: Callable[[str], None] = os.remove,
    list_python_files: Callable[[str], Iterable[str]] = get_python_files,
) -> Tuple[float, List[str]]:
    """
    Assess the testability of a Python codebase by running its tests and measuring coverage.

    This function is designed for improved testability itself:
    - External interactions (subprocess invocation, file operations, path checks, and file listing)
      can be injected via parameters for easier unit testing and mocking.
    - Pure logic is separated from side effects by delegating I/O to the injected callables.

    Parameters:
    - codebase_path: Path to the codebase directory to assess.
    - subprocess_run: Callable used to invoke external processes (default: subprocess.run).
    - file_opener: Callable used to open files (default: built-in open).
    - path_exists: Callable to check path existence (default: os.path.exists).
    - path_isdir: Callable to check if a path is a directory (default: os.path.isdir).
    - path_access: Callable to check path access permissions (default: os.access).
    - remove_file: Callable used to remove files (default: os.remove).
    - list_python_files: Callable that returns an iterable of python file paths given a directory
      (default: get_python_files from .utils).

    Returns:
    A tuple of (score: float, details: List[str]) where score is between 0.0 and 10.0.
    """
    details: List[str] = []
    
    # Input validation: defensive checks on codebase_path before any external calls
    if not isinstance(codebase_path, str) or not codebase_path:
        raise ValueError("codebase_path must be a non-empty string.")
    if "\x00" in codebase_path:
        return 0.0, ["Invalid codebase_path."]
    if len(codebase_path) > 4096:
        return 0.0, ["codebase_path is too long."]
    
    # Normalize and verify path
    codebase_path = os.path.abspath(codebase_path)
    if not path_exists(codebase_path) or not path_isdir(codebase_path):
        return 0.0, [f"Provided codebase_path '{codebase_path}' is not an existing directory."]
    if not path_access(codebase_path, os.R_OK):
        return 0.0, ["codebase_path is not readable."]
    
    # Check for presence of test files
    python_files = list_python_files(codebase_path)
    test_files_gen = (f for f in python_files if "test" in os.path.basename(f).lower())
    if not any(True for _ in test_files_gen):
        return 0.0, ["No test files found (e.g., files named test_*.py)."]

    json_report_path = os.path.join(codebase_path, "coverage.json")
    
    # Run pytest with coverage using safe subprocess invocation (no shell) and explicit argument separation.
    try:
        # Note: This assumes the codebase's dependencies are installed in the environment.
        # Use separate args for options to avoid injection via leading '-' in paths and add '--' before positional args.
        command = [
            "pytest",
            "--cov", codebase_path,
            "--cov-report", "json:" + json_report_path,
            "--",
            codebase_path,
        ]
        subprocess_run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=codebase_path,
            timeout=300
        )
    except FileNotFoundError:
        logger.exception("pytest executable not found when attempting to run tests.")
        return 0.0, ["Could not run pytest. Is it installed and in your PATH?"]
    except subprocess.TimeoutExpired:
        logger.exception("pytest timed out when running tests.")
        return 0.0, ["Pytest run timed out while assessing testability."]
    except Exception as e:
        logger.exception("Unexpected error when invoking pytest: %s", e)
        return 0.0, [f"Unexpected error when running pytest: {str(e)}"]
    
    if not path_exists(json_report_path):
        return 0.0, ["Coverage report (coverage.json) was not generated. Tests may have failed."]

    try:
        with file_opener(json_report_path) as f:
            report = json.load(f)
        
        coverage_percent = report.get("totals", {}).get("percent_covered", 0.0)
        details.append(f"Test coverage: {coverage_percent:.2f}%")
        
        # Scoring: 100% coverage = 10 points. 80% = 8 points, etc.
        score = coverage_percent / 10.0
        
        if coverage_percent < 50:
            details.append("Low coverage. Consider adding more tests for critical paths.")

    except (json.JSONDecodeError, FileNotFoundError):
        score = 0.0
        details.append("Could not parse coverage report.")
    finally:
        if path_exists(json_report_path):
            try:
                remove_file(json_report_path) # Clean up
            except Exception:
                logger.exception("Failed to remove coverage report at %s", json_report_path)

    return min(10.0, max(0.0, score)), details