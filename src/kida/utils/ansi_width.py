"""ANSI-aware string width operations for Kida template engine.

ANSI escape sequences are zero-width but occupy bytes. Any padding,
truncation, or wrapping must count *visible* characters, not raw string
length. This module provides width-correct alternatives to str.ljust,
str.rjust, str.center, and basic truncation/word-wrap.

All operations are pure Python with no dependencies outside stdlib.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

# Pre-compiled regex matching SGR, OSC, and CSI escape sequences.
# Covers the vast majority of terminal escape codes:
#   - SGR: \033[...m  (colors, bold, underline, etc.)
#   - OSC: \033]...\033\\  (operating system commands)
#   - CSI: \033[...<letter>  (cursor movement, erase, etc.)
_ANSI_RE = re.compile(r"\033\[[^m]*m|\033\].*?(?:\007|\033\\)|\033\[[^a-zA-Z]*[a-zA-Z]")


# =============================================================================
# Width Strategy — configurable character width measurement
# =============================================================================


@dataclass(frozen=True, slots=True)
class WidthStrategy:
    """Controls how ambiguous-width characters are measured.

    Attributes:
        ambiguous_width: Width to assign East Asian Ambiguous ("A") characters
            and symbol characters above U+2000 with Neutral ("N") width.
            Use 1 for most Western terminals, 2 for CJK-locale terminals
            or terminals that render these symbols at double width.
        _wcwidth_fn: Optional ``wcwidth.wcwidth`` function. When set, this
            takes precedence over the heuristic for non-wide characters.
    """

    ambiguous_width: int = 1
    _wcwidth_fn: Any = None  # Callable[[str], int] | None


# Module-level singleton — configured once, used by all width functions.
_strategy: WidthStrategy = WidthStrategy()


def configure_width(
    ambiguous_width: int = 1,
    use_wcwidth: bool = True,
) -> WidthStrategy:
    """Configure the global character width measurement strategy.

    Called by ``_init_terminal_mode()`` during Environment setup. The resolved
    strategy is stored at module level and automatically used by all width
    functions (``visible_len``, ``ansi_ljust``, ``pad`` filter, etc.).

    Args:
        ambiguous_width: Width for ambiguous characters (1 or 2).
        use_wcwidth: If True, attempt to import ``wcwidth`` for precise
            per-character widths. Falls back gracefully if not installed.

    Returns:
        The resolved ``WidthStrategy``.
    """
    global _strategy

    wcwidth_fn = None
    if use_wcwidth:
        try:
            from wcwidth import wcwidth as _wcwidth  # type: ignore[import-not-found]

            wcwidth_fn = _wcwidth
        except ImportError:
            pass

    _strategy = WidthStrategy(
        ambiguous_width=ambiguous_width,
        _wcwidth_fn=wcwidth_fn,
    )
    return _strategy


def _char_width(c: str) -> int:
    """Return the terminal display width of a single character.

    Consults the module-level ``_strategy`` for ambiguous character handling:
    1. If ``wcwidth`` is available, uses it (returns 1 or 2 per character).
    2. Otherwise, uses ``unicodedata.east_asian_width`` with the configured
       ``ambiguous_width`` for "A" (Ambiguous) and high-range "N" (Neutral)
       symbols that many terminals render as double-width.
    """
    # Fast path for ASCII (the vast majority of template text)
    o = ord(c)
    if o < 0x7F:
        return 1

    # Variation selectors (VS1-VS16, VS17-VS256) are zero-width.
    # VS15 (U+FE0E) forces text presentation; VS16 (U+FE0F) forces emoji.
    # Both are invisible combining characters.
    if 0xFE00 <= o <= 0xFE0F or 0xE0100 <= o <= 0xE01EF:
        return 0

    # wcwidth, when available, is the most accurate per-terminal match
    if _strategy._wcwidth_fn is not None:
        w = _strategy._wcwidth_fn(c)
        if w >= 0:
            return w
        return 1  # Control characters / unassigned → treat as 1

    eaw = unicodedata.east_asian_width(c)
    if eaw in ("W", "F"):  # Wide or Fullwidth — always 2
        return 2
    if eaw == "A":  # Ambiguous — terminal-dependent
        return _strategy.ambiguous_width
    # Neutral symbols above U+2000 (miscellaneous symbols, dingbats, etc.)
    # are often rendered as double-width in emoji-capable terminals even
    # though Unicode classifies them as Neutral.
    if o >= 0x2000 and eaw == "N" and unicodedata.category(c).startswith(("S", "So")):
        return _strategy.ambiguous_width
    return 1


def _str_width(s: str) -> int:
    """Return the total display width of a string (no ANSI).

    Handles VS15 (U+FE0E) text presentation selector: when a character
    is followed by VS15, the terminal renders it at width 1 regardless
    of its normal East Asian Width. The VS15 itself is zero-width.
    """
    total = 0
    chars = list(s)
    i = 0
    while i < len(chars):
        c = chars[i]
        # Check if next char is VS15 (text presentation selector)
        if i + 1 < len(chars) and chars[i + 1] == "\ufe0e":
            total += 1  # VS15 forces width 1
            i += 2  # skip both the char and VS15
        else:
            total += _char_width(c)
            i += 1
    return total


# =============================================================================
# Visible Length
# =============================================================================


def visible_len(s: str) -> int:
    """Return the visible character count, ignoring ANSI escape sequences.

    Uses a pre-compiled regex to strip all ANSI escapes before measuring.

    Args:
        s: String potentially containing ANSI escape sequences.

    Returns:
        Number of visible characters.

    Example:
        >>> visible_len("\\033[31mhello\\033[0m")
        5
        >>> visible_len("plain text")
        10

    """
    if "\033" not in s:
        return _str_width(s)
    return _str_width(_ANSI_RE.sub("", s))


# =============================================================================
# Padding / Justification
# =============================================================================


def ansi_ljust(s: str, width: int, fillchar: str = " ") -> str:
    """Left-justify (right-pad) to *width* visible characters.

    If the visible length already meets or exceeds *width*, return as-is.

    Args:
        s: String potentially containing ANSI escape sequences.
        width: Target visible width.
        fillchar: Character used for padding (default space).

    Returns:
        Padded string.

    """
    vlen = visible_len(s)
    if vlen >= width:
        return s
    return s + fillchar * (width - vlen)


def ansi_rjust(s: str, width: int, fillchar: str = " ") -> str:
    """Right-justify (left-pad) to *width* visible characters.

    If the visible length already meets or exceeds *width*, return as-is.

    Args:
        s: String potentially containing ANSI escape sequences.
        width: Target visible width.
        fillchar: Character used for padding (default space).

    Returns:
        Padded string.

    """
    vlen = visible_len(s)
    if vlen >= width:
        return s
    return fillchar * (width - vlen) + s


def ansi_center(s: str, width: int, fillchar: str = " ") -> str:
    """Center within *width* visible characters.

    If the visible length already meets or exceeds *width*, return as-is.
    When the padding is odd, the extra character goes on the right.

    Args:
        s: String potentially containing ANSI escape sequences.
        width: Target visible width.
        fillchar: Character used for padding (default space).

    Returns:
        Centered string.

    """
    vlen = visible_len(s)
    if vlen >= width:
        return s
    total_pad = width - vlen
    left_pad = total_pad // 2
    right_pad = total_pad - left_pad
    return fillchar * left_pad + s + fillchar * right_pad


# =============================================================================
# Truncation
# =============================================================================


def ansi_truncate(s: str, width: int, suffix: str = "\u2026") -> str:
    """Truncate to *width* visible characters.

    Walks the string character by character, tracking visible count while
    preserving ANSI sequences that appear before the cutoff point. If
    truncation occurs, appends *suffix* and a reset code (``\\033[0m``)
    to close any open styles.

    Args:
        s: String potentially containing ANSI escape sequences.
        width: Maximum visible width.
        suffix: String appended when truncation occurs (default ellipsis).

    Returns:
        Truncated string, or the original if it already fits.

    """
    # Fast path: no ANSI codes
    if "\033" not in s:
        if _str_width(s) <= width:
            return s
        suffix_len = _str_width(suffix)
        if width <= suffix_len:
            # Truncate suffix itself to fit
            out: list[str] = []
            w = 0
            for c in suffix:
                cw = _char_width(c)
                if w + cw > width:
                    break
                out.append(c)
                w += cw
            return "".join(out)
        target_w = width - suffix_len
        out = []
        w = 0
        for c in s:
            cw = _char_width(c)
            if w + cw > target_w:
                break
            out.append(c)
            w += cw
        return "".join(out) + suffix

    # Check if truncation is even needed
    if visible_len(s) <= width:
        return s

    suffix_len = visible_len(suffix)
    if width <= suffix_len:
        return suffix[:width]

    target = width - suffix_len
    result: list[str] = []
    visible = 0
    i = 0
    length = len(s)

    while i < length and visible < target:
        # Check for ANSI escape sequence
        if s[i] == "\033":
            m = _ANSI_RE.match(s, i)
            if m:
                result.append(m.group())
                i = m.end()
                continue
        # Visible character
        cw = _char_width(s[i])
        if visible + cw > target:
            break
        result.append(s[i])
        visible += cw
        i += 1

    return "".join(result) + suffix + "\033[0m"


# =============================================================================
# Word Wrap
# =============================================================================


def ansi_wrap(s: str, width: int) -> str:
    """Word-wrap at *width* visible characters.

    Tracks active ANSI style state and re-applies it at the start of each
    new line after a break. Words are split on spaces. Lines already
    shorter than *width* are left as-is.

    Args:
        s: String potentially containing ANSI escape sequences.
        width: Maximum visible width per line.

    Returns:
        Wrapped string with newlines inserted.

    """
    # Fast path: no ANSI codes
    if "\033" not in s:
        return _wrap_plain(s, width)

    # Tokenize: split into (token, is_ansi) pairs
    tokens = _tokenize(s)

    # Build words by splitting on spaces, preserving ANSI sequences
    # attached to adjacent visible characters.
    words: list[str] = []
    current_word: list[str] = []

    for token, is_ansi in tokens:
        if is_ansi:
            current_word.append(token)
        elif token == " ":
            if current_word:
                words.append("".join(current_word))
                current_word = []
            words.append(" ")
        else:
            # Regular visible characters — add one at a time
            for ch in token:
                current_word.append(ch)

    if current_word:
        words.append("".join(current_word))

    # Now wrap: walk words, tracking line width and active styles
    lines: list[str] = []
    line_parts: list[str] = []
    line_width = 0
    style_state: list[str] = []

    for word in words:
        if word == " ":
            # Space: add if room
            if line_width + 1 <= width:
                line_parts.append(" ")
                line_width += 1
            continue

        word_vlen = visible_len(word)

        # Collect ANSI codes from this word to track style
        word_styles = _ANSI_RE.findall(word)

        if line_width + word_vlen <= width:
            # Word fits on current line
            line_parts.append(word)
            line_width += word_vlen
            style_state.extend(word_styles)
        elif word_vlen > width:
            # Word itself is wider than width — force-break it
            _force_break_word(word, width, line_parts, line_width, lines, style_state)
            line_width = visible_len("".join(line_parts)) if line_parts else 0
        else:
            # Start a new line
            lines.append("".join(line_parts))
            # Re-apply active style state on new line
            prefix = _collapse_styles(style_state)
            line_parts = [prefix] if prefix else []
            line_parts.append(word)
            line_width = word_vlen
            style_state.extend(word_styles)

    if line_parts:
        lines.append("".join(line_parts))

    return "\n".join(lines)


# =============================================================================
# Internal Helpers
# =============================================================================


def _wrap_plain(s: str, width: int) -> str:
    """Word-wrap a plain string (no ANSI codes) at *width* characters."""
    words = s.split(" ")
    lines: list[str] = []
    line: list[str] = []
    line_len = 0

    for word in words:
        wlen = _str_width(word)
        if not line:
            line.append(word)
            line_len = wlen
        elif line_len + 1 + wlen <= width:
            line.append(word)
            line_len += 1 + wlen
        else:
            lines.append(" ".join(line))
            line = [word]
            line_len = wlen

    if line:
        lines.append(" ".join(line))

    return "\n".join(lines)


def _tokenize(s: str) -> list[tuple[str, bool]]:
    """Split *s* into (text, is_ansi) token pairs.

    ANSI escape sequences are returned as single tokens with ``is_ansi=True``.
    Non-ANSI text runs are returned with ``is_ansi=False``.
    """
    tokens: list[tuple[str, bool]] = []
    pos = 0
    for m in _ANSI_RE.finditer(s):
        start, end = m.start(), m.end()
        if pos < start:
            tokens.append((s[pos:start], False))
        tokens.append((m.group(), True))
        pos = end
    if pos < len(s):
        tokens.append((s[pos:], False))
    return tokens


def _collapse_styles(styles: list[str]) -> str:
    """Collapse a list of ANSI style codes into the minimal active state.

    If a reset (``\\033[0m``) is present, only codes after the last reset
    are relevant.
    """
    if not styles:
        return ""
    # Find last reset
    last_reset = -1
    for i, code in enumerate(styles):
        if code == "\033[0m":
            last_reset = i
    active = styles[last_reset + 1 :] if last_reset >= 0 else styles
    return "".join(active)


def _force_break_word(
    word: str,
    width: int,
    line_parts: list[str],
    line_width: int,
    lines: list[str],
    style_state: list[str],
) -> None:
    """Break a word that is wider than *width* across multiple lines.

    Mutates *line_parts*, *lines*, and *style_state* in place.
    """
    i = 0
    length = len(word)
    current_width = line_width
    word_styles: list[str] = []

    while i < length:
        if word[i] == "\033":
            m = _ANSI_RE.match(word, i)
            if m:
                line_parts.append(m.group())
                word_styles.append(m.group())
                style_state.append(m.group())
                i = m.end()
                continue
        # Visible character
        cw = _char_width(word[i])
        if current_width + cw > width:
            lines.append("".join(line_parts))
            prefix = _collapse_styles(style_state)
            line_parts.clear()
            if prefix:
                line_parts.append(prefix)
            current_width = 0
        line_parts.append(word[i])
        current_width += cw
        i += 1


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "WidthStrategy",
    "ansi_center",
    "ansi_ljust",
    "ansi_rjust",
    "ansi_truncate",
    "ansi_wrap",
    "configure_width",
    "visible_len",
]
