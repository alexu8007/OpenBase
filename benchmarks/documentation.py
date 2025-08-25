import ast

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files, parse_file

def assess_documentation(codebase_path: str):
    """
    Assess documentation coverage and quality for a Python codebase.

    This function walks through all Python files discovered by get_python_files,
    parses each file into an AST, and inspects modules, classes, and functions
    for the presence and basic quality of docstrings.

    Scoring:
    - Coverage component: percentage of documentable entities (modules, classes,
      functions) that have docstrings, mapped to a 0-10 scale (100% -> 10).
    - Quality component: fraction of those docstrings that pass the internal
      _good_docstring heuristic, mapped to 0-10.
    - Final score: average of coverage and quality components, clamped to [0, 10].

    Returns:
    - tuple(float, list[str]):
      - score: float between 0 and 10 inclusive representing combined documentation score.
      - details: list of human-readable messages describing findings and detected issues.

    Parameters:
    - codebase_path: path to the root of the codebase to analyze.

    Notes:
    - The function intentionally treats modules, classes, and functions as
      documentable entities. Private vs public is not distinguished here; the
      heuristic only aims to detect presence and some structural qualities of
      docstrings. This is a lightweight, static check intended to improve
      documentation coverage, not to replace human review.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    total_entities = 0
    documented_entities = 0
    details = []

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
    Simple heuristic to decide if a docstring is "good".

    Heuristic rules:
    - Must contain at least 3 non-blank lines (typically: short summary, blank line, and a description).
    - Must not have more than 5 consecutive blank lines (to avoid excessive vertical spacing).
    - Must mention both argument-like sections and a returns section, e.g. "Args:"/"Parameters:" and "Returns:".

    The heuristic is intentionally conservative: it favors docstrings that are
    structured (multi-line) and include both input and output descriptions.
    This function is a light-weight static check and does not attempt to
    validate content beyond these surface signals.
    """
    raw_lines = ds.splitlines()

    # Use a generator to count non-blank lines to avoid building a potentially
    # large intermediate list when analyzing very long docstrings.
    non_blank_count = sum(1 for ln in raw_lines if ln.strip())

    # Must have at least summary + description lines (conservative threshold).
    if non_blank_count < 3:
        return False

    # Heuristic 2: reject if more than 5 consecutive blank lines (excessive vertical space)
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
    # Detect common parameter section markers. We check both "args:" and "parameters:"
    # to be tolerant of different docstring styles (Google vs NumPy/Sphinx-like).
    has_args = any(k in lowered for k in ("args:", "parameters:"))
    # Detect returns section marker.
    has_returns = "returns:" in lowered

    return has_args and has_returns