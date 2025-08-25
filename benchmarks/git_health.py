from pathlib import Path

SUPPORTED_LANGUAGES = {"any"}
from datetime import datetime, timedelta
from collections import Counter
from typing import List

from git import Repo, InvalidGitRepositoryError

from .utils import get_python_files

THRESHOLD_DAYS = 180  # 6 months


# Primary entry point expected by dynamic loader
def assess_git_health(codebase_path: str):
    """Assess git-based code health: churn, age, hotspot identification.

    This function examines commits within the last THRESHOLD_DAYS and computes:
    - per-file churn counts (how many times each file was changed),
    - unique commit authors (bus factor),
    - average churn per file,
    - a short list of most-changed files.

    Returns:
        (score: float, details: List[str]) where score is 0-10 and details is
        a list of human-readable observations.
    """
    try:
        repo = Repo(Path(codebase_path).resolve(), search_parent_directories=True)
    except InvalidGitRepositoryError:
        return 5.0, ["Not a git repository; skipping git health checks."]

    now = datetime.utcnow()

    # Collect commits within the analysis window
    since_date = now - timedelta(days=THRESHOLD_DAYS)
    commits = list(repo.iter_commits(paths=codebase_path, since=since_date.isoformat()))

    # Counters for aggregated metrics
    file_counter: Counter[str] = Counter()
    author_counter: Counter[str] = Counter()

    # Aggregate file paths and authors from commits.
    # Refactor nested loops by collecting all file paths first, then counting.
    all_files = []
    for commit in commits:
        # Count commits per author to compute bus factor later
        author_counter[commit.author.email] += 1
        # Collect file paths changed in this commit for later bulk processing
        all_files.extend(commit.stats.files.keys())

    # Filter and count only Python files that are within the provided codebase_path.
    # This avoids nested per-commit/per-file counting and leverages Counter efficiency.
    filtered_python_files = [
        f for f in all_files if f.endswith(".py") and f.startswith(codebase_path)
    ]
    file_counter = Counter(filtered_python_files)

    details: List[str] = []

    if not file_counter:
        return 8.0, ["Low churn detected in the last 6 months."]

    # Prepare human-readable details for top changed files using join() for string assembly.
    most_changed = file_counter.most_common(5)
    for file_path, change_count in most_changed:
        details.append(" ".join([file_path, "changed", str(change_count), "times in last 6 months."]))

    avg_churn = sum(file_counter.values()) / len(file_counter)
    # Insert average churn at the front of details
    details.insert(0, f"Average churn / file: {avg_churn:.1f} commits in last 6 months.")

    bus_factor = len(author_counter)
    details.append(f"Bus factor (unique committers): {bus_factor}")

    # Scoring: moderate churn is ok; very high churn => lower score
    if avg_churn < 3:
        score = 9.0
    elif avg_churn < 10:
        score = 7.0
    elif avg_churn < 20:
        score = 5.0
    else:
        score = 3.0

    # Reward higher bus factor (more contributors)
    score += min(2.0, bus_factor / 5.0)

    return min(10.0, score), details

# Backward compatibility alias
assess_githealth = assess_git_health