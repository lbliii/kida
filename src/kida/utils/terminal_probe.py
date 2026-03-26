"""Terminal character width probing for Kida template engine.

Probes the actual terminal to determine how wide ambiguous-width Unicode
characters render. This gives pixel-accurate width measurement for the
user's specific terminal + font combination.

The probe works by:
1. Saving cursor position
2. Writing a test character
3. Querying cursor position via ANSI DSR (Device Status Report)
4. Measuring how many columns the cursor advanced

Thread-Safety:
    Probe functions are not thread-safe (they manipulate terminal state).
    Call once during Environment init, then use the cached result.
"""

from __future__ import annotations

import contextlib
import os
import sys


def probe_ambiguous_width(timeout: float = 0.1) -> int | None:
    """Probe the terminal to determine the rendered width of ambiguous characters.

    Writes a known ambiguous-width character and measures cursor movement
    using ANSI escape codes. Returns 1 or 2 on success, or ``None`` if
    probing is not possible (non-TTY, non-Unix, timeout, etc.).

    Args:
        timeout: Maximum seconds to wait for terminal response.

    Returns:
        1, 2, or None if probing failed.
    """
    # Guard: only works on Unix TTYs
    if not (sys.stdout.isatty() and sys.stdin.isatty()):
        return None

    if os.name != "posix":  # pragma: no cover
        return None

    try:
        import select
        import termios
        import tty
    except ImportError:  # pragma: no cover
        return None

    return _probe_tty(select, termios, tty, timeout)


def _probe_tty(select, termios, tty, timeout: float) -> int | None:  # pragma: no cover
    """TTY-dependent probe internals. Requires a real terminal to exercise."""
    # Test character: U+2605 (BLACK STAR) - East Asian Width "A" (Ambiguous).
    # Renders as width 1 on Western terminals, width 2 on CJK terminals.
    test_char = "\u2605"

    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()

    # Save terminal attributes
    try:
        old_attrs = termios.tcgetattr(stdin_fd)
    except termios.error:
        return None

    try:
        # Switch to raw mode so we can read the DSR response
        tty.setraw(stdin_fd)

        # Move to column 1, write test char, query position
        os.write(stdout_fd, b"\033[s")  # save cursor
        os.write(stdout_fd, b"\033[1G")  # move to column 1
        os.write(stdout_fd, f"{test_char}".encode())  # write test char
        os.write(stdout_fd, b"\033[6n")  # query cursor position

        # Read response: \033[<row>;<col>R
        response = b""
        while True:
            ready, _, _ = select.select([stdin_fd], [], [], timeout)
            if not ready:
                return None  # timeout
            ch = os.read(stdin_fd, 1)
            if not ch:
                return None
            response += ch
            if ch == b"R":
                break
            if len(response) > 32:
                return None  # sanity limit

        # Restore cursor (erase the test character)
        os.write(stdout_fd, b"\033[u")  # restore cursor
        os.write(stdout_fd, b"\033[K")  # erase to end of line

        # Parse response: \033[<row>;<col>R
        resp_str = response.decode("ascii", errors="ignore")
        if "[" not in resp_str or ";" not in resp_str:
            return None

        parts = resp_str.split("[")[-1].rstrip("R").split(";")
        if len(parts) != 2:
            return None

        col = int(parts[1])
        # We moved to column 1, then wrote one character.
        # If the cursor is now at column 2, the char is width 1.
        # If at column 3, the char is width 2.
        char_width = col - 1

        if char_width in (1, 2):
            return char_width
        return None

    except Exception:
        return None
    finally:
        # Always restore terminal attributes
        with contextlib.suppress(termios.error):
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attrs)
