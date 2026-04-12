"""Debug filters for Kida templates."""

from __future__ import annotations

import sys
from pprint import pformat
from typing import Any

from kida.tstring import plain as _plain


def _debug_repr(value: Any, max_len: int = 60) -> str:
    """Create a compact repr for debug output."""
    if value is None:
        return "None"

    type_name = type(value).__name__

    # Special handling for common types
    if hasattr(value, "title"):
        title = getattr(value, "title", None)
        weight = getattr(
            value,
            "weight",
            getattr(value, "metadata", {}).get("weight") if hasattr(value, "metadata") else None,
        )
        if title is not None:
            if weight is not None:
                return _plain(t"{type_name}(title={title!r}, weight={weight})")
            return _plain(t"{type_name}(title={title!r})")

    # Truncate long reprs
    r = repr(value)
    if len(r) > max_len:
        return r[: max_len - 3] + "..."
    return r


def _filter_debug(value: Any, label: str | None = None, max_items: int = 5) -> Any:
    """Debug filter that prints variable info to stderr and returns the value unchanged.

    Usage:
        {{ posts | debug }}                    -> Shows type and length
        {{ posts | debug('my posts') }}        -> Shows with custom label
        {{ posts | debug(max_items=10) }}      -> Show more items

    Args:
        value: The value to inspect
        label: Optional label for the output
        max_items: Maximum number of items to show for sequences

    Returns:
        The value unchanged (for use in filter chains)

    Output example:
        DEBUG [my posts]: <list[5]>
          [0] Page(title='Getting Started', weight=10)
          [1] Page(title='Installation', weight=None)  <-- None!
              ...

    """
    type_name = type(value).__name__
    label_str = _plain(t"[{label}]") if label else ""

    # Build output
    lines: list[str] = []

    if value is None:
        lines.append(_plain(t"DEBUG {label_str}: None"))
    elif isinstance(value, (list, tuple)):
        lines.append(_plain(t"DEBUG {label_str}: <{type_name}[{len(value)}]>"))
        for idx, item in enumerate(value[:max_items]):
            item_repr = _debug_repr(item)
            # Flag None values prominently
            none_warning = ""
            if hasattr(item, "__dict__"):
                none_attrs = [
                    attr
                    for attr, val in vars(item).items()
                    if val is None and not attr.startswith("_")
                ]
                if none_attrs:
                    joined = ", ".join(none_attrs[:3])
                    none_warning = _plain(t"  <-- None: {joined}")
            lines.append(_plain(t"  [{idx}] {item_repr}{none_warning}"))
        if len(value) > max_items:
            remaining = len(value) - max_items
            lines.append(_plain(t"  ... ({remaining} more items)"))
    elif isinstance(value, dict):
        lines.append(_plain(t"DEBUG {label_str}: <{type_name}[{len(value)} keys]>"))
        for key, val in list(value.items())[:max_items]:
            v_repr = _debug_repr(val)
            none_warning = " <-- None!" if val is None else ""
            lines.append(_plain(t"  {key!r}: {v_repr}{none_warning}"))
        if len(value) > max_items:
            remaining = len(value) - max_items
            lines.append(_plain(t"  ... ({remaining} more keys)"))
    elif hasattr(value, "__dict__"):
        # Object with attributes
        attrs = {attr: val for attr, val in vars(value).items() if not attr.startswith("_")}
        lines.append(_plain(t"DEBUG {label_str}: <{type_name}>"))
        for attr, val in list(attrs.items())[:max_items]:
            v_repr = _debug_repr(val)
            none_warning = " <-- None!" if val is None else ""
            lines.append(_plain(t"  .{attr} = {v_repr}{none_warning}"))
        if len(attrs) > max_items:
            remaining = len(attrs) - max_items
            lines.append(_plain(t"  ... ({remaining} more attributes)"))
    else:
        debug_repr = _debug_repr(value)
        lines.append(_plain(t"DEBUG {label_str}: {debug_repr} ({type_name})"))

    # Print to stderr
    print("\n".join(lines), file=sys.stderr)

    # Return value unchanged for chaining
    return value


def _filter_pprint(value: Any) -> str:
    """Pretty-print a value."""
    return pformat(value)
