"""Collection and sequence filters for Kida templates."""

from __future__ import annotations

from collections import deque
from itertools import groupby, islice
from typing import Any

# Sort key tuple constants for clarity
SORT_KEY_NONE = (1, 0, 0)  # None/empty values sort last


def _make_sort_key_numeric(value: int | float) -> tuple[int, int, int | float]:
    """Create sort key for numeric value."""
    return (0, 0, value)


def _make_sort_key_string(value: str) -> tuple[int, int, str]:
    """Create sort key for string value."""
    return (0, 1, value)


def _filter_attr(value: Any, name: str) -> Any:
    """Get attribute from object or dictionary key.

    Returns "" for None/missing values (None-resilient, like Hugo).

    """
    if value is None:
        return ""
    # Try dictionary access first (for dict items)
    if isinstance(value, dict):
        val = value.get(name)
        return "" if val is None else val
    # Then try attribute access (for objects)
    try:
        val = getattr(value, name, None)
        return "" if val is None else val
    except AttributeError, TypeError:
        return ""


def _filter_first(value: Any) -> Any:
    """Return first item of sequence."""
    if value is None:
        return None
    try:
        return next(iter(value), None)
    except TypeError, ValueError:
        return None


def _filter_last(value: Any) -> Any:
    """Return last item of sequence.

    Uses deque(maxlen=1) for O(1) space on iterators; avoids materializing
    entire sequence.
    """
    if value is None:
        return None
    try:
        it = iter(value)
        dq = deque(it, maxlen=1)
        return dq[0] if dq else None
    except TypeError, ValueError:
        return None


def _filter_length(value: Any) -> int:
    """Return length of sequence."""
    if value is None:
        return 0
    try:
        return len(value)
    except TypeError, ValueError:
        return 0


def _filter_join(value: Any, separator: str = "") -> str:
    """Join sequence with separator."""
    if value is None:
        return ""
    try:
        return separator.join(str(x) for x in value)
    except TypeError, ValueError:
        return str(value)


def _filter_reverse(value: Any) -> list[Any] | str:
    """Reverse sequence."""
    try:
        return list(reversed(value))
    except TypeError:
        return str(value)[::-1]


def _filter_batch(value: Any, linecount: int, fill_with: Any = None) -> list[list[Any]]:
    """Batch items into groups of linecount."""
    result: list[list[Any]] = []
    batch: list[Any] = []
    for item in value:
        batch.append(item)
        if len(batch) >= linecount:
            result.append(batch)
            batch = []
    if batch:
        if fill_with is not None:
            while len(batch) < linecount:
                batch.append(fill_with)
        result.append(batch)
    return result


def _filter_slice(value: Any, slices: int, fill_with: Any = None) -> list[list[Any]]:
    """Slice items into number of groups."""
    result: list[list[Any]] = [[] for _ in range(slices)]
    for idx, item in enumerate(value):
        result[idx % slices].append(item)
    return result


def _filter_take(value: Any, count: int) -> list[Any]:
    """Take the first N items from a sequence.

    Kida-native filter for readable pipeline operations.

    Example:
        {{ items |> take(5) }}
        {{ posts |> sort(attribute='date', reverse=true) |> take(3) }}

    Args:
        value: Sequence to take from
        count: Number of items to take

    Returns:
        List of first N items (or fewer if sequence is shorter)

    """
    if value is None:
        return []
    try:
        return list(islice(value, count))
    except TypeError, ValueError:
        return []


def _filter_skip(value: Any, count: int) -> list[Any]:
    """Skip the first N items from a sequence.

    Kida-native filter for readable pipeline operations.

    Example:
        {{ items |> skip(5) }}
        {{ posts |> skip(10) |> take(10) }}  # pagination

    Args:
        value: Sequence to skip from
        count: Number of items to skip

    Returns:
        List of remaining items after skipping N

    """
    if value is None:
        return []
    try:
        return list(islice(value, count, None))
    except TypeError, ValueError:
        return []


def _filter_compact(value: Any, *, truthy: bool = True) -> list[Any]:
    """Remove None values (and optionally all falsy values) from a sequence.

    Enables declarative list building with conditional items, replacing
    imperative {% do %} patterns.

    Example:
        {# Declarative conditional list building #}
        {% let badges = [
                'async' if member.is_async,
                'deprecated' if member.is_deprecated,
                'abstract' if member.is_abstract,
        ] | compact %}

        {# Remove only None (keep empty strings, 0, False) #}
        {{ [0, None, '', False, 'value'] | compact(truthy=false) }}
        → [0, '', False, 'value']

        {# Remove all falsy values (default) #}
        {{ [0, None, '', False, 'value'] | compact }}
        → ['value']

    Args:
        value: Sequence to compact
        truthy: If True (default), remove all falsy values.
                If False, remove only None values.

    Returns:
        List with None/falsy values removed.

    """
    if value is None:
        return []
    try:
        if truthy:
            return [v for v in value if v]
        else:
            return [v for v in value if v is not None]
    except TypeError, ValueError:
        return []


def _filter_map(
    value: Any,
    *args: Any,
    attribute: str | None = None,
) -> list[Any]:
    """Map an attribute or method from a sequence."""
    if value is None:
        return []
    try:
        if attribute:
            return [_filter_attr(item, attribute) for item in value]
        if args:
            method_name = args[0]
            return [getattr(item, method_name)() for item in value]
        return list(value)
    except TypeError, ValueError:
        return []


def _filter_selectattr(value: Any, attr: str, *args: Any) -> list[Any]:
    """Select items where attribute passes test."""
    from kida.environment.tests import _apply_test

    result = []
    for item in value:
        val = getattr(item, attr, None)
        if args:
            test_name = args[0]
            test_args = args[1:] if len(args) > 1 else ()
            if _apply_test(val, test_name, *test_args):
                result.append(item)
        elif val:
            result.append(item)
    return result


def _filter_rejectattr(value: Any, attr: str, *args: Any) -> list[Any]:
    """Reject items where attribute passes test."""
    from kida.environment.tests import _apply_test

    result = []
    for item in value:
        val = getattr(item, attr, None)
        if args:
            test_name = args[0]
            test_args = args[1:] if len(args) > 1 else ()
            if not _apply_test(val, test_name, *test_args):
                result.append(item)
        elif not val:
            result.append(item)
    return result


def _filter_select(value: Any, test_name: str | None = None, *args: Any) -> list[Any]:
    """Select items that pass a test."""
    from kida.environment.tests import _apply_test

    if test_name is None:
        return [item for item in value if item]
    return [item for item in value if _apply_test(item, test_name, *args)]


def _filter_reject(value: Any, test_name: str | None = None, *args: Any) -> list[Any]:
    """Reject items that pass a test."""
    from kida.environment.tests import _apply_test

    if test_name is None:
        return [item for item in value if not item]
    return [item for item in value if not _apply_test(item, test_name, *args)]


def _filter_groupby(value: Any, attribute: str) -> list[dict[str, Any]]:
    """Group items by attribute with None-safe sorting.

    Items with None/empty values for the attribute are grouped together
    and sorted last.

    """

    def get_key(item: Any) -> Any:
        # Support dict-style access for dict items
        if isinstance(item, dict):
            return item.get(attribute)
        return getattr(item, attribute, None)

    def sort_key(item: Any) -> tuple[Any, ...]:
        """None-safe sort key: (is_none, value_for_comparison)."""
        val = get_key(item)
        if val is None or val == "":
            # None/empty sorts last, use empty string for grouping key stability
            return (1, "")
        if isinstance(val, (int, float)):
            return (0, val)
        # Convert to string for consistent comparison
        return (0, str(val).lower())

    sorted_items = sorted(value, key=sort_key)
    return [
        {"grouper": key, "list": list(group)} for key, group in groupby(sorted_items, key=get_key)
    ]


def _filter_sort(
    value: Any,
    reverse: bool = False,
    case_sensitive: bool = False,
    attribute: str | None = None,
) -> list[Any]:
    """Sort sequence with improved error handling for None values.

    When sorting fails due to None comparisons, provides detailed error
    showing which items have None values for the sort attribute.

    """
    from kida.environment.exceptions import NoneComparisonError

    if not value:
        return []

    items = list(value)

    # Handle multi-attribute sorting (e.g., "weight,title")
    attributes = attribute.split(",") if attribute else []

    def key_func(item: Any) -> tuple[Any, ...]:
        """Generate sort key with None-safe handling.

        Strategy: Use (is_none, sort_value) tuples where:
        - is_none=0 for real values (sort first)
        - is_none=1 for None/empty values (sort last)
        - sort_value is normalized for consistent comparison

        With None-resilient handling, both None and "" are treated as missing.
        """
        if not attributes:
            val = item
            if val is None or val == "":
                return SORT_KEY_NONE  # None/empty sorts last
            if isinstance(val, (int, float)):
                return _make_sort_key_numeric(val)  # Numbers
            val_str = str(val)
            if not case_sensitive:
                val_str = val_str.lower()
            return _make_sort_key_string(val_str)  # Strings

        # Build tuple of values for multi-attribute sort
        values: list[tuple[int, int, int | float | str]] = []
        for attr in attributes:
            attr = attr.strip()
            val = _filter_attr(item, attr)

            # Defensive: Handle None and "" (None-resilient) first
            if val is None or val == "":
                # None/empty always sorts last
                values.append(SORT_KEY_NONE)
            elif isinstance(val, (int, float)):
                # Numbers: type 0 means numeric
                values.append(_make_sort_key_numeric(val))
            else:
                # Everything else as string: type 1 means string
                # Convert to string safely (handles edge cases)
                try:
                    val_str = str(val)
                    if not case_sensitive:
                        val_str = val_str.lower()
                    values.append(_make_sort_key_string(val_str))
                except TypeError, ValueError:
                    # Fallback for unstringable values (shouldn't happen, but be defensive)
                    values.append((1, 0, ""))

        return tuple(values)

    try:
        return sorted(items, reverse=reverse, key=key_func)
    except TypeError as e:
        # Provide detailed error about which items have None/empty values
        error_str = str(e)
        if "NoneType" in error_str or "not supported between" in error_str:
            # Find items with None/empty values for the attribute(s)
            none_items = []
            for idx, item in enumerate(items):
                if attributes:
                    for attr in attributes:
                        attr = attr.strip()
                        val = _filter_attr(item, attr)
                        if val is None or val == "":
                            # Get a representative label for the item
                            item_label = (
                                getattr(item, "title", None)
                                or getattr(item, "name", None)
                                or f"item[{idx}]"
                            )
                            none_items.append(f"  - {item_label}: {attr} = None/empty")
                            break
                else:
                    if item is None or item == "":
                        none_items.append(f"  - item[{idx}] = None/empty")

            attr_str = attribute or "value"
            error_msg = f"Sort failed: cannot compare None values when sorting by '{attr_str}'"
            if none_items:
                error_msg += "\n\nItems with None/empty values:\n" + "\n".join(none_items[:10])
                if len(none_items) > 10:
                    error_msg += f"\n  ... and {len(none_items) - 10} more"
            error_msg += "\n\nSuggestion: Use | default(fallback) on the attribute, or filter out None values first"

            raise NoneComparisonError(
                None,
                None,
                attribute=attribute,
                expression=f"| sort(attribute='{attribute}')" if attribute else "| sort",
            ) from e
        raise


def _filter_unique(
    value: Any, case_sensitive: bool = False, attribute: str | None = None
) -> list[Any]:
    """Return unique items."""
    seen: set[Any] = set()
    result = []
    for item in value:
        val = getattr(item, attribute, None) if attribute else item
        if not case_sensitive and isinstance(val, str):
            val = val.lower()
        if val not in seen:
            seen.add(val)
            result.append(item)
    return result


def _filter_dictsort(
    value: dict[str, Any],
    case_sensitive: bool = False,
    by: str = "key",
    reverse: bool = False,
) -> list[tuple[str, Any]]:
    """Sort a dict and return list of (key, value) pairs."""
    if by == "value":

        def sort_key(item: tuple[str, Any]) -> Any:
            val = item[1]
            if not case_sensitive and isinstance(val, str):
                return val.lower()
            return val

    else:

        def sort_key(item: tuple[str, Any]) -> Any:
            val = item[0]
            if not case_sensitive and isinstance(val, str):
                return val.lower()
            return val

    return sorted(value.items(), key=sort_key, reverse=reverse)
