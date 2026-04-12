"""Debug filters for Kida templates."""

from __future__ import annotations

import sys
from pprint import pformat
from typing import Any


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
                return f"{type_name}(title={title!r}, weight={weight})"
            return f"{type_name}(title={title!r})"

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
    label_str = f"[{label}]" if label else ""

    # Build output
    lines = []

    if value is None:
        lines.append(f"DEBUG {label_str}: None")
    elif isinstance(value, (list, tuple)):
        lines.append(f"DEBUG {label_str}: <{type_name}[{len(value)}]>")
        for idx, item in enumerate(value[:max_items]):
            item_repr = _debug_repr(item)
            # Flag None values prominently
            none_warning = ""
            if hasattr(item, "__dict__"):
                none_attrs = [
                    k for k, v in vars(item).items() if v is None and not k.startswith("_")
                ]
                if none_attrs:
                    none_warning = f"  <-- None: {', '.join(none_attrs[:3])}"
            lines.append(f"  [{idx}] {item_repr}{none_warning}")
        if len(value) > max_items:
            lines.append(f"  ... ({len(value) - max_items} more items)")
    elif isinstance(value, dict):
        lines.append(f"DEBUG {label_str}: <{type_name}[{len(value)} keys]>")
        for k, v in list(value.items())[:max_items]:
            v_repr = _debug_repr(v)
            none_warning = " <-- None!" if v is None else ""
            lines.append(f"  {k!r}: {v_repr}{none_warning}")
        if len(value) > max_items:
            lines.append(f"  ... ({len(value) - max_items} more keys)")
    elif hasattr(value, "__dict__"):
        # Object with attributes
        attrs = {k: v for k, v in vars(value).items() if not k.startswith("_")}
        lines.append(f"DEBUG {label_str}: <{type_name}>")
        for k, v in list(attrs.items())[:max_items]:
            v_repr = _debug_repr(v)
            none_warning = " <-- None!" if v is None else ""
            lines.append(f"  .{k} = {v_repr}{none_warning}")
        if len(attrs) > max_items:
            lines.append(f"  ... ({len(attrs) - max_items} more attributes)")
    else:
        lines.append(f"DEBUG {label_str}: {_debug_repr(value)} ({type_name})")

    # Print to stderr
    print("\n".join(lines), file=sys.stderr)

    # Return value unchanged for chaining
    return value


def _filter_pprint(value: Any) -> str:
    """Pretty-print a value."""
    return pformat(value)
