import ast
from typing import Tuple, List

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files, parse_file

def assess_documentation(codebase_path: str) -> Tuple[float, List[str]]:
    """
    Assess the documentation quality of a Python codebase.

    This function walks through all Python files found under the provided
    codebase path, checks for module, class, and function docstrings, and
    computes a simple score composed of documentation coverage and an
    intrinsic docstring quality measure.

    Parameters
    - codebase_path (str): Filesystem path to the root of the codebase to scan.

    Returns
    - Tuple[float, List[str]]: A tuple where the first element is a score in the
      range [0.0, 10.0] and the second element is a list of human-readable
      details about missing docstrings and coverage metrics.

    Example:
    >>> score, details = assess_documentation("/path/to/project")
    >>> isinstance(score, float) and isinstance(details, list)
    True
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    total_entities = 0
    documented_entities = 0
    details: List[str] = []

    good_docstrings = 0

    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue
        
        # Module docstring
        total_entities += 1
        if ast.get_docstring(tree):
            documented_entities += 1
            if _good_docstring(ast.get_docstring(tree)):
                good_docstrings += 1
        else:
            details.append(f"Missing docstring in module: {file_path}")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                total_entities += 1
                ds = ast.get_docstring(node)
                if ds:
                    documented_entities += 1
                    if _good_docstring(ds):
                        good_docstrings += 1
                else:
                    details.append(f"Missing docstring for '{node.name}' in {file_path}:{node.lineno}")
    
    if total_entities == 0:
        return 0.0, ["No documentable entities (classes, functions) found."]

    doc_coverage = (documented_entities / total_entities) * 100
    quality_ratio = (good_docstrings / documented_entities) if documented_entities else 0

    # Score components
    coverage_score = doc_coverage / 10.0  # 100% ->10
    intrinsic_quality_score = quality_ratio * 10.0
    quality_score = intrinsic_quality_score

    final_score = (coverage_score + quality_score) / 2.0

    details.insert(0, f"Documentation coverage: {doc_coverage:.2f}% ({documented_entities}/{total_entities})")
    details.insert(1, f"Good docstrings: {good_docstrings}/{documented_entities} ({quality_ratio*100:.1f}%)")

    return min(10.0, max(0.0, final_score)), details 

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _good_docstring(ds: str) -> bool:
    """
    Heuristic to determine whether a docstring is of 'good' quality.

    Current heuristic:
    - Must contain at least three non-blank lines (summary + description)
    - Must not contain more than 5 consecutive blank lines (excessive vertical space)
    - Must include both an arguments section (e.g., "Args:" or "Parameters:") and a "Returns:" section.

    Parameters
    - ds (str): The docstring to evaluate.

    Returns
    - bool: True if the docstring meets the heuristic, False otherwise.
    """
    raw_lines = ds.splitlines()
    # Count non-blank lines using a generator to avoid constructing large intermediate lists.
    non_blank_count = sum(1 for ln in raw_lines if ln.strip())

    # Must have at least summary + description lines
    if non_blank_count < 3:
        return False

    # Heuristic 2: reject if there are more than 5 consecutive blank lines
    # This loop detects excessive vertical spacing inside the docstring.
    consecutive_blanks = 0
    excessive_blanks = False
    for ln in raw_lines:
        if ln.strip() == "":
            consecutive_blanks += 1
            if consecutive_blanks > 5:
                excessive_blanks = True
                break
        else:
            consecutive_blanks = 0

    if excessive_blanks:
        return False

    lowered = ds.lower()
    has_args = any(k in lowered for k in ("args:", "parameters:"))
    has_returns = "returns:" in lowered

    return has_args and has_returns