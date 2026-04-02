"""Markdown escape utilities for Kida template engine.

Provides GFM-safe escaping and the Marked safe-string class for markdown mode.
Analogous to terminal_escape.py's ansi_sanitize/Styled but for GitHub-flavored
markdown output.

Escapes special markdown characters via str.translate() with backslash prefixes.
Objects implementing __markdown__() bypass escaping (like __terminal__/__html__).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, SupportsIndex, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

# =============================================================================
# Markdown Special Characters
# =============================================================================

# Characters that have special meaning in GFM and need backslash-escaping
_MD_SPECIAL = '*_[]()#`+-!|~>\\"'

# Build a translation table: each special char -> backslash + char
_ESCAPE_TABLE = str.maketrans({ch: f"\\{ch}" for ch in _MD_SPECIAL})


# =============================================================================
# Core Escaping
# =============================================================================


def markdown_escape(value: Any) -> str:
    """Escape GFM special characters in untrusted input.

    Checks the ``__markdown__`` protocol first — objects that implement it
    are considered pre-escaped and returned as-is (like ``__html__`` for
    Markup or ``__terminal__`` for Styled).

    Args:
        value: Value to escape (will be converted to string).

    Returns:
        String with GFM special characters backslash-escaped.
    """
    # __markdown__ protocol: already-safe content
    markdown_method = getattr(value, "__markdown__", None)
    if markdown_method is not None:
        return str(markdown_method())

    s = value if isinstance(value, str) else str(value)
    return s.translate(_ESCAPE_TABLE)


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
