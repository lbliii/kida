"""Tests for live terminal rendering — Spinner, stream_to_terminal, LiveRenderer."""

import io

from kida.terminal import LiveRenderer, Spinner, stream_to_terminal, terminal_env
from kida.utils.terminal_escape import Styled


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

    def test_no_crash_on_empty_template(self):
        env = terminal_env()
        tpl = env.from_string("", name="test")
        buf = io.StringIO()
        with LiveRenderer(tpl, file=buf) as live:
            live.update()
