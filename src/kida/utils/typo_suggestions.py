"""Typo suggestion utilities for Kida error messages.

Provides suggest_closest() for "Did you mean?" hints when a name is not found
but a similar name exists. Used by compiler (filters, tests), loaders
(template names), and runtime (UndefinedError).
"""

from __future__ import annotations

from difflib import get_close_matches
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def suggest_closest(
    name: str,
    candidates: Iterable[str],
    *,
    limit: int = 3,
    cutoff: float = 0.6,
) -> list[str]:
    """Return closest matching names for typo suggestions.

    Uses difflib.get_close_matches with configurable cutoff.
    Returns up to `limit` matches, or empty list if none close enough.

    Args:
        name: The unknown name (e.g. filter name, variable name)
        candidates: Valid names to match against (e.g. env._filters.keys())
        limit: Max number of suggestions to return
        cutoff: Similarity threshold (0.0-1.0). 0.6 is reasonable for typos.

    Returns:
        List of closest matches, best first. Empty if no close match.

    Example:
        >>> suggest_closest("lenght", ["length", "upper", "lower"])
        ['length']
    """
    if not candidates:
        return []
    matches = get_close_matches(name, list(candidates), n=limit, cutoff=cutoff)
    return matches
