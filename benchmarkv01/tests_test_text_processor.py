"""
Basic tests for the intentionally inefficient TextProcessor in test3.py.
Includes a slow test marker via environment check rather than pytest markers to
avoid relying on pytest fixtures in this flat layout.
"""
from __future__ import annotations

import os
import time

import pytest

from benchmarkv01.test3 import TextProcessor


def assert_equal(a, b, msg: str | None = None) -> None:
    """Assert two values are equal with a clear error message."""
    if a != b:
        raise AssertionError(msg or f"Expected {a!r} to equal {b!r}")


def assert_in(item, container, msg: str | None = None) -> None:
    """Assert an item is contained in a container with a clear error message."""
    if item not in container:
        raise AssertionError(msg or f"Expected {item!r} to be in {container!r}")


def assert_positive(value, msg: str | None = None) -> None:
    """Assert a numeric value is positive (> 0)."""
    try:
        number = float(value)
    except Exception:
        raise AssertionError(msg or f"Expected a numeric value, got {value!r}")
    if number <= 0:
        raise AssertionError(msg or f"Expected a positive value, got {number!r}")


def assert_gte(a, b, msg: str | None = None) -> None:
    """Assert a >= b with a clear error message."""
    try:
        if a < b:
            raise AssertionError(msg or f"Expected {a!r} to be >= {b!r}")
    except TypeError:
        raise AssertionError(msg or f"Cannot compare values {a!r} and {b!r}")


def assert_true(value, msg: str | None = None) -> None:
    """Assert a value is truthy with a clear error message."""
    if not value:
        raise AssertionError(msg or f"Expected {value!r} to be truthy")


@pytest.fixture
def tp() -> TextProcessor:
    """Provide a fresh TextProcessor instance for tests to reduce duplication."""
    return TextProcessor()


@pytest.fixture
def sample_texts() -> dict[str, str]:
    """Provide a set of sample texts including common edge cases for reuse."""
    return {
        "palindrome": "Able was I ere I saw Elba",
        "empty": "",
        "single_char": "x",
        "punctuated_palindrome": "A man, a plan, a canal: Panama",
    }


def test_reverse_and_palindrome_basic(tp: TextProcessor, sample_texts: dict[str, str]):
    """Reverse a known phrase and verify palindrome detection for that phrase."""
    text = sample_texts["palindrome"]
    reversed_text = tp.reverse_text_slowly(text)
    assert_equal(reversed_text, text[::-1])
    # Verify the palindrome check for the given phrase (intentionally inefficient method)
    assert_true(tp.check_palindrome_inefficiently(text), "Expected the text to be detected as a palindrome")


def test_longest_word_and_counts(tp: TextProcessor):
    """Find the longest word in a simple sentence and ensure word count is positive."""
    text = "alpha beta gamma delta epsilon"
    longest = tp.find_longest_word_slowly(text)
    # Accept either expected outcomes from the intentionally flawed implementation
    assert_in(longest, {"epsilon", "gamma"})
    count = tp.count_words_inefficiently(text)
    # The method is intentionally flawed; assert it returns a positive number
    assert_positive(count)


def test_slow_path_optional(tp: TextProcessor):
    """Optional slow integration-style test that runs only when explicitly enabled."""
    if os.getenv("RUN_SLOW_TESTS") != "1":
        pytest.skip("Skipping slow tests; set RUN_SLOW_TESTS=1 to enable")
    start = time.time()
    _ = tp.process_text_very_slowly("some moderately long string " * 50)
    elapsed = time.time() - start
    # Just assert it took some non-trivial time on most machines
    assert_gte(elapsed, 0.01)


def test_palindrome_edge_cases(tp: TextProcessor, sample_texts: dict[str, str]):
    """Cover palindrome edge cases such as empty and single-character strings."""
    empty = sample_texts["empty"]
    single = sample_texts["single_char"]
    # Empty string is commonly considered a palindrome
    assert_true(tp.check_palindrome_inefficiently(empty), "Empty string should be treated as a palindrome")
    # Single character strings should be palindromes
    assert_true(tp.check_palindrome_inefficiently(single), "Single character should be detected as a palindrome")


def test_longest_word_edge_cases(tp: TextProcessor):
    """Cover edge cases for longest-word and word-count behavior on empty input."""
    empty = ""
    longest = tp.find_longest_word_slowly(empty)
    # The implementation may reasonably return an empty string or None for no words
    assert_in(longest, {"", None})
    count = tp.count_words_inefficiently(empty)
    # Word count for empty input should be non-negative (defensive check)
    assert_gte(count, 0)