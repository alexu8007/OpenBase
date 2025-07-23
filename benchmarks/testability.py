import subprocess

SUPPORTED_LANGUAGES = {"python"}
import json
import os
from .utils import get_python_files

def assess_testability(codebase_path: str):
    """
    Assesses the testability of a codebase by running tests and measuring coverage.
    """
    details = []
    
    # Check for presence of test files
    python_files = get_python_files(codebase_path)
    test_files = (f for f in python_files if "test" in os.path.basename(f).lower())
    if not any(test_files):
        return 0.0, ["No test files found (e.g., files named test_*.py)."]

    json_report_path = os.path.join(codebase_path, "coverage.json")
    
    # Run pytest with coverage
    try:
        if not os.path.isdir(codebase_path):
            return 0.0, ["Invalid codebase path."]
        command = [
            "pytest",
            "--cov=" + codebase_path,
            "--cov-report=json:" + json_report_path,
            codebase_path
        ]
        subprocess.run(command, capture_output=True, text=True, check=False, cwd=codebase_path)
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