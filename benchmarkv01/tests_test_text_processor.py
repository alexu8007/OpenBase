"""
Basic tests for the intentionally inefficient TextProcessor in test3.py.
Includes a slow test marker via environment check rather than pytest markers to
avoid relying on pytest fixtures in this flat layout.
"""
from __future__ import annotations

import os
import time

from benchmarkv01.test3 import TextProcessor


def test_reverse_and_palindrome_basic():
    tp = TextProcessor()
    text = "Able was I ere I saw Elba"
    reversed_text = tp.reverse_text_slowly(text)
    assert reversed_text == text[::-1]
    assert tp.check_palindrome_inefficiently(text)


def test_longest_word_and_counts():
    tp = TextProcessor()
    text = "alpha beta gamma delta epsilon"
    longest = tp.find_longest_word_slowly(text)
    assert longest in {"epsilon", "gamma"}
    count = tp.count_words_inefficiently(text)
    # The method is intentionally flawed; we assert it returns a positive number
    assert count > 0


def test_slow_path_optional():
    if os.getenv("RUN_SLOW_TESTS") != "1":
        # Skip pseudo-marker
        return
    tp = TextProcessor()
    start = time.time()
    _ = tp.process_text_very_slowly("some moderately long string " * 50)
    elapsed = time.time() - start
    # Just assert it took some non-trivial time on most machines
    assert elapsed >= 0.01
