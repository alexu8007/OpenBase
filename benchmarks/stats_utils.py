"""Statistical utilities for benchmark normalization and confidence intervals."""

import numpy as np
from scipy import stats
from typing import List, Tuple, Dict, Any
from .utils import get_python_files

def _count_nonblank_lines_in_file(file_path: str) -> int:
    """
    Count non-blank lines in a file using a generator expression to avoid
    building a large list in memory.

    Returns:
        int: Number of non-empty lines in the file. Returns 0 if the file
             cannot be read due to encoding or I/O errors.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return sum(1 for line in f if line.strip())
    except (UnicodeDecodeError, IOError):
        return 0

def get_codebase_size_bucket(codebase_path: str) -> str:
    """Categorize codebase by total lines of code."""
    python_files = get_python_files(codebase_path)
    total_loc = 0
    
    for file_path in python_files:
        total_loc += _count_nonblank_lines_in_file(file_path)
    
    if total_loc < 100:
        return "small"
    elif total_loc < 1000:
        return "medium"
    else:
        return "large"


def normalize_scores_zscore(scores: Dict[str, float]) -> Dict[str, float]:
    """
    Apply light normalization to prevent extreme outliers from dominating,
    but preserve the original score relationships for meaningful comparison.
    """
    if len(scores) < 2:
        return scores
    
    values = list(scores.values())
    max_score = max(values)
    
    # If max score is very high compared to others, apply light scaling
    if max_score > 15.0:  # Only normalize if we have extreme outliers
        normalized = {}
        for name, score in scores.items():
            # Scale down extreme scores but preserve relative relationships
            if score > 10.0:
                normalized[name] = 10.0 + (score - 10.0) * 0.3  # Compress scores above 10
            else:
                normalized[name] = score
        return normalized
    else:
        # No normalization needed - return original scores
        return scores


def calculate_confidence_interval(
    scores: List[float], 
    confidence: float = 0.95
) -> Tuple[float, float]:
    """Calculate confidence interval for a set of scores."""
    if len(scores) < 2:
        return (0.0, 0.0)
    
    mean_score = np.mean(scores)
    sem = stats.sem(scores)  # standard error of mean
    interval = stats.t.interval(confidence, len(scores)-1, loc=mean_score, scale=sem)
    
    return interval


def adjust_score_for_size(raw_score: float, bucket: str, metric_type: str) -> float:
    """Adjust scores based on codebase size to reduce bias."""
    adjustments = {
        "maintainability": {
            "small": 1.5,    # Small codebases get bonus (MI often artificially low)
            "medium": 1.0,   # No adjustment
            "large": 0.9     # Large codebases slightly penalized (complexity expected)
        },
        "readability": {
            "small": 1.2,
            "medium": 1.0,
            "large": 0.95
        },
        "default": {
            "small": 1.1,
            "medium": 1.0,
            "large": 1.0
        }
    }
    
    multiplier = adjustments.get(metric_type, adjustments["default"]).get(bucket, 1.0)
    return min(10.0, raw_score * multiplier)


class BenchmarkResult:
    """Enhanced result container with confidence intervals and metadata."""
    
    def __init__(
        self, 
        score: float, 
        details: List[str], 
        raw_metrics: Dict[str, Any] = None,
        confidence_interval: Tuple[float, float] = None
    ):
        self.score = score
        self.details = details
        self.raw_metrics = raw_metrics or {}
        self.confidence_interval = confidence_interval or (score, score)
    
    def __iter__(self):
        """Maintain backward compatibility with tuple unpacking."""
        return iter((self.score, self.details))
    
    def format_score_with_ci(self) -> str:
        """Format score with confidence interval."""
        if self.confidence_interval[0] == self.confidence_interval[1]:
            return f"{self.score:.2f}"
        
        ci_range = self.confidence_interval[1] - self.confidence_interval[0]
        return f"{self.score:.2f} ±{ci_range/2:.1f}"