from pathlib import Path
from typing import Set

# Mapping of file extensions to language names
_EXT_MAP = {
    # C / C++ / C# / Objective-C
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".cs": "csharp",
    ".m": "objective-c",
    ".mm": "objective-cpp",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # Java
    ".java": "java",
    # JVM languages optional
    ".kt": "kotlin",
    # JavaScript / TypeScript
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    # Python
    ".py": "python",
    # HTML / CSS etc (for completeness)
    ".html": "html",
    ".css": "css",
    ".scss": "css",
}


def detect_languages(codebase_path: str | Path) -> Set[str]:
    """Return a set of language identifiers present in the directory tree."""
    codebase_path = Path(codebase_path)
    langs: Set[str] = set()
    for path in codebase_path.rglob("*"):
        if path.is_file():
            langs.add(_EXT_MAP.get(path.suffix.lower(), "unknown"))
    langs.discard("unknown")
    return langs
