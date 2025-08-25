"""
Intentional N+1 query example and a batched alternative.
This file is used by scalability/architecture benchmarks to detect data-access smells.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from time import sleep
from typing import Dict, Iterable, Iterator, List, Optional


@dataclass(frozen=True)
class Author:
    id: int
    name: str


@dataclass(frozen=True)
class Post:
    id: int
    author_id: int
    title: str


# Tiny in-memory "database"
AUTHORS: Dict[int, Author] = {
    1: Author(id=1, name="Ada"),
    2: Author(id=2, name="Linus"),
    3: Author(id=3, name="Guido"),
}

POSTS: List[Post] = [
    Post(id=1, author_id=1, title="Turing complete thoughts"),
    Post(id=2, author_id=2, title="Kernel notes"),
    Post(id=3, author_id=3, title="On the benevolent dictator"),
    Post(id=4, author_id=1, title="Computation and you"),
]


def _validate_author_id(author_id: int) -> int:
    """Validate that author_id is an integer and return it.

    Raises:
        TypeError: if author_id is not an int.
    """
    if not isinstance(author_id, int):
        raise TypeError("author_id must be an int")
    return author_id


def _normalize_author_ids(author_ids: Iterable[int]) -> List[int]:
    """Validate and normalize an iterable of author IDs to a list of ints.

    Raises:
        TypeError: if any element in author_ids is not an int or author_ids is not iterable.
    """
    try:
        iterator = iter(author_ids)
    except TypeError:
        raise TypeError("author_ids must be an iterable of ints")
    validated: List[int] = []
    for aid in iterator:
        if not isinstance(aid, int):
            raise TypeError("author_ids must be an iterable of ints")
        validated.append(aid)
    return validated


def _batch_fetch_authors(author_ids: Iterable[int]) -> Dict[int, Author]:
    """Helper that consolidates batched author lookups and input validation."""
    normalized = _normalize_author_ids(author_ids)
    unique_ids = set(normalized)
    return {aid: AUTHORS[aid] for aid in unique_ids if aid in AUTHORS}


def get_all_posts() -> List[Post]:
    """Return a shallow copy of all posts.

    Keeping a copy prevents callers from mutating the module-level POSTS list.
    """
    return list(POSTS)


def get_author_by_id(author_id: int) -> Optional[Author]:
    """Simulate a per-row query to fetch an author by ID.

    Validates input type to catch developer errors early.
    """
    _validate_author_id(author_id)
    # Simulate a per-row query
    # Add a tiny delay to amplify the N+1 effect in runtime profiling
    sleep(0.001)
    return AUTHORS.get(author_id)


def get_authors_by_ids(author_ids: Iterable[int]) -> Dict[int, Author]:
    """Simulate a batched query returning a mapping of author_id -> Author.

    Accepts any iterable of ints and de-duplicates IDs internally.
    """
    return _batch_fetch_authors(author_ids)


def load_posts_with_authors_n_plus_one() -> List[Dict[str, object]]:
    """
    N+1 pattern: fetch posts, then fetch each author individually inside the loop.
    This function is intentionally inefficient for benchmark detection.
    """
    result: List[Dict[str, object]] = []
    for post in get_all_posts():
        author = get_author_by_id(post.author_id)  # N+1 per post
        result.append({"post": post, "author": author})
    return result


def _iter_posts_with_authors(posts: Iterable[Post], author_map: Dict[int, Author]) -> Iterator[Dict[str, object]]:
    """Stream posts joined with authors using a generator to avoid building intermediate large lists."""
    for p in posts:
        yield {"post": p, "author": author_map.get(p.author_id)}


def load_posts_with_authors_prefetched() -> List[Dict[str, object]]:
    """Optimized version using a batched author lookup.

    Uses a generator internally to stream the join. Returns a list to preserve the original public interface.
    """
    posts = get_all_posts()
    author_map = get_authors_by_ids(p.author_id for p in posts)
    return list(_iter_posts_with_authors(posts, author_map))


# Additional helpers to give benchmarks more signal

@lru_cache(maxsize=16)
def get_author_cached(author_id: int) -> Optional[Author]:
    """Cached variant that still calls the per-row getter (to test cache use).

    Input is validated to ensure consistent caching behavior.
    """
    _validate_author_id(author_id)
    return get_author_by_id(author_id)


def load_posts_with_cache() -> List[Dict[str, object]]:
    """N+1 shape but slightly mitigated by an LRU cache (still suboptimal)."""
    result: List[Dict[str, object]] = []
    for post in get_all_posts():
        author = get_author_cached(post.author_id)
        result.append({"post": post, "author": author})
    return result


def iter_posts_streaming(batch_size: int = 2) -> Iterator[List[Post]]:
    """Simulate streaming/batched DB access to exercise iterator patterns.

    This implementation avoids copying the entire posts list into a new list and
    yields batches incrementally, which is more memory-friendly for large datasets.
    """
    if not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    posts = get_all_posts()
    buffer: List[Post] = []
    for p in posts:
        buffer.append(p)
        if len(buffer) >= batch_size:
            yield list(buffer)
            buffer.clear()
    if buffer:
        yield list(buffer)