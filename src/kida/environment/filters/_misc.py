"""Miscellaneous filters for Kida templates."""

from __future__ import annotations

import random as random_module
from datetime import datetime
from typing import Any
from urllib.parse import quote


def _filter_get(value: Any, key: str, default: Any = None) -> Any:
    """Safe dictionary/object access that avoids Python method name conflicts.

    When accessing dict keys like 'items', 'keys', 'values', or 'get', using
    dotted access (e.g., ``schema.items``) returns the method, not the key value.
    This filter provides clean syntax for safe key access.

    Examples:
        {{ user | get('name') }}              # Get 'name' key
        {{ config | get('timeout', 30) }}     # With default value
        {{ schema | get('items') }}           # Safe access to 'items' key
        {{ data | get('keys') }}             # Safe access to 'keys' key

    Args:
        value: Dict, object, or None to access
        key: Key or attribute name to access
        default: Value to return if key doesn't exist (default: None)

    Returns:
        value[key] if exists, else default

    Note:
        This avoids conflicts with Python's built-in dict method names
        (items, keys, values, get) that would otherwise shadow key access.

    """
    if value is None:
        return default

    # Dict access (handles method name conflicts)
    if isinstance(value, dict):
        return value.get(key, default)

    # Object attribute access
    return getattr(value, key, default)


def _filter_date(value: Any, format: str = "%Y-%m-%d") -> str:
    """Format datetime, date, or epoch timestamp with strftime.

    Example:
        {{ dt | date }} → "2025-02-13"
        {{ dt | date("%b %d, %Y") }} → "Feb 13, 2025"
        {{ none | date }} → ""
    """
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime(format)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).strftime(format)
    return ""


def _filter_urlencode(value: str) -> str:
    """URL-encode a string."""
    return quote(str(value), safe="")


def _filter_random(value: Any) -> Any:
    """Return a random item from the sequence.

    Warning: This filter is impure (non-deterministic).

    Args:
        value: A sequence to pick from.

    Returns:
        A random element from the sequence.

    """
    seq = list(value)
    if not seq:
        return None
    return random_module.choice(seq)


def _filter_shuffle(value: Any) -> list[Any]:
    """Return a shuffled copy of the sequence.

    Warning: This filter is impure (non-deterministic).

    Args:
        value: A sequence to shuffle.

    Returns:
        A new list with elements in random order.

    """
    result = list(value)
    random_module.shuffle(result)
    return result


def _filter_classes(value: Any) -> str:
    """Join a list of CSS class names, dropping falsy values.

    Simplifies conditional class building in templates:

    Example:
        {{ ['card', 'active' if is_active, 'done' if todo.done] | classes }}
        → "card active"   (when is_active=True, todo.done=False)

    Handles:
    - None values (dropped)
    - Empty strings (dropped)
    - False / 0 (dropped)
    - Nested lists (flattened one level)

    """
    if value is None:
        return ""
    parts: list[str] = []
    try:
        items = list(value)
    except TypeError:
        return str(value)
    for item in items:
        if isinstance(item, (list, tuple)):
            parts.extend(str(sub) for sub in item if sub)
        elif item:
            parts.append(str(item))
    return " ".join(parts)
