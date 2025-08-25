from radon.visitors import ComplexityVisitor
import logging
from io import StringIO

# Readability analysis is currently Python-specific
SUPPORTED_LANGUAGES = {"python"}
from pycodestyle import StyleGuide
from .utils import get_python_files

logger = logging.getLogger(__name__)

def _analyze_python_file(file_path: str):
    """
    Analyze a single Python file for function cyclomatic complexity.

    Returns:
    - messages: List[str] of human-readable findings for the file.
    - complexity_total: int sum of complexities for functions in the file.
    - function_count: int number of functions analyzed in the file.

    This helper extracts the per-file logic out of the main flow to reduce
    nesting in assess_readability and to make the behavior easier to test.
    It uses StringIO to efficiently accumulate multi-line messages for the file
    and then returns them as a list of lines.
    """
    messages = []
    try:
        with open(file_path, 'r', encoding='utf-8') as fh:
            source_code = fh.read()
    except OSError as exc:
        logger.warning("Failed to read %s: %s", file_path, exc)
        messages.append(f"Could not read {file_path}: {exc}")
        return messages, 0, 0

    try:
        visitor = ComplexityVisitor.from_code(source_code)
    except (SyntaxError, ValueError) as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        messages.append(f"Could not parse {file_path}: {exc}")
        return messages, 0, 0

    complexity_total = 0
    function_count = 0
    buffer = StringIO()

    # Iterate over functions in the file and record any high-complexity findings.
    # Using StringIO avoids repeated string concatenation in a loop.
    for func in visitor.functions:
        function_count += 1
        complexity_total += func.complexity
        if func.complexity > 10:
            buffer.write(f"High complexity ({func.complexity}) in function '{func.name}' at {file_path}:{func.lineno}\n")

    # Convert accumulated text into list entries (one per line) for consistent output.
    file_messages = buffer.getvalue().splitlines()
    messages.extend(file_messages)
    return messages, complexity_total, function_count


def assess_readability(codebase_path: str):
    """
    Assess the readability of a codebase at the given path.

    The assessment combines:
    - Cyclomatic complexity analysis (radon): lower is better.
    - PEP8 style compliance (pycodestyle): fewer violations is better.

    Returns:
    - readability_score: float between 0.0 and 10.0 (higher is better).
    - details: List[str] of messages describing findings and summary metrics.

    Implementation notes:
    - The per-file complexity processing is factored into a helper to avoid
      deep nesting and to make the main function concise.
    - StringIO is used in the helper to prevent inefficient string
      concatenation inside loops.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    details = []
    total_complexity = 0
    total_functions = 0

    # Process each Python file individually to keep the loop shallow and clear.
    for file_path in python_files:
        file_messages, file_complexity, file_function_count = _analyze_python_file(file_path)
        if file_messages:
            details.extend(file_messages)
        total_complexity += file_complexity
        total_functions += file_function_count

    # Compute average complexity per function; guard against division by zero.
    average_complexity = (total_complexity / total_functions) if total_functions > 0 else 0.0
    complexity_score = max(0, 10 - (average_complexity - 5))
    details.append(f"Average cyclomatic complexity: {average_complexity:.2f}")

    # Run PEP8/pycodestyle check once over all files.
    style_guide = StyleGuide(quiet=True)
    report = style_guide.check_files(python_files)
    pep8_errors = report.total_errors
    details.append(f"Found {pep8_errors} PEP8 style violations.")

    pep8_score = max(0, 10 - (pep8_errors / 5))

    # Weighted combination of complexity and style scores.
    readability_score = (0.6 * complexity_score + 0.4 * pep8_score)

    # Ensure returned score is within expected bounds.
    return min(10.0, max(0.0, readability_score)), details