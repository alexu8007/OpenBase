"""Module B participating in an intentional circular import with module A.
Designed for coupling/cycle detection benchmarks.
"""
from __future__ import annotations

import typing as _t
from dataclasses import dataclass

# Intentional circular import
import benchmarkv01.cycle_a as cycle_a  # type: ignore


def b_to_a_decrement_until_zero(value: int) -> int:
    """Calls into A until value reaches zero, then returns 0."""
    if value <= 0:
        return 0
    # Reference to function in cycle_a is resolved at call time
    return cycle_a.a_to_b_decrement_until_zero(value - 1)


def identity_from_b(value: _t.Any) -> _t.Any:
    return value


@dataclass
class BThing:
    """Data class referencing A by string type to avoid import-time evaluation."""

    name: str
    related: "cycle_a.AThing | None" = None


def create_linked_things(name_b: str, name_a: str) -> BThing:
    b = BThing(name=name_b)
    a = cycle_a.AThing(name=name_a, related=None)
    b.related = a
    a.related = b
    return b
