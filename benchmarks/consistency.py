import ast

SUPPORTED_LANGUAGES = {"python"}
import re
from .utils import get_python_files, parse_file

"""
Module to assess naming convention consistency within a Python codebase.

This module provides a function to walk Python ASTs and evaluate whether class,
function, and variable names follow preferred naming conventions:
- Class names should be CamelCase.
- Function and variable names should be snake_case.
"""

SNAKE_CASE_REGEX = re.compile(r"^[a-z_][a-z0-9_]*$")
CAMEL_CASE_REGEX = re.compile(r"^[A-Z][a-zA-Z0-9]*$")

def assess_consistency(codebase_path: str):
    """
    Assess naming convention consistency for Python files found under codebase_path.

    The function walks the AST of each Python file and checks:
    - ClassDef names for CamelCase compliance.
    - FunctionDef names for snake_case compliance (dunder methods are ignored).
    - Name nodes used as stores (variable assignments) for snake_case compliance.

    Returns:
        A tuple (consistency_score: float, issues: list[str]).
        - consistency_score is a float in the range [0.0, 10.0], where 10.0 indicates
          perfect consistency.
        - issues is a list of human-readable messages describing inconsistencies
          found (or informative messages if no files/names were found).

    Notes:
        - The check only applies to Python files discovered by get_python_files.
        - Files that cannot be parsed by parse_file are skipped.
    """
    python_file_paths = get_python_files(codebase_path)
    if not python_file_paths:
        return 0.0, ["No Python files found."]

    total_identifiers = 0
    inconsistent_identifiers = 0
    issues = []

    for file_path in python_file_paths:
        tree = parse_file(file_path)
        if not tree:
            continue

        for node in ast.walk(tree):
            # Check class names
            if isinstance(node, ast.ClassDef):
                total_identifiers += 1
                if not CAMEL_CASE_REGEX.match(node.name):
                    inconsistent_identifiers += 1
                    issues.append(
                        f"Inconsistent class name: '{node.name}' should be CamelCase. ({file_path}:{node.lineno})"
                    )
                continue

            # Check function names (ignore dunder methods)
            if isinstance(node, ast.FunctionDef):
                total_identifiers += 1
                if not node.name.startswith("__") and not SNAKE_CASE_REGEX.match(node.name):
                    inconsistent_identifiers += 1
                    issues.append(
                        f"Inconsistent function name: '{node.name}' should be snake_case. ({file_path}:{node.lineno})"
                    )
                continue

            # Check variable names used in assignments
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                total_identifiers += 1
                if not SNAKE_CASE_REGEX.match(node.id):
                    inconsistent_identifiers += 1
                    issues.append(
                        f"Inconsistent variable name: '{node.id}' should be snake_case. ({file_path}:{node.lineno})"
                    )

    if total_identifiers == 0:
        return 10.0, ["No relevant names found to check."]

    consistency_ratio = (total_identifiers - inconsistent_identifiers) / total_identifiers
    consistency_score = consistency_ratio * 10.0
    issues.insert(0, f"Naming consistency: {consistency_ratio*100:.2f}% ({total_identifiers - inconsistent_identifiers}/{total_identifiers} consistent)")

    return min(10.0, max(0.0, consistency_score)), issues