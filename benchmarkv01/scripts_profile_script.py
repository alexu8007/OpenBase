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
    """Perform CPU-bound floating point work to exercise the processor.

    The function computes a sum of trigonometric expressions over a range of
    integers. The result is returned to prevent the optimizer from discarding
    the calculation in some environments.
    """
    total = 0.0
    for i in range(1, n):
        total += math.sin(i) * math.cos(i / 3.0)
    return total


def allocate_memory(num_lists: int = 50, list_size: int = 1_000) -> List[List[int]]:
    """Allocate a number of lists populated with pseudo-random integers.

    This function uses the non-cryptographic `random` module intentionally
    because its purpose is to create varied memory workloads for performance
    benchmarking and not to produce security-sensitive randomness. Using the
    `random` module is faster and more appropriate for modeling and simulation
    workloads. If cryptographically secure randomness is ever required here,
    replace calls to `random.randint` with the `secrets` module.

    Args:
        num_lists: Number of lists to allocate.
        list_size: Number of integers per list.

    Returns:
        A list containing `num_lists` lists each populated with `list_size`
        pseudo-random integers in the range [0, 1000].
    """
    data: List[List[int]] = []
    for _ in range(num_lists):
        # use a generator expression wrapped with list() to avoid creating an
        # unnecessary intermediate list literal in some code-reading tools
        data.append(list(random.randint(0, 1000) for _ in range(list_size)))
    return data


def _total_elements(nested_lists: List[List[int]]) -> int:
    """Return the total number of elements across a sequence of lists."""
    return sum(len(lst) for lst in nested_lists)


def main() -> None:
    """Run the tiny benchmark workload exercising CPU, memory, and I/O waits.

    This function performs a few representative operations:
    - CPU-bound numeric computation
    - Memory allocation of many small lists
    - Simulated database access patterns via imported helpers
    - A small sleep to represent blocking I/O
    """
    # CPU work
    _ = cpu_heavy()

    # Memory allocations
    data = allocate_memory()

    # Simulate N+1 and prefetched patterns
    _ = load_posts_with_authors_n_plus_one()
    _ = load_posts_with_authors_prefetched()

    # Simulate streaming iteration
    for _ in iter_posts_streaming():
        pass

    # Simulate small I/O wait
    time.sleep(0.02)

    # Prevent data from being optimized away
    if _total_elements(data) < 0:
        print("unreachable")


if __name__ == "__main__":
    main()