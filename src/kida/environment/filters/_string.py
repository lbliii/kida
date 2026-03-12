"""String manipulation filters for Kida templates."""

from __future__ import annotations

import re
import textwrap
from typing import Any


def _filter_capitalize(value: str) -> str:
    """Capitalize first character."""
    return str(value).capitalize()


def _filter_lower(value: str) -> str:
    """Convert to lowercase."""
    return str(value).lower()


def _filter_upper(value: str) -> str:
    """Convert to uppercase."""
    return str(value).upper()


def _filter_title(value: str) -> str:
    """Title case."""
    return str(value).title()


def _filter_trim(value: str, chars: str | None = None) -> str:
    """Strip whitespace or specified characters.

    Args:
        value: String to trim
        chars: Optional characters to strip (default: whitespace)

    """
    return str(value).strip(chars)


def _filter_replace(value: str, old: str, new: str, count: int | str | None = -1) -> str:
    """Replace occurrences."""
    if count is None or count == -1:
        replace_count = -1
    else:
        try:
            replace_count = int(count)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"replace count expects a number, got {type(count).__name__}: {count!r}. "
                "Use | int on the count value."
            ) from e
    return str(value).replace(old, new, replace_count if replace_count > 0 else -1)


def _filter_truncate(
    value: str,
    length: int = 255,
    killwords: bool = False,
    end: str = "...",
    leeway: int | None = None,
) -> str:
    """Truncate string to specified length.

    Args:
        value: String to truncate
        length: Maximum length including end marker
        killwords: If False (default), truncate at word boundary; if True, cut mid-word
        end: String to append when truncated (default: "...")
        leeway: Allow slightly longer strings before truncating (Jinja2 compat, ignored)

    Returns:
        Truncated string with end marker if truncated

    """
    value = str(value)
    if len(value) <= length:
        return value

    # Calculate available space for content
    available = length - len(end)
    if available <= 0:
        return end[:length] if length > 0 else ""

    if killwords:
        # Cut mid-word
        return value[:available] + end
    else:
        # Try to break at word boundary
        truncated = value[:available]
        # Find last space
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
        return truncated.rstrip() + end


def _filter_center(value: str, width: int = 80) -> str:
    """Center string in width."""
    return str(value).center(width)


def _filter_indent(value: str, width: int = 4, first: bool = False) -> str:
    """Indent text lines."""
    lines = str(value).splitlines(True)
    indent = " " * width
    if not first:
        return lines[0] + "".join(indent + line for line in lines[1:])
    return "".join(indent + line for line in lines)


def _filter_wordwrap(value: str, width: int = 79, break_long_words: bool = True) -> str:
    """Wrap text at width."""
    return textwrap.fill(str(value), width=width, break_long_words=break_long_words)


# Pattern for %-style format specs (e.g. %.2f, %s, %5d) — avoids false positive on "50%"
_PERCENT_FORMAT_SPEC = re.compile(r"%\d*\.?\d*[sdfioxXeEgGcrs]")


def _filter_format(value: str, *args: Any, **kwargs: Any) -> str:
    """Format string with args/kwargs. Uses str.format() — {} placeholders, not %."""
    s = str(value)
    has_args = bool(args or kwargs)
    has_placeholders = "{" in s
    # Detect %-style format string passed to format filter — Python silently ignores
    if has_args and not has_placeholders and _PERCENT_FORMAT_SPEC.search(s):
        raise ValueError(
            "format filter uses str.format() with {} placeholders, not %. "
            "For numeric formatting use format_number (e.g. x | format_number(2)) "
            'or {:.2f}-style: {{ "{:.2f}" | format(x) }}.'
        )
    return s.format(*args, **kwargs)


def _filter_slug(value: Any) -> str:
    """Convert text to URL-safe slug (lowercase, hyphens, ASCII-only).

    Example:
        {{ "Hello World" | slug }} → "hello-world"
        {{ "  foo  bar  " | slug }} → "foo-bar"
        {{ none | slug }} → ""
    """
    if value is None:
        return ""
    s = str(value).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _filter_pluralize(value: Any, suffix: str = "s") -> str:
    """Django-style pluralization suffix.

    Example:
        {{ 1 | pluralize }} → ""
        {{ 2 | pluralize }} → "s"
        {{ 1 | pluralize("y,ies") }} → "y"
        {{ 2 | pluralize("y,ies") }} → "ies"
    """
    if value is None:
        return suffix
    try:
        n = int(value) if not isinstance(value, int) else value
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"pluralize expects a number, got {type(value).__name__}: {value!r}. "
            "Use | int or ensure numeric value."
        ) from e
    if n == 1:
        if "," in suffix:
            return suffix.split(",")[0].strip()
        return ""
    if "," in suffix:
        return suffix.split(",")[1].strip()
    return suffix


def _filter_wordcount(value: str) -> int:
    """Count words in a string."""
    return len(str(value).split())
