"""
Module to assess robustness of a Python codebase with regard to exception handling and logging.

This module inspects Python files to:
- Detect whether the `logging` module is imported/used.
- Count exception handlers and distinguish specific exception types from generic handlers.
- Provide a numeric score (0.0-10.0) and a list of detail messages.

Failure modes and behavior:
- If no Python files are found, returns a score of 0.0 and a message list explaining that.
- If parsing a file fails or returns no AST, the file is skipped and a detail message is recorded.
- Any unexpected errors during analysis are logged via the standard `logging` module and recorded in the details.
- The function is conservative about scoring: missing handlers or bare/generic excepts reduce the robustness score.
"""

import ast
import logging

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files, parse_file

logger = logging.getLogger(__name__)


def _analyze_file_ast(tree: ast.AST, file_path: str):
    """
    Analyze the AST of a single file for logging usage and exception handler quality.

    Returns a tuple:
      (uses_logging: bool, total_handlers: int, good_handlers: int, file_details: list)

    This helper walks the AST once and collects relevant information. It avoids repeated
    string concatenation in loops by building message parts and joining them.
    """
    uses_logging = False
    total_handlers = 0
    good_handlers = 0
    file_details = []

    for node in ast.walk(tree):
        # Detect imports of the logging module
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "logging":
                    uses_logging = True
                    break
        elif isinstance(node, ast.ImportFrom):
            if node.module == "logging":
                uses_logging = True

        # Analyze exception handlers
        if isinstance(node, ast.ExceptHandler):
            total_handlers += 1
            if node.type:
                # Specific exception type present
                if isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    # Generic Exception used (still has a type but it's too broad)
                    msg_parts = ["Generic 'except Exception' used in ", file_path, ":", str(node.lineno)]
                    file_details.append("".join(msg_parts))
                else:
                    good_handlers += 1
            else:
                # Bare except:
                msg_parts = ["Bare 'except:' used in ", file_path, ":", str(node.lineno)]
                file_details.append("".join(msg_parts))

    return uses_logging, total_handlers, good_handlers, file_details


def assess_robustness(codebase_path: str):
    """
    Assess the robustness of a codebase with respect to exception handling and logging.

    Parameters:
      codebase_path: Path to the root of the codebase to analyze.

    Returns:
      A tuple (score: float, details: list). Score ranges from 0.0 to 10.0.
      Details is a list of human-readable messages explaining findings.

    Notes on failure modes:
      - If no Python files are found, returns (0.0, ["No Python files found."]).
      - If a file cannot be parsed (parse_file returns None or raises), the file is skipped,
        a detail message is recorded, and analysis proceeds for other files.
      - All unexpected exceptions during file analysis are logged and added to details.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    total_handlers = 0
    good_handlers = 0
    uses_logging = False
    details = []

    for file_path in python_files:
        try:
            tree = parse_file(file_path)
        except Exception as exc:
            logger.exception("Failed to parse file %s", file_path)
            details.append("Failed to parse file " + file_path + ": " + str(exc))
            continue

        if not tree:
            details.append("No AST produced for " + file_path + "; file skipped.")
            continue

        try:
            file_uses_logging, file_total, file_good, file_details = _analyze_file_ast(tree, file_path)
        except Exception as exc:
            logger.exception("Error analyzing AST for %s", file_path)
            details.append("Error analyzing " + file_path + ": " + str(exc))
            continue

        if file_uses_logging:
            uses_logging = True
        total_handlers += file_total
        good_handlers += file_good
        # Extend details with per-file messages
        if file_details:
            details.extend(file_details)

    # Prepend a summary about logging usage
    if uses_logging:
        details.insert(0, "Codebase appears to use the 'logging' module.")
    else:
        details.insert(0, "Codebase does not appear to use the 'logging' module.")

    if total_handlers == 0:
        return 5.0 if uses_logging else 2.0, details

    handler_quality = (good_handlers / total_handlers)
    handler_score = handler_quality * 8.0  # Max 8 points from handlers

    if uses_logging:
        handler_score += 2.0  # Bonus points for logging

    # Insert a human-readable summary of handler quality near the top of the details
    details.insert(1, f"Error handling quality: {handler_quality*100:.2f}% ({good_handlers}/{total_handlers} specific handlers)")

    return min(10.0, max(0.0, handler_score)), details