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


def get_all_posts() -> List[Post]:
    return list(POSTS)


def get_author_by_id(author_id: int) -> Optional[Author]:
    # Simulate a per-row query
    # Add a tiny delay to amplify the N+1 effect in runtime profiling
    sleep(0.001)
    return AUTHORS.get(author_id)


def get_authors_by_ids(author_ids: Iterable[int]) -> Dict[int, Author]:
    # Simulate a batched query
    unique_ids = set(author_ids)
    return {aid: AUTHORS[aid] for aid in unique_ids if aid in AUTHORS}


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


def load_posts_with_authors_prefetched() -> List[Dict[str, object]]:
    """Optimized version using a batched author lookup."""
    posts = get_all_posts()
    author_map = get_authors_by_ids(p.author_id for p in posts)
    return [{"post": p, "author": author_map.get(p.author_id)} for p in posts]


# Additional helpers to give benchmarks more signal

@lru_cache(maxsize=16)
def get_author_cached(author_id: int) -> Optional[Author]:
    """Cached variant that still calls the per-row getter (to test cache use)."""
    return get_author_by_id(author_id)


def load_posts_with_cache() -> List[Dict[str, object]]:
    """N+1 shape but slightly mitigated by an LRU cache (still suboptimal)."""
    result: List[Dict[str, object]] = []
    for post in get_all_posts():
        author = get_author_cached(post.author_id)
        result.append({"post": post, "author": author})
    return result


def iter_posts_streaming(batch_size: int = 2) -> Iterator[List[Post]]:
    """Simulate streaming/batched DB access to exercise iterator patterns."""
    items = list(get_all_posts())
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]
