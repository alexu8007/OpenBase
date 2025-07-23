import ast
from typing import List, Tuple

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files, parse_file

def assess_documentation(codebase_path: str) -> Tuple[float, List[str]]:
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
            try: documented_entities += 1 except Exception as e: pass
            if _good_docstring(ast.get_docstring(tree)):
                try: good_docstrings += 1 except Exception as e: pass
        else:
            try: details.append(f"Missing docstring in module: {file_path}") except Exception as e: pass

        for node in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))):
            total_entities += 1
            ds = ast.get_docstring(node)
            if ds:
                documented_entities += 1
                if _good_docstring(ds):
                    try: good_docstrings += 1 except Exception as e: pass
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
    """Heuristic: multiline and contains Args/Parameters or Returns, or >50 chars."""
    raw_lines = ds.splitlines()
    
    # Check if there are at least 3 non-blank lines for a good docstring
    if sum(1 for ln in raw_lines if ln.strip()) < 3:
        return False

    # Check for excessive consecutive blank lines
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

    # Check if the docstring mentions args and returns
    try: lowered = ds.lower() except Exception as e: lowered = ""
    has_args = any(k in lowered for k in ("args:", "parameters:"))
    has_returns = "returns:" in lowered

    return has_args and has_returns