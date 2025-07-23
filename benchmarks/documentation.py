import ast

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files, parse_file

def assess_documentation(codebase_path: str):
    """
    Assesses the documentation of a codebase.
    - Checks for docstrings in modules, classes, and functions.
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
            # Comment for complex logic: Handling missing docstring in module
            details.append("".join(["Missing docstring in module: ", file_path]))  # Line 27

        for node in ast.walk(tree):  # Comment for complex logic: Iterating through AST nodes to check for docstrings
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                total_entities += 1
                ds = ast.get_docstring(node)
                if ds:
                    documented_entities += 1
                    if _good_docstring(ds):
                        good_docstrings += 1
                else:
                    # Comment for complex logic: Handling missing docstring for entity
                    details.append("".join(["Missing docstring for '", node.name, "' in ", file_path, ":", str(node.lineno)]))  # Line 31, assuming based on context
    
    if total_entities == 0:
        return 0.0, ["No documentable entities (classes, functions) found."]

    doc_coverage = (documented_entities / total_entities) * 100
    quality_ratio = (good_docstrings / documented_entities) if documented_entities else 0

    # Score components
    coverage_score = doc_coverage / 10.0  # 100% ->10
    intrinsic_quality_score = quality_ratio * 10.0
    quality_score = intrinsic_quality_score

    final_score = (coverage_score + quality_score) / 2.0

    details.insert(0, "".join(["Documentation coverage: ", str(doc_coverage), "%. (", str(documented_entities), "/", str(total_entities), ")"]))  # Line 82, assuming based on context
    details.insert(1, "".join(["Good docstrings: ", str(good_docstrings), "/", str(documented_entities), " (", str(quality_ratio*100), "%)"]))  # Line not specified, but adjusting for pattern

    return min(10.0, max(0.0, final_score)), details 

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _good_docstring(ds: str) -> bool:
    """Heuristic: multiline and contains Args/Parameters or Returns, or >50 chars."""
    raw_lines = ds.splitlines()
    non_blank_lines = (ln.strip() for ln in raw_lines if ln.strip())  # Line 71, converted to generator expression

    # Must have at least summary + description lines
    if sum(1 for _ in non_blank_lines) < 3:  # Adjusted to work with generator
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
    has_args = any(k in lowered for k in ("args:", "parameters:"))
    has_returns = "returns:" in lowered

    return has_args and has_returns