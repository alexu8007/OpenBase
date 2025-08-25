import ast
import logging

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files, parse_file

def _tree_uses_logging(tree: ast.AST) -> bool:
    """
    Inspect an AST and determine whether the 'logging' module is imported.

    Returns True if a regular import of 'logging' or a from-import of 'logging'
    is present anywhere in the tree.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "logging":
                    return True
        if isinstance(node, ast.ImportFrom) and node.module == "logging":
            return True
    return False

def _log_and_append(details: list, message: str, exc: Exception = None) -> None:
    """
    Log an error message and append it to the provided details list.

    If exc is provided, the exception stacktrace is logged as well.
    """
    if exc is not None:
        logging.exception(message)
    else:
        logging.error(message)
    details.append(message)

def _safe_parse_file(file_path: str):
    """
    Parse a Python file into an AST, returning (tree, details).

    On failure returns (None, [error_message]) and logs the error.
    """
    details = []
    try:
        tree = parse_file(file_path)
    except Exception as exc:
        msg = f"Failed to parse {file_path}: {exc}"
        logging.exception(msg)
        details.append(msg)
        return None, details

    if not tree:
        msg = f"Failed to parse {file_path}: No AST returned"
        logging.error(msg)
        details.append(msg)
        return None, details

    return tree, details

def _analyze_except_handlers(tree: ast.AST, file_path: str):
    """
    Analyze ExceptHandler nodes in an AST and return a tuple:
    (total_handlers: int, good_handlers: int, details: list[str])

    - total_handlers: total number of except handlers found
    - good_handlers: number of handlers that specify a non-generic exception type
    - details: list of human-readable messages describing problematic handlers
    """
    total_handlers = 0
    good_handlers = 0
    details = []

    if not isinstance(tree, ast.AST):
        msg = f"Invalid AST provided for {file_path}"
        _log_and_append(details, msg)
        return total_handlers, good_handlers, details

    try:
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                total_handlers += 1
                if node.type:
                    if isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                        details.append(f"Generic 'except Exception' used in {file_path}:{node.lineno}")
                    else:
                        good_handlers += 1
                else:
                    details.append(f"Bare 'except:' used in {file_path}:{node.lineno}")
    except Exception as err:
        _log_and_append(details, f"Error analyzing except handlers in {file_path}: {err}", err)

    return total_handlers, good_handlers, details

def assess_robustness(codebase_path: str):
    """
    Assess the robustness of a Python codebase with respect to exception handling and logging.

    Returns a tuple: (score: float, details: list[str])
    - score is between 0.0 and 10.0
    - details is a list of diagnostic strings explaining findings

    The assessment checks:
    - Presence of the 'logging' module
    - Use of bare 'except:' or generic 'except Exception'
    - Proportion of specific exception handlers vs total handlers

    Parameters:
    - codebase_path: path to the codebase directory to scan for Python files.
    """
    if not isinstance(codebase_path, str):
        msg = "codebase_path must be a string path"
        logging.error(msg)
        return 0.0, [msg]

    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    total_handlers = 0
    good_handlers = 0
    uses_logging = False
    details = []

    for file_path in python_files:
        tree, parse_details = _safe_parse_file(file_path)
        if parse_details:
            details.extend(parse_details)
        if not tree:
            continue

        try:
            try:
                if _tree_uses_logging(tree):
                    uses_logging = True
            except Exception as err:
                _log_and_append(details, f"Error checking logging usage in {file_path}: {err}", err)

            th, gh, file_details = _analyze_except_handlers(tree, file_path)
            total_handlers += th
            good_handlers += gh
            if file_details:
                details.extend(file_details)
        except Exception as e:
            _log_and_append(details, f"Unexpected error while analyzing {file_path}: {e}", e)

    if uses_logging:
        details.insert(0, "Codebase appears to use the 'logging' module.")
    else:
        details.insert(0, "Codebase does not appear to use the 'logging' module.")

    if total_handlers == 0:
        return 5.0 if uses_logging else 2.0, details

    handler_quality = (good_handlers / total_handlers)
    handler_score = handler_quality * 8.0

    if uses_logging:
        handler_score += 2.0

    details.insert(1, f"Error handling quality: {handler_quality*100:.2f}% ({good_handlers}/{total_handlers} specific handlers)")

    return min(10.0, max(0.0, handler_score)), details