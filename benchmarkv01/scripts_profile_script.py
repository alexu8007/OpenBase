"""
A tiny workload used by dynamic performance benchmarking.
It exercises CPU work, memory allocations, and a bit of I/O-like sleep to
produce measurable but quick signals for tools like pyinstrument and
memory_profiler.

Usage:
    BENCH_PROFILE_SCRIPT=benchmarkv01/scripts_profile_script.py python main.py ...
"""
from __future__ import annotations

import math
import random
import time
from typing import List

from benchmarkv01.db_access import (
    iter_posts_streaming,
    load_posts_with_authors_n_plus_one,
    load_posts_with_authors_prefetched,
)


def cpu_heavy(n: int = 50_000) -> float:
    total = 0.0
    for i in range(1, n):
        total += math.sin(i) * math.cos(i / 3.0)
    return total


def allocate_memory(num_lists: int = 50, list_size: int = 1_000) -> List[List[int]]:
    data: List[List[int]] = []
    for _ in range(num_lists):
        data.append([random.randint(0, 1000) for _ in range(list_size)])
    return data


def main() -> None:
    # CPU work
    _ = cpu_heavy()

    # Memory allocations
    data = allocate_memory()

    # Simulate N+1 and prefetched patterns
    _ = load_posts_with_authors_n_plus_one()
    _ = load_posts_with_authors_prefetched()

    # Simulate streaming iteration
    for _batch in iter_posts_streaming():
        pass

    # Simulate small I/O wait
    time.sleep(0.02)

    # Prevent data from being optimized away
    if sum(len(x) for x in data) < 0:
        print("unreachable")


if __name__ == "__main__":
    main()
