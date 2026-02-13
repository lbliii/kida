"""Terminal color utilities for rich error messages.

Provides ANSI color codes with automatic TTY detection and NO_COLOR support.
Simple, zero-dependency implementation for beautiful error output.
"""

from __future__ import annotations

import os
import sys
from typing import Literal

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
    "reset", "bold", "dim",
    "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_magenta", "bright_cyan"
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
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


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

    if is_error:
        content_colored = error_line(content)
    else:
        content_colored = dim_text(content)

    return f"{num_colored} | {content_colored}"
