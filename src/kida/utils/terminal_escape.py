"""Terminal ANSI escape utilities for Kida template engine.

Provides ANSI sanitization and the Styled safe-string class for terminal mode.
Analogous to html.py's html_escape/Markup but for terminal output.

Security:
- Strips dangerous ANSI sequences (cursor movement, screen manipulation, OSC,
  device control, bracketed paste) from untrusted input
- Preserves safe SGR (styling) sequences: colors, bold, underline, etc.
- Fast path: strings without ESC byte are returned immediately

All operations are O(n) single-pass with no ReDoS risk.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Self, SupportsIndex, cast

# =============================================================================
# ANSI Sequence Detection
# =============================================================================

# ESC byte — the start of all ANSI escape sequences
_ESC = "\033"

# Safe SGR pattern: ESC [ <digits and semicolons> m
# SGR (Select Graphic Rendition) controls text styling only — colors, bold,
# underline, etc. These are safe to pass through from untrusted input.
_SGR_RE = re.compile(r"\033\[[\d;]*m")

# All ANSI escape sequences (CSI, OSC, and simple two-char escapes).
# This captures everything we need to examine and potentially strip.
# - CSI: ESC [ ... <final byte 0x40-0x7E>
# - OSC: ESC ] ... (terminated by BEL \007 or ST \033\\)
# - Two-char: ESC <0x40-0x7E> (e.g., ESC D, ESC M)
_ANSI_RE = re.compile(
    r"\033"
    r"(?:"
    r"\[[0-?]*[ -/]*[@-~]"  # CSI sequences (includes SGR, private-mode params)
    r"|\][^\007\033]*(?:\007|\033\\)?"  # OSC sequences
    r"|[A-Z@-_]"  # Two-character sequences
    r")"
)


def _replace_sequence(match: re.Match[str]) -> str:
    """Keep safe SGR sequences, strip everything else."""
    seq = match.group(0)
    if _SGR_RE.fullmatch(seq):
        return seq
    return ""


# =============================================================================
# Core Sanitization
# =============================================================================


def ansi_sanitize(value: Any) -> str:
    """Strip dangerous ANSI sequences from untrusted input.

    Preserves safe SGR (styling) sequences while stripping cursor movement,
    screen manipulation, OSC, device control, and other dangerous escapes.

    This is the terminal-mode analogue of ``html_escape`` for HTML mode.

    Args:
        value: Value to sanitize (will be converted to string).

    Returns:
        Sanitized string with only safe SGR sequences remaining.

    Complexity:
        O(n) single pass. Returns immediately if no ESC byte present.

    """
    # __terminal__ protocol: already-safe content (like __html__ for Markup)
    terminal_method = getattr(value, "__terminal__", None)
    if terminal_method is not None:
        return str(terminal_method())

    s = value if isinstance(value, str) else str(value)

    # Fast path: no escape sequences at all
    if _ESC not in s:
        return s

    return _ANSI_RE.sub(_replace_sequence, s)


# =============================================================================
# Styled Class
# =============================================================================


class Styled(str):
    """A string subclass marking content as already styled with ANSI codes.

    The Styled class implements the ``__terminal__`` protocol used by the
    template engine to identify pre-sanitized terminal content. When combined
    with regular strings via operators like ``+``, the non-Styled strings are
    automatically sanitized.

    This is the terminal-mode analogue of ``Markup`` for HTML mode.

    Example:
            >>> safe = Styled("\\033[1mbold\\033[0m")
            >>> safe + " \\033[2Jclear"  # dangerous sequence stripped
        Styled('\\033[1mbold\\033[0m \\033[2Jclear' -> sanitized)

    Thread-Safety:
        Immutable (inherits from str). Safe for concurrent access.

    """

    __slots__ = ()

    def __new__(cls, value: Any = "") -> Self:
        """Create a Styled string.

        Args:
            value: Content to mark as safe. If it has a ``__terminal__()``
                   method, that method is called to get the string value.

        Returns:
            Styled instance containing the safe content.
        """
        if hasattr(value, "__terminal__"):
            value = value.__terminal__()
        return super().__new__(cls, value)

    def __terminal__(self) -> Self:
        """Return self -- already safe content.

        This method is the ``__terminal__`` protocol that the template engine
        uses to detect pre-sanitized terminal content.
        """
        return self

    def __repr__(self) -> str:
        return f"Styled({super().__repr__()})"

    # --- Operations that sanitize non-Styled values ---

    def __add__(self, other: str) -> Self:  # type: ignore[override]
        """Concatenate, sanitizing ``other`` if not Styled."""
        if isinstance(other, str) and not isinstance(other, Styled):
            other = ansi_sanitize(other)
        return self.__class__(super().__add__(other))

    def __radd__(self, other: str) -> Self:
        """Reverse concatenate, sanitizing ``other`` if not Styled."""
        if isinstance(other, str) and not isinstance(other, Styled):
            other = ansi_sanitize(other)
        return self.__class__(other.__add__(self))

    def __mul__(self, n: SupportsIndex) -> Self:  # type: ignore[override]
        """Repeat string n times."""
        return self.__class__(super().__mul__(n))

    def __mod__(self, args: Any) -> Self:  # type: ignore[override]
        """Format string with %-style, sanitizing non-Styled args."""
        escaped_args: Any
        if isinstance(args, tuple):
            args_tuple = cast("tuple[Any, ...]", args)
            escaped_args = tuple(_sanitize_arg(a) for a in args_tuple)
        elif isinstance(args, dict):
            args_dict = cast("dict[str, Any]", args)
            escaped_args = {k: _sanitize_arg(v) for k, v in args_dict.items()}
        else:
            escaped_args = _sanitize_arg(args)
        return self.__class__(super().__mod__(escaped_args))

    def __format__(self, format_spec: str) -> Self:
        """Support format() built-in, preserving Styled type."""
        if not format_spec:
            return self
        return self.__class__(format(str(self), format_spec))

    def format(self, *args: Any, **kwargs: Any) -> Self:  # type: ignore[override]
        """Format string, sanitizing non-Styled arguments."""
        args = tuple(_sanitize_arg(a) for a in args)
        kwargs = {k: _sanitize_arg(v) for k, v in kwargs.items()}
        return self.__class__(super().format(*args, **kwargs))

    def join(self, seq: Iterable[str]) -> Self:  # type: ignore[override]
        """Join sequence, sanitizing non-Styled elements."""
        return self.__class__(super().join(_sanitize_arg(s) for s in seq))


# =============================================================================
# Internal Helpers
# =============================================================================


def _sanitize_arg(value: Any) -> Any:
    """Sanitize a value if it's a string but not Styled.

    Used for sanitizing format arguments.
    """
    if isinstance(value, Styled):
        return value
    if isinstance(value, str):
        return ansi_sanitize(value)
    return value


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "Styled",
    "ansi_sanitize",
]
