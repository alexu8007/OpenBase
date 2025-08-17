"""Module A participating in an intentional circular import with module B.
Designed for coupling/cycle detection benchmarks.
"""
from __future__ import annotations

import typing as _t
from dataclasses import dataclass

# Intentional circular import
import benchmarkv01.cycle_b as cycle_b  # type: ignore


def a_to_b_decrement_until_zero(value: int) -> int:
    """Calls into B until value reaches zero, then returns 0."""
    if value <= 0:
        return 0
    # Reference to function in cycle_b is resolved at call time
    return cycle_b.b_to_a_decrement_until_zero(value - 1)


def identity_from_a(value: _t.Any) -> _t.Any:
    return value


@dataclass
class AThing:
    """Data class referencing B by using a string type to avoid import-time NameError."""

    name: str
    related: "cycle_b.BThing | None" = None


def create_linked_things(name_a: str, name_b: str) -> AThing:
    """Create AThing and BThing that reference each other (mutual refs)."""
    a = AThing(name=name_a)
    b = cycle_b.BThing(name=name_b, related=None)
    a.related = b
    b.related = a
    return a
