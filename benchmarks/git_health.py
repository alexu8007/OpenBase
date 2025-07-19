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
    """Assess git-based code health: churn, age, hotspot identification."""
    try:
        repo = Repo(Path(codebase_path).resolve(), search_parent_directories=True)
    except InvalidGitRepositoryError:
        return 5.0, ["Not a git repository; skipping git health checks."]

    now = datetime.utcnow()

    # Map file -> commits last THRESHOLD_DAYS
    since_date = now - timedelta(days=THRESHOLD_DAYS)
    commits = list(repo.iter_commits(paths=codebase_path, since=since_date.isoformat()))

    file_counter: Counter[str] = Counter()
    author_counter: Counter[str] = Counter()

    for commit in commits:
        author_counter[commit.author.email] += 1
        for f in commit.stats.files.keys():
            if f.endswith(".py") and f.startswith(codebase_path):
                file_counter[f] += 1

    details: List[str] = []

    if not file_counter:
        return 8.0, ["Low churn detected in the last 6 months."]

    most_changed = file_counter.most_common(5)
    for f, n in most_changed:
        details.append(f"{f} changed {n} times in last 6 months.")

    avg_churn = sum(file_counter.values()) / len(file_counter)
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