from abc import ABC, abstractmethod
from typing import Tuple, List, Set

class BenchmarkPlugin(ABC):
    """Base class for all benchmark plug-ins with language awareness."""
    """Base class for all benchmark plug-ins."""

    name: str = "Unnamed"
    # Languages this plugin natively understands (lower-case identifiers).
    # Use {"any"} to apply to every project. Example: {"python"}, {"java", "javascript"}
    supported_languages: Set[str] = {"any"}
    # If True, run even if language not listed (heuristic / fallback mode).
    fallback: bool = False

    @abstractmethod
    def run(self, codebase_path: str) -> Tuple[float, List[str]]:
        """Return (score, details).""" 