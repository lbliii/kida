"""Markdown escape utilities for Kida template engine.

Provides GFM-safe escaping and the Marked safe-string class for markdown mode.
Analogous to terminal_escape.py's ansi_sanitize/Styled but for GitHub-flavored
markdown output.

Objects implementing __markdown__() bypass escaping (like __terminal__/__html__).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Self, SupportsIndex, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

# =============================================================================
# Markdown Special Characters
# =============================================================================

# Inline-special characters that can trigger markdown formatting anywhere
# in a line. Backslash is included so existing backslashes are preserved
# rather than chained with following escapes.
_INLINE_SPECIAL = "\\`*_[]<"
_INLINE_TABLE = str.maketrans({ch: f"\\{ch}" for ch in _INLINE_SPECIAL})

# Block-leading patterns that only have meaning at the start of a line
# (after up to 3 spaces of indentation, per CommonMark): ATX headings,
# blockquotes, unordered list markers, and ordered list markers.
_BLOCK_LEAD_RE = re.compile(
    r"(^|\n)([ \t]{0,3})(#{1,6}(?=[ \t]|$)|>|[-+](?=[ \t]|$)|\d{1,9}[.)](?=[ \t]|$))"
)


# =============================================================================
# Core Escaping
# =============================================================================


def markdown_escape(value: Any) -> str:
    """Escape GFM-significant characters in untrusted input.

    Inline characters (``\\``, `` ` ``, ``*``, ``_``, ``[``, ``]``, ``<``) are
    always backslash-escaped. Block-leading markers (``#``, ``>``, ``-``,
    ``+``, ordered-list digits) are escaped only at the start of a line —
    matching how real GFM parsers interpret them and keeping inline content
    like dates, version numbers, and prose hyphens unmangled.

    Objects implementing the ``__markdown__`` protocol bypass escaping.
    """
    markdown_method = getattr(value, "__markdown__", None)
    if markdown_method is not None:
        return str(markdown_method())

    s = value if isinstance(value, str) else str(value)
    s = s.translate(_INLINE_TABLE)
    return _BLOCK_LEAD_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}\\{m.group(3)}", s)


# =============================================================================
# Marked Class
# =============================================================================


class Marked(str):
    """A string subclass marking content as already safe for markdown output.

    The Marked class implements the ``__markdown__`` protocol used by the
    template engine to identify pre-escaped markdown content. When combined
    with regular strings via operators like ``+``, the non-Marked strings are
    automatically escaped.

    This is the markdown-mode analogue of ``Markup`` for HTML and ``Styled``
    for terminal mode.
    """

    __slots__ = ()

    def __new__(cls, value: Any = "") -> Self:
        if hasattr(value, "__markdown__"):
            value = value.__markdown__()
        return super().__new__(cls, value)

    def __markdown__(self) -> Self:
        """Return self -- already safe content."""
        return self

    def __repr__(self) -> str:
        return f"Marked({super().__repr__()})"

    # --- Operations that escape non-Marked values ---

    def __add__(self, other: str) -> Self:  # type: ignore[override]
        if isinstance(other, str) and not isinstance(other, Marked):
            other = markdown_escape(other)
        return self.__class__(super().__add__(other))

    def __radd__(self, other: str) -> Self:
        if isinstance(other, str) and not isinstance(other, Marked):
            other = markdown_escape(other)
        return self.__class__(other.__add__(self))

    def __mul__(self, n: SupportsIndex) -> Self:  # type: ignore[override]
        return self.__class__(super().__mul__(n))

    def __mod__(self, args: Any) -> Self:  # type: ignore[override]
        escaped_args: Any
        if isinstance(args, tuple):
            args_tuple = cast("tuple[Any, ...]", args)
            escaped_args = tuple(_escape_arg(a) for a in args_tuple)
        elif isinstance(args, dict):
            args_dict = cast("dict[str, Any]", args)
            escaped_args = {k: _escape_arg(v) for k, v in args_dict.items()}
        else:
            escaped_args = _escape_arg(args)
        return self.__class__(super().__mod__(escaped_args))

    def __format__(self, format_spec: str) -> Self:
        if not format_spec:
            return self
        return self.__class__(format(str(self), format_spec))

    def format(self, *args: Any, **kwargs: Any) -> Self:  # type: ignore[override]
        args = tuple(_escape_arg(a) for a in args)
        kwargs = {k: _escape_arg(v) for k, v in kwargs.items()}
        return self.__class__(super().format(*args, **kwargs))

    def join(self, seq: Iterable[str]) -> Self:  # type: ignore[override]
        return self.__class__(super().join(_escape_arg(s) for s in seq))


# =============================================================================
# Internal Helpers
# =============================================================================


def _escape_arg(value: Any) -> Any:
    """Escape a value if it's a string but not Marked."""
    if isinstance(value, Marked):
        return value
    if isinstance(value, str):
        return markdown_escape(value)
    return value


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "Marked",
    "markdown_escape",
]
