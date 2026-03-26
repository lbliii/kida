"""Live terminal rendering — progressive output and in-place re-rendering.

Provides three public symbols:

- ``stream_to_terminal`` — write ``render_stream()`` chunks progressively
- ``Spinner`` — animated frame-cycling spinner for live templates
- ``LiveRenderer`` — context manager for in-place re-rendering
"""

from __future__ import annotations

import atexit
import contextlib
import os
import signal
import sys
import threading
import time
from typing import TYPE_CHECKING, Any, ClassVar, TextIO

from kida.utils.terminal_escape import Styled

if TYPE_CHECKING:
    from kida.template.core import Template

# ─── ANSI control sequences (written directly, not through template engine) ──

_CURSOR_UP = "\033[A"
_ERASE_LINE = "\033[2K"
_CURSOR_HIDE = "\033[?25l"
_CURSOR_SHOW = "\033[?25h"
_CR = "\r"


# =============================================================================
# Spinner
# =============================================================================


class Spinner:
    """Animated spinner that advances one frame per call.

    Use inside live-rendered templates — each ``LiveRenderer.update()``
    re-renders the template, calling the spinner again to advance the frame.

    The spinner implements the ``__terminal__`` protocol so its output
    bypasses ANSI sanitization, consistent with ``Styled`` and ``IconSet``.

    Usage in templates::

        {{ spinner() }} Building project...

    Usage in Python::

        spinner = Spinner()
        context["spinner"] = spinner
        # Each template.render(**context) call advances the frame
    """

    BRAILLE: ClassVar[tuple[str, ...]] = (
        "\u280b",
        "\u2819",
        "\u2839",
        "\u2838",
        "\u283c",
        "\u2834",
        "\u2826",
        "\u2827",
        "\u2807",
        "\u280f",
    )
    DOTS: ClassVar[tuple[str, ...]] = BRAILLE  # alias
    LINE: ClassVar[tuple[str, ...]] = ("-", "\\", "|", "/")
    ARROW: ClassVar[tuple[str, ...]] = (
        "\u2190",
        "\u2196",
        "\u2191",
        "\u2197",
        "\u2192",
        "\u2198",
        "\u2193",
        "\u2199",
    )

    def __init__(self, frames: tuple[str, ...] | None = None) -> None:
        self._frames = frames or self.BRAILLE
        self._index = 0
        self._lock = threading.Lock()

    def __call__(self) -> Styled:
        """Return the current frame and advance."""
        with self._lock:
            frame = self._frames[self._index % len(self._frames)]
            self._index += 1
        return Styled(frame)

    def __terminal__(self) -> str:
        """Protocol method — return current frame as safe string."""
        return str(self())

    def reset(self) -> None:
        """Reset the frame counter to the beginning."""
        with self._lock:
            self._index = 0


# =============================================================================
# stream_to_terminal
# =============================================================================


def stream_to_terminal(
    template: Template,
    context: dict[str, Any] | None = None,
    *,
    delay: float = 0.02,
    file: TextIO | None = None,
) -> None:
    """Write ``render_stream()`` chunks to the terminal progressively.

    Each chunk (delimited by statement boundaries or ``{% flush %}``) is
    written to *file* with an optional *delay* between chunks, creating a
    typewriter-style reveal effect.

    When *file* is not a TTY (piped output, CI, etc.), the delay is skipped
    and all chunks are written immediately.

    Args:
        template: A compiled Kida template.
        context: Template context variables.
        delay: Seconds to sleep between chunks (0 = no delay).
        file: Output stream (defaults to ``sys.stdout``).
    """
    if file is None:
        file = sys.stdout
    ctx = context or {}

    is_tty = hasattr(file, "isatty") and file.isatty()
    effective_delay = delay if is_tty else 0

    for chunk in template.render_stream(**ctx):
        file.write(chunk)
        file.flush()
        if effective_delay > 0:
            time.sleep(effective_delay)


# =============================================================================
# LiveRenderer
# =============================================================================


class LiveRenderer:
    """Context manager for in-place terminal re-rendering.

    Uses ANSI cursor movement to overwrite previously rendered output,
    creating smooth animation effects. Each call to ``update()`` re-renders
    the template with fresh context and replaces the on-screen output.

    When the output is not a TTY, falls back to appending each render
    separated by a blank line (log-style trace).

    Usage::

        from kida.terminal import terminal_env, LiveRenderer

        env = terminal_env()
        tpl = env.from_string(template_str, name="live")

        with LiveRenderer(tpl) as live:
            live.update(status="building", progress=0.0)
            time.sleep(1)
            live.update(status="testing", progress=0.5)
            time.sleep(1)
            live.update(status="done", progress=1.0)

    Args:
        template: A compiled Kida template.
        refresh_rate: Minimum seconds between auto-refreshes (when using
            ``start_auto()``). Defaults to 0.1.
        file: Output stream (defaults to ``sys.stdout``).
        transient: If True, clear the output on exit instead of leaving
            the final render on screen.
    """

    def __init__(
        self,
        template: Template,
        *,
        refresh_rate: float = 0.1,
        file: TextIO | None = None,
        transient: bool = False,
    ) -> None:
        self._template = template
        self._refresh_rate = refresh_rate
        self._file: TextIO = file or sys.stdout
        self._transient = transient

        self._is_live = hasattr(self._file, "isatty") and self._file.isatty()
        self._prev_line_count = 0
        self._lock = threading.Lock()
        self._context: dict[str, Any] = {}
        self._spinner = Spinner()
        self._original_sigint: Any = None
        self._atexit_registered = False

        # Auto-refresh state
        self._auto_stop = threading.Event()
        self._auto_thread: threading.Thread | None = None

    def __enter__(self) -> LiveRenderer:
        if self._is_live:
            # Hide cursor to prevent flicker
            self._file.write(_CURSOR_HIDE)
            self._file.flush()

            # Safety: show cursor on unexpected exit
            atexit.register(self._show_cursor)
            self._atexit_registered = True

            # Catch Ctrl+C gracefully
            self._original_sigint = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self._handle_sigint)

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop_auto()

        if self._is_live:
            if self._transient:
                self._clear_previous()
            self._file.write(_CURSOR_SHOW)
            self._file.flush()

            # Restore signal handler
            if self._original_sigint is not None:
                signal.signal(signal.SIGINT, self._original_sigint)
                self._original_sigint = None

            # Remove atexit handler
            if self._atexit_registered:
                atexit.unregister(self._show_cursor)
                self._atexit_registered = False

    def update(self, **context: Any) -> None:
        """Re-render the template with updated context.

        Merges *context* into the accumulated context from previous
        ``update()`` calls, then renders and replaces the on-screen output.
        """
        self._context.update(context)

        # Always provide spinner
        self._context.setdefault("spinner", self._spinner)

        # Update terminal width on each render (handles resize)
        if self._is_live:
            with contextlib.suppress(OSError, ValueError):
                self._context["columns"] = os.get_terminal_size(self._file.fileno()).columns

        output = self._template.render(**self._context)

        with self._lock:
            if self._is_live:
                self._clear_previous()
                self._write_output(output)
            else:
                # Non-TTY fallback: append each render
                if self._prev_line_count > 0:
                    self._file.write("\n")
                self._write_output(output)

    def start_auto(self, **context: Any) -> None:
        """Start auto-refreshing in a background thread.

        The template is re-rendered at ``refresh_rate`` intervals using the
        current context. This is useful for animating spinners without
        explicit ``update()`` calls. Call ``stop_auto()`` or exit the
        context manager to stop.
        """
        if self._auto_thread is not None:
            return

        self._context.update(context)
        self._auto_stop.clear()

        def _loop() -> None:
            while not self._auto_stop.is_set():
                self.update()
                self._auto_stop.wait(self._refresh_rate)

        self._auto_thread = threading.Thread(target=_loop, daemon=True)
        self._auto_thread.start()

    def stop_auto(self) -> None:
        """Stop the auto-refresh background thread."""
        if self._auto_thread is not None:
            self._auto_stop.set()
            self._auto_thread.join(timeout=2.0)
            self._auto_thread = None

    # ── Internal ──────────────────────────────────────────────────────────

    def _clear_previous(self) -> None:
        """Move cursor up and erase all previously rendered lines."""
        if self._prev_line_count > 0:
            self._file.write(_CR)
            for _ in range(self._prev_line_count):
                self._file.write(_CURSOR_UP + _ERASE_LINE)
            self._file.write(_CR)

    def _write_output(self, output: str) -> None:
        """Write rendered output and track line count."""
        self._file.write(output)
        if not output.endswith("\n"):
            self._file.write("\n")
        self._file.flush()
        self._prev_line_count = output.count("\n") + (0 if output.endswith("\n") else 1)

    def _show_cursor(self) -> None:
        """Safety net: ensure cursor is visible."""
        with contextlib.suppress(Exception):
            self._file.write(_CURSOR_SHOW)
            self._file.flush()

    def _handle_sigint(self, signum: int, frame: Any) -> None:
        """Handle Ctrl+C: clean up and re-raise."""
        self.stop_auto()
        self._file.write(_CURSOR_SHOW)
        self._file.flush()

        # Restore original handler and re-raise
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        raise KeyboardInterrupt
