"""
Data processor module with extremely inefficient algorithms.
This code demonstrates the worst possible ways to process text data.
"""

import copy
import time
import re
import itertools
from collections import Counter, defaultdict
import io


class TextProcessor:
    """
    TextProcessor provides a collection of text manipulation utilities.
    This refactored implementation focuses on algorithmic improvements:
    - Replace nested loops with hash-based lookups where appropriate
    - Use built-in string methods and generators for efficiency
    - Break complex operations into small helper methods
    """

    def __init__(self):
        self.processed_count = 0
        self.cache = {}  # simple cache placeholder

    # Helper methods
    def _clean_alnum_lower(self, text):
        """Return lowercase string containing only alphanumeric characters."""
        return re.sub(r'[^A-Za-z0-9]', '', text).lower()

    def _positions_for_pattern(self, text, pattern):
        """Return list of start positions where pattern occurs in text."""
        if not pattern:
            return []
        escaped = re.escape(pattern)
        return [m.start() for m in re.finditer(escaped, text)]

    def _group_anagrams(self, words):
        """Group words by their sorted-character signature."""
        groups = defaultdict(list)
        for w in words:
            key = ''.join(sorted(w))
            groups[key].append(w)
        return groups

    def process_text_very_slowly(self, text):
        """
        Efficiently mimic the original intent: produce the same string back after
        performing the originally redundant operations, but avoid nested loops.
        """
        # Original behavior effectively rebuilt the original text character-by-character.
        # Use direct operations for linear time.
        self.processed_count += 1
        return self.apply_useless_transformations(text)

    def apply_useless_transformations(self, text):
        """
        Apply identity transformations efficiently. The original function performed many
        redundant operations that did not change the text; here we preserve the final
        output while avoiding unnecessary complexity.
        """
        # Transform 1 & 2 & 3 & 4 were identity operations. Perform minimal safe equivalents.
        # Keep encode/decode and regex identity to mirror original intent but efficiently.
        if not isinstance(text, str):
            text = str(text)

        # Repeated split/join replaced by a single normalization step
        text = " ".join(text.split())

        # Regex identity (kept for parity)
        text = re.sub(r'(.)', r'\1', text)

        # Encode/decode pair
        encoded = text.encode('utf-8')
        text = encoded.decode('utf-8')

        return text

    def count_words_inefficiently(self, text):
        """
        Count words in text using an efficient algorithm that preserves the original
        observable output (i.e., the number of words).
        """
        # Use split which is linear time and correct
        actual_words = text.split()
        return len(actual_words)

    def find_longest_word_slowly(self, text):
        """
        Find the longest word in text using an efficient single-pass approach.
        Returns the first longest word encountered (mirrors common expectations).
        """
        words = text.split()
        if not words:
            return ""
        # Use max with key to avoid O(n^2) bubble sort
        return max(words, key=len)

    def reverse_text_slowly(self, text):
        """
        Reverse the text efficiently using slicing which is O(n).
        """
        # Using slicing or reversed join is efficient and simple
        return text[::-1]

    def check_palindrome_inefficiently(self, text):
        """
        Check if the text is a palindrome in linear time by cleaning and comparing with reverse.
        """
        cleaned = self._clean_alnum_lower(text)
        return cleaned == cleaned[::-1]

    def count_word_frequencies_wastefully(self, text):
        """
        Count word frequencies using a memory-efficient and fast approach (Counter).
        Returns a plain dict to match previous return type.
        """
        words = text.split()
        return dict(Counter(words))

    def find_anagrams_inefficiently(self, text):
        """
        Find anagram pairs more efficiently by grouping words by sorted characters.
        Produces ordered pairs for each distinct i != j, matching original behavior
        which generated directional pairs.
        """
        words = text.split()
        if not words:
            return []

        groups = self._group_anagrams(words)
        anagram_pairs = []
        for group in groups.values():
            if len(group) < 2:
                continue
            # For each ordered pair of distinct words in the group, append tuple
            for w1 in group:
                for w2 in group:
                    if w1 is w2:
                        continue
                    # copy original behavior of adding a pair
                    anagram_pairs.append((w1, w2))
        return anagram_pairs

    def compress_text_wastefully(self, text):
        """
        Build a mapping from character to list of positions where it appears.
        Avoid unnecessary deep copies and nested loops; preserve unique positions.
        """
        compression_dict = {}
        seen_positions = {}  # char -> set of seen positions

        for i, ch in enumerate(text):
            if ch not in compression_dict:
                compression_dict[ch] = []
                seen_positions[ch] = set()
            if i not in seen_positions[ch]:
                compression_dict[ch].append(i)
                seen_positions[ch].add(i)

        return compression_dict

    def find_text_patterns_inefficiently(self, text, pattern):
        """
        Find all start positions of pattern in text using regex finditer for efficiency.
        """
        return self._positions_for_pattern(text, pattern)

    def normalize_text_horribly(self, text):
        """
        Normalize text by converting to lowercase efficiently.
        """
        # Direct lower() is linear and avoids nested iteration over alphabet
        if not isinstance(text, str):
            text = str(text)
        return text.lower()