import subprocess

SUPPORTED_LANGUAGES = {"python"}
import json
import os
from .utils import get_python_files

def _run_subprocess(command, cwd=None):
    """
    Wrapper around subprocess.run to allow easy mocking in tests.
    Executes the provided command list and returns the subprocess.CompletedProcess.

    Security rationale:
    - Accepts only a list/tuple of string arguments to avoid invoking a shell and
      mitigate shell injection risks.
    - Rejects arguments containing null bytes which can be used to truncate strings
      in some APIs.
    - Note: we intentionally do not use shell=True anywhere in this codebase.
    """
    if not isinstance(command, (list, tuple)):
        raise ValueError("command must be a list or tuple of arguments")
    for arg in command:
        if not isinstance(arg, str):
            raise ValueError("all command arguments must be str")
        if "\x00" in arg:
            raise ValueError("command arguments must not contain null bytes")
    return subprocess.run(command, capture_output=True, text=True, check=False, cwd=cwd)

def assess_testability(codebase_path: str):
    """
    Assess the testability of a codebase by running tests and measuring coverage.

    Parameters:
    - codebase_path: Path to the codebase root where tests and coverage report should be generated.

    Returns:
    - tuple(score: float, details: list[str])
      score: A value between 0.0 and 10.0 derived from coverage percentage (coverage% / 10).
      details: Human-readable messages describing findings and issues.

    Behavior:
    - Searches for Python files using get_python_files(codebase_path).
    - Detects presence of test files (filenames containing "test" case-insensitive).
    - Runs pytest with coverage to generate a coverage.json in the codebase root.
    - Parses coverage.json to extract percent_covered and maps it to a score.
    - Cleans up the coverage.json file after processing.
    """
    details = []
    
    # Check for presence of test files
    python_files = get_python_files(codebase_path)
    # Use generator to avoid creating large intermediate lists when scanning huge codebases
    test_files_gen = (f for f in python_files if "test" in os.path.basename(f).lower())
    if not any(test_files_gen):
        return 0.0, ["No test files found (e.g., files named test_*.py)."]

    json_report_path = os.path.join(codebase_path, "coverage.json")
    
    # Run pytest with coverage using the subprocess wrapper
    try:
        # Note: This assumes the codebase's dependencies are installed in the environment.
        command = [
            "pytest",
            "--cov=" + codebase_path,
            "--cov-report=json:" + json_report_path,
            codebase_path
        ]
        _run_subprocess(command, cwd=codebase_path)
    except FileNotFoundError:
        return 0.0, ["Could not run pytest. Is it installed and in your PATH?"]
    
    if not os.path.exists(json_report_path):
        return 0.0, ["Coverage report (coverage.json) was not generated. Tests may have failed."]

    try:
        with open(json_report_path) as f:
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
        if os.path.exists(json_report_path):
            os.remove(json_report_path) # Clean up

    return min(10.0, max(0.0, score)), details 


# Unit tests for edge cases and behavior. Placed here to avoid creating new files.
import tempfile
import unittest

class AssessTestabilityTests(unittest.TestCase):
    def setUp(self):
        # Preserve originals to restore after tests
        self._orig_get_python_files = globals().get("get_python_files")
        self._orig_run = globals().get("_run_subprocess")

    def tearDown(self):
        if self._orig_get_python_files is not None:
            globals()["get_python_files"] = self._orig_get_python_files
        if self._orig_run is not None:
            globals()["_run_subprocess"] = self._orig_run

    def test_no_test_files(self):
        globals()["get_python_files"] = lambda path: ["module.py", "utils.py"]
        score, details = assess_testability("/fake/path")
        self.assertEqual(score, 0.0)
        self.assertTrue(any("No test files found" in d for d in details))

    def test_pytest_not_installed(self):
        globals()["get_python_files"] = lambda path: ["test_sample.py"]
        def raise_fn(cmd, cwd=None):
            raise FileNotFoundError()
        globals()["_run_subprocess"] = raise_fn
        score, details = assess_testability("/fake/path")
        self.assertEqual(score, 0.0)
        self.assertTrue(any("Could not run pytest" in d for d in details))

    def test_no_coverage_report_generated(self):
        # Simulate tests ran but no coverage file created
        globals()["get_python_files"] = lambda path: ["test_sample.py"]
        def fake_run(cmd, cwd=None):
            class Dummy:
                returncode = 1
            return Dummy()
        globals()["_run_subprocess"] = fake_run
        with tempfile.TemporaryDirectory() as tmp:
            score, details = assess_testability(tmp)
            self.assertEqual(score, 0.0)
            self.assertTrue(any("Coverage report" in d for d in details))

    def test_malformed_coverage_json(self):
        globals()["get_python_files"] = lambda path: ["test_sample.py"]
        def fake_run(cmd, cwd=None):
            class Dummy:
                returncode = 0
            # Create a malformed coverage.json
            path = os.path.join(cwd, "coverage.json")
            with open(path, "w") as f:
                f.write("{ invalid json ")
            return Dummy()
        globals()["_run_subprocess"] = fake_run
        with tempfile.TemporaryDirectory() as tmp:
            score, details = assess_testability(tmp)
            self.assertEqual(score, 0.0)
            self.assertTrue(any("Could not parse coverage report" in d for d in details))

    def test_valid_coverage_results_in_score(self):
        globals()["get_python_files"] = lambda path: ["test_sample.py"]
        def fake_run(cmd, cwd=None):
            class Dummy:
                returncode = 0
            path = os.path.join(cwd, "coverage.json")
            with open(path, "w") as f:
                json.dump({"totals": {"percent_covered": 85}}, f)
            return Dummy()
        globals()["_run_subprocess"] = fake_run
        with tempfile.TemporaryDirectory() as tmp:
            score, details = assess_testability(tmp)
            self.assertAlmostEqual(score, 8.5)
            self.assertTrue(any("Test coverage" in d for d in details))
            self.assertFalse(any("Low coverage" in d for d in details))

if __name__ == "__main__":
    unittest.main()