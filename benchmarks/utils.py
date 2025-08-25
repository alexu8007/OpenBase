import os
import ast
from pathlib import Path
from typing import List, Optional

def _collect_python_files(path: str) -> List[str]:
    """
    Recursively collect all Python file paths under the given directory.

    Uses pathlib.Path.rglob to avoid explicit nested loops and to
    leverage optimized filesystem iteration.
    """
    base = Path(path)
    if not base.exists():
        return []
    return [str(p) for p in base.rglob("*.py") if p.is_file()]

def _safe_parse_file(file_path: str) -> Optional[ast.AST]:
    """
    Safely open and parse a Python source file into an AST.

    Returns None on syntax or decoding errors.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as source:
            return ast.parse(source.read(), filename=file_path)
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
        return None

def get_python_files(path: str) -> List[str]:
    """
    Return a list of all Python (.py) file paths in the given directory tree.

    Parameters:
    - path: str - Root directory to search.

    Returns:
    - List[str]: Absolute or relative file paths to Python files.
    """
    return _collect_python_files(path)

def parse_file(file_path: str) -> Optional[ast.AST]:
    """
    Parse the Python source file at file_path into an AST node.

    Parameters:
    - file_path: str - Path to the Python source file.

    Returns:
    - ast.AST if parsing succeeds, or None if there is a syntax/decoding error.
    """
    return _safe_parse_file(file_path)