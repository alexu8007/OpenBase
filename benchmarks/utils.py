import os
import ast
from pathlib import Path
from typing import List, Optional

def _is_python_file(path: Path) -> bool:
    """Return True if the given Path points to a Python file by suffix."""
    return path.suffix == ".py"

def get_python_files(path: str) -> List[str]:
    """Recursively collect all Python (.py) files under the given path.

    Uses pathlib.Path.rglob to avoid explicit nested loops for file discovery.
    """
    base = Path(path)
    if not base.exists():
        return []
    return [str(p) for p in base.rglob("*.py") if p.is_file() and _is_python_file(p)]

def _parse_source(content: str, filename: str) -> Optional[ast.AST]:
    """Parse Python source content into an AST, returning None on parse errors."""
    try:
        return ast.parse(content, filename=filename)
    except (SyntaxError, UnicodeDecodeError):
        return None

def parse_file(file_path: str) -> Optional[ast.AST]:
    """Read a file and parse its contents into an AST node tree.

    Returns None if the file cannot be parsed due to syntax or decoding errors.
    """
    with open(file_path, "r", encoding="utf-8") as source:
        try:
            return _parse_source(source.read(), filename=file_path)
        except (SyntaxError, UnicodeDecodeError):
            return None