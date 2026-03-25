"""Terminal capabilities, color utilities, and rich error messages.

Provides:
- ``TerminalCaps``: Detected terminal capabilities (color, size, unicode)
- ``_detect_terminal_caps()``: Auto-detect capabilities from the environment
- ``_make_hr_func()``: Factory for ``hr()`` horizontal-rule template global
- ``_init_terminal_mode()``: Configure Environment for ``autoescape="terminal"``
- ANSI color codes with automatic TTY detection and NO_COLOR support
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    pass  # Environment import avoided to prevent circular deps

# ANSI color codes
_COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
}

ColorName = Literal[
    "reset",
    "bold",
    "dim",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
]


def _should_use_colors() -> bool:
    """Check if terminal supports colors and user allows them.

    Returns:
        True if colors should be used, False otherwise

    Respects:
        - NO_COLOR environment variable (https://no-color.org/)
        - FORCE_COLOR environment variable (overrides NO_COLOR)
        - sys.stdout.isatty() for TTY detection
    """
    # FORCE_COLOR overrides everything
    if os.environ.get("FORCE_COLOR"):
        return True

    # NO_COLOR disables colors
    if os.environ.get("NO_COLOR"):
        return False

    # Only use colors if stdout is a TTY
    return sys.stdout.isatty()


# Cache the color decision
_USE_COLORS = _should_use_colors()


def supports_color() -> bool:
    """Check if current terminal supports color output.

    Returns:
        True if colors are enabled, False otherwise
    """
    return _USE_COLORS


def colorize(text: str, *colors: ColorName) -> str:
    """Apply ANSI color codes to text.

    Args:
        text: Text to colorize
        *colors: One or more color names to apply

    Returns:
        Colorized text if colors are supported, otherwise plain text

    Example:
        >>> colorize("Error", "red", "bold")
        '\033[31m\033[1mError\033[0m'  # if colors supported
        'Error'  # if colors not supported
    """
    if not _USE_COLORS or not colors:
        return text

    # Build color prefix
    prefix = "".join(_COLORS.get(color, "") for color in colors)
    if not prefix:
        return text

    reset = _COLORS["reset"]
    return f"{prefix}{text}{reset}"


def strip_colors(text: str) -> str:
    """Remove ANSI color codes from text.

    Args:
        text: Text potentially containing ANSI codes

    Returns:
        Text with all ANSI codes removed

    Example:
        >>> strip_colors("\033[31mError\033[0m")
        'Error'
    """
    import re

    # Match ANSI escape sequences
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


# Semantic color helpers for error messages
def error_code(text: str) -> str:
    """Color text as an error code (bright red + bold)."""
    return colorize(text, "bright_red", "bold")


def location(text: str) -> str:
    """Color text as a file location (cyan)."""
    return colorize(text, "cyan")


def line_number(text: str) -> str:
    """Color text as a line number (yellow)."""
    return colorize(text, "yellow")


def error_line(text: str) -> str:
    """Color text as an error line (bright red)."""
    return colorize(text, "bright_red")


def hint(text: str) -> str:
    """Color text as a hint/suggestion (green)."""
    return colorize(text, "green")


def suggestion(text: str) -> str:
    """Color text as a 'Did you mean?' suggestion (bright_green + bold)."""
    return colorize(text, "bright_green", "bold")


def dim_text(text: str) -> str:
    """Color text as dimmed/secondary (dim)."""
    return colorize(text, "dim")


def docs_url(text: str) -> str:
    """Color text as a documentation URL (bright_blue)."""
    return colorize(text, "bright_blue")


def format_error_header(code: str | None, message: str) -> str:
    """Format error header with optional code.

    Args:
        code: Optional error code (e.g., "K-RUN-001")
        message: Error message

    Returns:
        Formatted header with colors

    Example:
        >>> format_error_header("K-RUN-001", "Undefined variable")
        '\033[91m\033[1mK-RUN-001:\033[0m Undefined variable'
    """
    if code:
        return f"{error_code(code)}: {message}"
    return message


def format_source_line(
    lineno: int,
    content: str,
    is_error: bool = False,
    show_marker: bool = True,
) -> str:
    """Format a source line with colors.

    Args:
        lineno: Line number
        content: Line content
        is_error: True if this is the error line
        show_marker: True to show '>' marker for error line

    Returns:
        Formatted line with colors

    Example:
        >>> format_source_line(42, "{{ user }}", is_error=True)
        '\033[33m 42\033[0m | \033[91m{{ user }}\033[0m'
    """
    marker = ">" if (is_error and show_marker) else " "
    num_str = f"{marker}{lineno:>3}"
    num_colored = line_number(num_str)
    content_colored = error_line(content) if is_error else dim_text(content)
    return f"{num_colored} | {content_colored}"


# ---------------------------------------------------------------------------
# Terminal capability detection (moved from environment/core.py)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TerminalCaps:
    """Detected terminal capabilities."""

    is_tty: bool = True
    color: str = "basic"  # "none" | "basic" | "256" | "truecolor"
    unicode: bool = True
    width: int = 80
    height: int = 24


def _detect_terminal_caps() -> TerminalCaps:
    """Detect terminal capabilities from the environment."""
    is_tty = sys.stdout.isatty()

    # Color detection
    if os.environ.get("NO_COLOR") is not None:
        color = "none"
    elif os.environ.get("FORCE_COLOR") is not None:
        color = "basic"
    elif os.environ.get("COLORTERM", "") in ("truecolor", "24bit"):
        color = "truecolor"
    elif "256color" in os.environ.get("TERM", ""):
        color = "256"
    elif is_tty:
        color = "basic"
    else:
        color = "none"

    # Unicode detection from locale
    lang = os.environ.get("LANG", "")
    unicode_support = "UTF" in lang.upper()

    # Terminal size
    try:
        size = os.get_terminal_size()
        width, height = size.columns, size.lines
    except ValueError, OSError:
        width, height = 80, 24

    return TerminalCaps(
        is_tty=is_tty,
        color=color,
        unicode=unicode_support,
        width=width,
        height=height,
    )


def _make_hr_func(width: int, unicode: bool) -> Callable:
    """Create an ``hr()`` function for terminal templates."""
    default_char = "\u2500" if unicode else "-"

    def hr(w: int | None = None, char: str | None = None, title: str | None = None) -> str:
        c = char or default_char
        total = w or width
        if title:
            # ── Title ──────────
            max_title_len = max(0, total - 4)  # 4 = 2 chars padding + 2 spaces
            t = title[:max_title_len]
            padding = total - len(t) - 4
            left = 2
            right = max(0, padding - left)
            return f"{c * left} {t} {c * right}"
        return c * total

    return hr


def _init_terminal_mode(
    env: Any,
    terminal_color: str | None,
    terminal_width: int | None,
    terminal_unicode: bool | None,
) -> TerminalCaps:
    """Configure Environment for ``autoescape="terminal"`` mode.

    Detects terminal capabilities, applies user overrides, registers
    terminal-specific filters and globals.  Returns the resolved
    ``TerminalCaps`` so the caller can store it.
    """
    caps = _detect_terminal_caps()
    # Apply overrides
    color = terminal_color or caps.color
    width = terminal_width or caps.width
    unicode = terminal_unicode if terminal_unicode is not None else caps.unicode

    resolved = TerminalCaps(
        is_tty=caps.is_tty,
        color=color,
        unicode=unicode,
        width=width,
        height=caps.height,
    )

    # Register terminal filters
    from kida.environment.filters._terminal import make_terminal_filters

    terminal_filters = make_terminal_filters(
        color=(color != "none"),
        unicode=unicode,
    )
    env._filters.update(terminal_filters)

    # Override existing filters with ANSI-aware versions
    from kida.utils.ansi_width import ansi_center, ansi_truncate, ansi_wrap

    _orig_wordwrap = env._filters.get("wordwrap")
    _orig_truncate = env._filters.get("truncate")

    def _terminal_wordwrap(value, width=79, break_long_words=True):
        if not break_long_words and _orig_wordwrap is not None:
            return _orig_wordwrap(value, width, break_long_words=False)
        return ansi_wrap(str(value), width)

    def _terminal_truncate(value, length=255, killwords=False, end="\u2026", leeway=None):
        if not killwords and _orig_truncate is not None:
            return _orig_truncate(value, length, killwords=False, end=end, leeway=leeway)
        return ansi_truncate(str(value), length, suffix=end)

    def _terminal_center(value, width=80):
        return ansi_center(str(value), width)

    env._filters["wordwrap"] = _terminal_wordwrap
    env._filters["wrap"] = _terminal_wordwrap
    env._filters["truncate"] = _terminal_truncate
    env._filters["center"] = _terminal_center

    # Inject terminal globals
    from kida.utils.terminal_boxes import BoxSet
    from kida.utils.terminal_icons import IconSet

    env.globals.update(
        {
            "columns": width,
            "rows": resolved.height,
            "tty": caps.is_tty,
            "icons": IconSet(unicode=unicode),
            "box": BoxSet(unicode=unicode),
            "hr": _make_hr_func(width, unicode),
        }
    )

    return resolved
