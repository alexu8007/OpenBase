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
from typing import Iterator, List

from benchmarkv01.db_access import (
    iter_posts_streaming,
    load_posts_with_authors_n_plus_one,
    load_posts_with_authors_prefetched,
)


def cpu_heavy(n: int = 50_000) -> float:
    """Perform CPU-bound mathematical work and return the accumulated result.

    This function iterates over a range of values and computes a trigonometric
    expression for each value to generate a measurable CPU workload.
    """
    accumulated_total = 0.0
    for value in range(1, n):
        accumulated_total += math.sin(value) * math.cos(value / 3.0)
    return accumulated_total


def allocate_memory(num_lists: int = 50, list_size: int = 1_000) -> Iterator[List[int]]:
    """Yield lists of random integers to simulate memory allocations.

    Yields one list at a time to avoid constructing all lists in memory at once,
    which helps when profiling or working with larger datasets.
    """
    for list_index in range(num_lists):
        yield [random.randint(0, 1000) for _ in range(list_size)]


def main() -> None:
    """Run a small benchmark workload exercising CPU, memory, and I/O-like waits."""
    # CPU work
    _ = cpu_heavy()

    # Memory allocations (streamed)
    data = allocate_memory()

    # Simulate N+1 and prefetched patterns
    _ = load_posts_with_authors_n_plus_one()
    _ = load_posts_with_authors_prefetched()

    # Simulate streaming iteration
    for batch in iter_posts_streaming():
        pass

    # Simulate small I/O wait
    time.sleep(0.02)

    # Prevent data from being optimized away
    if sum(len(x) for x in data) < 0:
        print("unreachable")


if __name__ == "__main__":
    main()