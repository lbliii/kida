"""Tests for live terminal rendering — Spinner, stream_to_terminal, LiveRenderer."""

import io
import signal
from typing import Any

import pytest

from kida.terminal import LiveRenderer, Spinner, stream_to_terminal, terminal_env
from kida.terminal import live as live_module
from kida.utils.terminal_escape import Styled


class _FakeTTY(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[object, ...]] = []

    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        return 1

    def write(self, value: str) -> int:
        self.events.append(("write", value))
        return super().write(value)

    def flush(self) -> None:
        self.events.append(("flush",))
        super().flush()


def _capture_live_hooks(monkeypatch, stream: _FakeTTY):
    original_handler = object()
    registered_callbacks: list[Any] = []
    unregistered_callbacks: list[Any] = []
    signal_calls: list[tuple[int, Any]] = []

    def get_signal_handler(signum: int) -> object:
        stream.events.append(("getsignal", signum))
        return original_handler

    def set_signal_handler(signum: int, handler: Any) -> None:
        signal_calls.append((signum, handler))
        stream.events.append(("signal", signum, handler))

    def register_atexit(callback: Any) -> None:
        registered_callbacks.append(callback)
        stream.events.append(("atexit.register", callback))

    def unregister_atexit(callback: Any) -> None:
        unregistered_callbacks.append(callback)
        stream.events.append(("atexit.unregister", callback))

    monkeypatch.setattr(live_module.signal, "getsignal", get_signal_handler)
    monkeypatch.setattr(live_module.signal, "signal", set_signal_handler)
    monkeypatch.setattr(live_module.atexit, "register", register_atexit)
    monkeypatch.setattr(live_module.atexit, "unregister", unregister_atexit)
    monkeypatch.setattr(
        live_module.os,
        "get_terminal_size",
        lambda _fd=None: live_module.os.terminal_size((80, 24)),
    )
    return original_handler, registered_callbacks, unregistered_callbacks, signal_calls


class TestSpinner:
    def test_returns_styled(self):
        s = Spinner()
        assert isinstance(s(), Styled)

    def test_cycles_frames(self):
        s = Spinner(frames=("A", "B", "C"))
        assert str(s()) == "A"
        assert str(s()) == "B"
        assert str(s()) == "C"
        assert str(s()) == "A"  # wraps

    def test_default_braille_frames(self):
        s = Spinner()
        frame = s()
        assert len(frame) == 1  # single braille char

    def test_line_frames(self):
        s = Spinner(frames=Spinner.LINE)
        frames = [str(s()) for _ in range(4)]
        assert frames == ["-", "\\", "|", "/"]

    def test_reset(self):
        s = Spinner(frames=("X", "Y"))
        s()  # advance to Y
        s.reset()
        assert str(s()) == "X"

    def test_terminal_protocol(self):
        s = Spinner(frames=("Z",))
        assert s.__terminal__() == "Z"


class TestStreamToTerminal:
    def test_writes_all_chunks(self):
        env = terminal_env()
        tpl = env.from_string("Hello {{ name }}!\nDone.\n", name="test")
        buf = io.StringIO()
        stream_to_terminal(tpl, {"name": "world"}, delay=0, file=buf)
        assert "Hello world!" in buf.getvalue()
        assert "Done." in buf.getvalue()

    def test_no_delay_for_non_tty(self):
        env = terminal_env()
        tpl = env.from_string("{{ x }}", name="test")
        buf = io.StringIO()
        # StringIO.isatty() returns False, so delay should be skipped
        stream_to_terminal(tpl, {"x": "ok"}, delay=10, file=buf)
        assert buf.getvalue().strip() == "ok"

    def test_empty_context(self):
        env = terminal_env()
        tpl = env.from_string("static content", name="test")
        buf = io.StringIO()
        stream_to_terminal(tpl, delay=0, file=buf)
        assert "static content" in buf.getvalue()


class TestLiveRenderer:
    def test_non_tty_fallback(self):
        env = terminal_env()
        tpl = env.from_string("Status: {{ status }}", name="test")
        buf = io.StringIO()
        with LiveRenderer(tpl, file=buf) as live:
            live.update(status="building")
            live.update(status="done")
        output = buf.getvalue()
        assert "building" in output
        assert "done" in output

    def test_context_accumulates(self):
        env = terminal_env()
        tpl = env.from_string("{{ a }}-{{ b }}", name="test")
        buf = io.StringIO()
        with LiveRenderer(tpl, file=buf) as live:
            live.update(a="1", b="2")
            live.update(a="3")  # b should persist
        output = buf.getvalue()
        assert "3-2" in output

    def test_spinner_injected(self):
        env = terminal_env()
        tpl = env.from_string("{{ spinner() }}", name="test")
        buf = io.StringIO()
        with LiveRenderer(tpl, file=buf) as live:
            live.update()
        # Spinner should have been injected and rendered
        assert len(buf.getvalue().strip()) > 0

    def test_transient_mode(self):
        env = terminal_env()
        tpl = env.from_string("temp", name="test")
        buf = io.StringIO()
        # Non-TTY transient behaves same as non-transient (no cursor codes)
        with LiveRenderer(tpl, file=buf, transient=True) as live:
            live.update()
        assert "temp" in buf.getvalue()

    def test_tty_cursor_hidden_on_enter_and_restored_on_exit(self, monkeypatch):
        buf = _FakeTTY()
        original_handler, registered, unregistered, signal_calls = _capture_live_hooks(
            monkeypatch, buf
        )
        env = terminal_env()
        tpl = env.from_string("ready", name="test")

        with LiveRenderer(tpl, file=buf) as live:
            assert buf.getvalue() == "\033[?25l"

        assert buf.getvalue() == "\033[?25l\033[?25h"
        assert signal_calls == [
            (signal.SIGINT, live._handle_sigint),
            (signal.SIGINT, original_handler),
        ]
        assert registered == [live._show_cursor]
        assert unregistered == [live._show_cursor]
        assert buf.events == [
            ("write", "\033[?25l"),
            ("flush",),
            ("atexit.register", live._show_cursor),
            ("getsignal", signal.SIGINT),
            ("signal", signal.SIGINT, live._handle_sigint),
            ("write", "\033[?25h"),
            ("flush",),
            ("signal", signal.SIGINT, original_handler),
            ("atexit.unregister", live._show_cursor),
        ]

    def test_sigint_callback_shows_cursor_and_restores_prior_handler(self, monkeypatch):
        buf = _FakeTTY()
        original_handler, _registered, _unregistered, signal_calls = _capture_live_hooks(
            monkeypatch, buf
        )
        env = terminal_env()
        tpl = env.from_string("ready", name="test")
        live = LiveRenderer(tpl, file=buf)
        live.__enter__()

        try:
            handler = signal_calls[0][1]
            assert handler == live._handle_sigint
            with pytest.raises(KeyboardInterrupt):
                handler(signal.SIGINT, None)

            assert buf.getvalue() == "\033[?25l\033[?25h"
            assert signal_calls == [
                (signal.SIGINT, live._handle_sigint),
                (signal.SIGINT, original_handler),
            ]
        finally:
            live.__exit__(None, None, None)

    def test_atexit_callback_shows_cursor(self, monkeypatch):
        buf = _FakeTTY()
        _original_handler, registered, _unregistered, _signal_calls = _capture_live_hooks(
            monkeypatch, buf
        )
        env = terminal_env()
        tpl = env.from_string("ready", name="test")
        live = LiveRenderer(tpl, file=buf)
        live.__enter__()

        try:
            assert registered == [live._show_cursor]
            callback = registered[0]
            buf.events.clear()
            callback()

            assert buf.getvalue() == "\033[?25l\033[?25h"
            assert buf.events == [("write", "\033[?25h"), ("flush",)]
        finally:
            live.__exit__(None, None, None)

    def test_tty_transient_clears_previous_lines_before_showing_cursor(self, monkeypatch):
        buf = _FakeTTY()
        original_handler, registered, _unregistered, _signal_calls = _capture_live_hooks(
            monkeypatch, buf
        )
        env = terminal_env()
        tpl = env.from_string("first\nsecond", name="test")

        with LiveRenderer(tpl, file=buf, transient=True) as live:
            live.update()
            assert buf.getvalue() == "\033[?25lfirst\nsecond\n"

        assert buf.getvalue() == ("\033[?25lfirst\nsecond\n\r\033[A\033[2K\033[A\033[2K\r\033[?25h")
        assert buf.events[-8:] == [
            ("write", "\r"),
            ("write", "\033[A\033[2K"),
            ("write", "\033[A\033[2K"),
            ("write", "\r"),
            ("write", "\033[?25h"),
            ("flush",),
            ("signal", signal.SIGINT, original_handler),
            ("atexit.unregister", registered[0]),
        ]

    def test_tty_update_clears_multiline_output_before_shorter_redraw(self, monkeypatch):
        buf = _FakeTTY()
        _capture_live_hooks(monkeypatch, buf)
        env = terminal_env()
        tpl = env.from_string("{{ status }}", name="test")

        with LiveRenderer(tpl, file=buf) as live:
            live.update(status="first\nsecond\nthird")
            live.update(status="ready")

            assert buf.getvalue() == (
                "\033[?25lfirst\nsecond\nthird\n\r\033[A\033[2K\033[A\033[2K\033[A\033[2K\rready\n"
            )

        assert buf.getvalue().endswith("\033[?25h")

    def test_tty_update_refreshes_terminal_width(self, monkeypatch):
        buf = _FakeTTY()
        _capture_live_hooks(monkeypatch, buf)
        env = terminal_env()
        tpl = env.from_string("{{ columns }}", name="test")
        widths = iter((80, 120))
        monkeypatch.setattr(
            live_module.os,
            "get_terminal_size",
            lambda _fd=None: live_module.os.terminal_size((next(widths), 24)),
        )

        with LiveRenderer(tpl, file=buf) as live:
            live.update()
            live.update()

        assert buf.getvalue() == ("\033[?25l80\n\r\033[A\033[2K\r120\n\033[?25h")

    @pytest.mark.parametrize("error", [OSError, ValueError])
    def test_tty_update_renders_when_terminal_size_lookup_fails(self, monkeypatch, error):
        buf = _FakeTTY()
        _capture_live_hooks(monkeypatch, buf)
        env = terminal_env()
        tpl = env.from_string("rendered", name="test")

        def fail_terminal_size(_fd=None):
            raise error("terminal size unavailable")

        monkeypatch.setattr(live_module.os, "get_terminal_size", fail_terminal_size)

        with LiveRenderer(tpl, file=buf) as live:
            live.update()

        assert buf.getvalue() == "\033[?25lrendered\n\033[?25h"

    def test_no_crash_on_empty_template(self):
        env = terminal_env()
        tpl = env.from_string("", name="test")
        buf = io.StringIO()
        with LiveRenderer(tpl, file=buf) as live:
            live.update()

    def test_update_holds_lock_through_render(self):
        """Context merge and render share the output critical section."""
        import threading

        lock_available_during_render: list[bool] = []

        class ProbeTemplate:
            def render(self, **context):
                def probe_lock() -> None:
                    acquired = live._lock.acquire(blocking=False)
                    lock_available_during_render.append(acquired)
                    if acquired:
                        live._lock.release()

                probe = threading.Thread(target=probe_lock)
                probe.start()
                probe.join(timeout=5)
                assert not probe.is_alive()
                return context["marker"]

        buf = io.StringIO()
        live = LiveRenderer(ProbeTemplate(), file=buf)
        live.update(marker="atomic")

        assert lock_available_during_render == [False]
        assert buf.getvalue() == "atomic\n"
