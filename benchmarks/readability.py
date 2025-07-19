from radon.visitors import ComplexityVisitor

# Readability analysis is currently Python-specific
SUPPORTED_LANGUAGES = {"python"}
from pycodestyle import StyleGuide
from .utils import get_python_files

def assess_readability(codebase_path: str):
    """
    Assesses the readability of a codebase.
    - Cyclomatic Complexity: Lower is better.
    - PEP8 Compliance: Fewer errors is better.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    details = []
    total_complexity = 0
    total_functions = 0
    
    for file_path in python_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        try:
            visitor = ComplexityVisitor.from_code(code)
            for f in visitor.functions:
                if f.complexity > 10:
                    details.append(f"High complexity ({f.complexity}) in function '{f.name}' at {file_path}:{f.lineno}")
                total_complexity += f.complexity
                total_functions += 1
        except Exception:
            pass # Ignore files that can't be parsed

    avg_complexity = (total_complexity / total_functions) if total_functions > 0 else 0
    complexity_score = max(0, 10 - (avg_complexity - 5))
    details.append(f"Average cyclomatic complexity: {avg_complexity:.2f}")

    style_guide = StyleGuide(quiet=True)
    report = style_guide.check_files(python_files)
    pep8_errors = report.total_errors
    details.append(f"Found {pep8_errors} PEP8 style violations.")
    
    pep8_score = max(0, 10 - (pep8_errors / 5))
    
    readability_score = (0.6 * complexity_score + 0.4 * pep8_score)
    
    return min(10.0, max(0.0, readability_score)), details 