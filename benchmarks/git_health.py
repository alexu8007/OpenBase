from pathlib import Path

SUPPORTED_LANGUAGES = {"any"}
from datetime import datetime, timedelta
from collections import Counter
from typing import List

from git import Repo, InvalidGitRepositoryError

from .utils import get_python_files

THRESHOLD_DAYS = 180  # 6 months


def _score_from_avg_and_bus_factor(avg_churn: float, bus_factor: int) -> float:
    """Compute a health score based on average churn and bus factor.

    Score rules:
    - avg_churn < 3  => base 9.0
    - 3 <= avg_churn < 10 => base 7.0
    - 10 <= avg_churn < 20 => base 5.0
    - avg_churn >= 20 => base 3.0

    Then reward by adding up to 2.0 based on bus_factor (bus_factor/5 capped at 2.0).
    Final score is capped at 10.0.
    """
    if avg_churn < 3:
        base_score = 9.0
    elif avg_churn < 10:
        base_score = 7.0
    elif avg_churn < 20:
        base_score = 5.0
    else:
        base_score = 3.0

    bonus = min(2.0, bus_factor / 5.0)
    return min(10.0, base_score + bonus)


# Primary entry point expected by dynamic loader
def assess_git_health(codebase_path: str):
    """Assess git-based code health for a given codebase path.

    Returns a tuple (score: float, details: List[str]).
    Score is in range [0.0, 10.0]. Details is a list of human-readable strings
    describing churn and contributor statistics.

    This function inspects commits in the last THRESHOLD_DAYS and:
    - Counts Python file modifications under the provided path.
    - Estimates average churn per file and identifies most-changed files.
    - Computes a bus factor from unique commit authors.
    """
    try:
        repo = Repo(Path(codebase_path).resolve(), search_parent_directories=True)
    except InvalidGitRepositoryError:
        return 5.0, ["Not a git repository; skipping git health checks."]

    now = datetime.utcnow()

    # Map file -> commits last THRESHOLD_DAYS
    since_date = now - timedelta(days=THRESHOLD_DAYS)
    commits = list(repo.iter_commits(paths=codebase_path, since=since_date.isoformat()))

    # Collect author emails and Python file changes efficiently using comprehensions
    author_emails = [commit.author.email for commit in commits]
    unique_authors = set(author_emails)

    py_files = [
        f
        for commit in commits
        for f in commit.stats.files.keys()
        if f.endswith(".py") and f.startswith(codebase_path)
    ]
    file_counter: Counter[str] = Counter(py_files)

    details: List[str] = []

    if not file_counter:
        return 8.0, ["Low churn detected in the last 6 months."]

    most_changed = file_counter.most_common(5)
    # Build detail strings using a comprehension (avoids repeated append calls)
    details.extend([f"{f} changed {n} times in last 6 months." for f, n in most_changed])

    avg_churn = sum(file_counter.values()) / len(file_counter)
    details.insert(0, f"Average churn / file: {avg_churn:.1f} commits in last 6 months.")

    bus_factor = len(unique_authors)
    details.append(f"Bus factor (unique committers): {bus_factor}")

    score = _score_from_avg_and_bus_factor(avg_churn, bus_factor)

    return min(10.0, score), details

# Backward compatibility alias
assess_githealth = assess_git_health

if __name__ == "__main__":
    # Basic unit tests for algorithmic branches of the scoring function.
    # These tests exercise the different avg_churn thresholds and bus factor bonuses.
    def _almost_equal(a: float, b: float, tol: float = 1e-6) -> bool:
        return abs(a - b) <= tol

    # avg_churn < 3 branch
    assert _almost_equal(_score_from_avg_and_bus_factor(0.0, 0), 9.0)
    assert _almost_equal(_score_from_avg_and_bus_factor(2.9, 1), 9.0 + min(2.0, 1 / 5.0))

    # 3 <= avg_churn < 10 branch
    assert _almost_equal(_score_from_avg_and_bus_factor(3.0, 0), 7.0)
    assert _almost_equal(_score_from_avg_and_bus_factor(9.9, 5), min(10.0, 7.0 + min(2.0, 5 / 5.0)))

    # 10 <= avg_churn < 20 branch
    assert _almost_equal(_score_from_avg_and_bus_factor(10.0, 0), 5.0)
    assert _almost_equal(_score_from_avg_and_bus_factor(15.0, 10), 5.0 + min(2.0, 10 / 5.0))

    # avg_churn >= 20 branch
    assert _almost_equal(_score_from_avg_and_bus_factor(20.0, 0), 3.0)
    assert _almost_equal(_score_from_avg_and_bus_factor(25.0, 20), min(10.0, 3.0 + min(2.0, 20 / 5.0)))

    print("All internal unit tests passed.")