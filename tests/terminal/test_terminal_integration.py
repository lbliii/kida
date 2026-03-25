"""Integration tests for Kida terminal mode.

Tests the full stack: Environment setup with autoescape="terminal",
terminal capabilities detection, filter registration, template rendering,
escape function selection, and the terminal_env convenience function.
"""

from __future__ import annotations

import pytest

from kida.environment import Environment
from kida.environment.terminal import TerminalCaps, _detect_terminal_caps, _make_hr_func
from kida.terminal import terminal_env

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def term_env():
    """Environment with terminal mode and basic color forced (CI-safe)."""
    return Environment(autoescape="terminal", terminal_color="basic")


@pytest.fixture()
def nocolor_env():
    """Terminal environment with color disabled."""
    return Environment(autoescape="terminal", terminal_color="none")


# ===========================================================================
# Environment setup
# ===========================================================================


class TestEnvironmentSetup:
    """autoescape='terminal' wires up caps, filters, and globals."""

    def test_terminal_caps_created(self, term_env: Environment):
        assert term_env._terminal_caps is not None
        assert isinstance(term_env._terminal_caps, TerminalCaps)

    @pytest.mark.parametrize("name", ["red", "bold", "badge", "green", "underline"])
    def test_terminal_filters_registered(self, term_env: Environment, name: str):
        assert name in term_env._filters, f"filter '{name}' not registered"

    @pytest.mark.parametrize("name", ["columns", "rows", "tty", "icons", "box", "hr"])
    def test_terminal_globals_injected(self, term_env: Environment, name: str):
        assert name in term_env.globals, f"global '{name}' not injected"

    def test_select_autoescape_terminal_returns_true(self, term_env: Environment):
        # "terminal" is a truthy non-"false" string, so select_autoescape returns True
        assert term_env.select_autoescape("anything.txt") is True
        assert term_env.select_autoescape(None) is True

    def test_override_terminal_color(self):
        env = Environment(autoescape="terminal", terminal_color="truecolor")
        assert env._terminal_caps is not None
        assert env._terminal_caps.color == "truecolor"

    def test_override_terminal_width(self):
        env = Environment(autoescape="terminal", terminal_width=120, terminal_color="basic")
        assert env._terminal_caps is not None
        assert env._terminal_caps.width == 120
        assert env.globals["columns"] == 120


# ===========================================================================
# TerminalCaps
# ===========================================================================


class TestTerminalCaps:
    """TerminalCaps frozen dataclass basics."""

    def test_fields_accessible(self):
        caps = TerminalCaps()
        assert caps.is_tty is True
        assert caps.color == "basic"
        assert caps.unicode is True
        assert caps.width == 80
        assert caps.height == 24

    def test_frozen(self):
        caps = TerminalCaps()
        with pytest.raises(AttributeError):
            caps.width = 999  # type: ignore[misc]

    def test_custom_values(self):
        caps = TerminalCaps(is_tty=False, color="truecolor", unicode=False, width=132, height=50)
        assert caps.is_tty is False
        assert caps.color == "truecolor"
        assert caps.unicode is False
        assert caps.width == 132
        assert caps.height == 50


# ===========================================================================
# _detect_terminal_caps
# ===========================================================================


class TestDetectTerminalCaps:
    """Environment-variable driven capability detection."""

    def test_no_color_env_var(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        caps = _detect_terminal_caps()
        assert caps.color == "none"

    def test_force_color_env_var(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("FORCE_COLOR", "1")
        caps = _detect_terminal_caps()
        assert caps.color != "none"

    def test_colorterm_truecolor(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.setenv("COLORTERM", "truecolor")
        caps = _detect_terminal_caps()
        assert caps.color == "truecolor"


# ===========================================================================
# _make_hr_func
# ===========================================================================


class TestMakeHrFunc:
    """Horizontal rule factory."""

    def test_full_width(self):
        hr = _make_hr_func(80, unicode=True)
        result = hr()
        assert len(result) == 80

    def test_custom_width(self):
        hr = _make_hr_func(80, unicode=True)
        result = hr(30)
        assert len(result) == 30

    def test_custom_char(self):
        hr = _make_hr_func(80, unicode=True)
        result = hr(30, "=")
        assert result == "=" * 30

    def test_title(self):
        hr = _make_hr_func(80, unicode=True)
        result = hr(30, title="Section")
        assert "Section" in result
        # Title format: "── Section ──────────..."
        # Verify title is embedded between rule characters
        assert result.startswith("\u2500\u2500 ")
        assert " Section " in result

    def test_unicode_false_uses_dash(self):
        hr = _make_hr_func(10, unicode=False)
        result = hr()
        assert result == "-" * 10


# ===========================================================================
# Escape function selection
# ===========================================================================


class TestEscapeFunctionSelection:
    """autoescape mode determines the escape function used during render."""

    def test_terminal_mode_uses_ansi_sanitize(self):
        env = Environment(autoescape="terminal", terminal_color="basic")
        # Dangerous cursor-move sequence in user input should be stripped
        t = env.from_string("{{ user_input }}")
        result = t.render(user_input="hello\033[2Jworld")
        assert "\033[2J" not in result
        assert "helloworld" in result

    def test_html_mode_uses_html_escape(self):
        env = Environment(autoescape=True)
        t = env.from_string("{{ user_input }}")
        result = t.render(user_input="<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_no_escape_mode(self):
        env = Environment(autoescape=False)
        t = env.from_string("{{ user_input }}")
        result = t.render(user_input="<b>raw</b>")
        assert result == "<b>raw</b>"


# ===========================================================================
# Template rendering in terminal mode
# ===========================================================================


class TestTemplateRendering:
    """Rendering templates with terminal autoescape."""

    def test_dangerous_ansi_stripped_from_context(self, term_env: Environment):
        t = term_env.from_string("{{ user_input }}")
        # ESC[2J is "erase display" -- dangerous
        result = t.render(user_input="hello\033[2Jworld")
        assert "\033[2J" not in result
        assert "helloworld" in result

    def test_filter_output_not_escaped(self, term_env: Environment):
        t = term_env.from_string("{{ x | red }}")
        result = t.render(x="hi")
        # The red filter wraps text in SGR codes (ESC[31m...ESC[0m)
        assert "\033[31m" in result
        assert "\033[0m" in result
        assert "hi" in result

    def test_render_stream_terminal(self, term_env: Environment):
        t = term_env.from_string("A{{ x }}B")
        chunks = list(t.render_stream(x="mid"))
        joined = "".join(chunks)
        assert joined == "AmidB"

    def test_render_block_terminal(self, term_env: Environment):
        t = term_env.from_string("{% block greet %}Hello {{ name }}{% endblock %}")
        result = t.render_block("greet", name="World")
        assert result == "Hello World"


# ===========================================================================
# terminal_env convenience
# ===========================================================================


class TestTerminalEnv:
    """terminal_env() helper in kida.terminal."""

    def test_returns_environment(self):
        env = terminal_env(terminal_color="basic")
        assert isinstance(env, Environment)
        assert env.autoescape == "terminal"

    def test_accepts_kwargs(self):
        env = terminal_env(terminal_color="truecolor", terminal_width=100)
        assert env._terminal_caps is not None
        assert env._terminal_caps.color == "truecolor"
        assert env._terminal_caps.width == 100

    def test_has_loader(self):
        env = terminal_env(terminal_color="basic")
        assert env.loader is not None


# ===========================================================================
# Components (loaded via terminal_env)
# ===========================================================================


class TestComponents:
    """Built-in terminal component templates."""

    def test_can_load_components(self):
        env = terminal_env(terminal_color="basic")
        # components.txt should be loadable
        t = env.get_template("components.txt")
        assert t is not None

    def test_box_component_renders(self):
        env = terminal_env(terminal_color="basic")
        t = env.from_string(
            '{% from "components.txt" import box %}'
            '{% call box(title="Test", width=40) %}Line one{% endcall %}'
        )
        result = t.render()
        assert "Test" in result
        assert "Line one" in result


# ===========================================================================
# Filter overrides (ANSI-aware)
# ===========================================================================


class TestFilterOverrides:
    """Terminal mode overrides wordwrap, truncate, center with ANSI-aware versions."""

    def test_wordwrap_ansi_aware(self, term_env: Environment):
        t = term_env.from_string("{{ text | wordwrap(10) }}")
        result = t.render(text="short long_word_here")
        # Should wrap; exact output depends on ansi_wrap implementation
        assert "\n" in result or len(result.split("\n")[0]) <= 15

    def test_truncate_ansi_aware(self, term_env: Environment):
        t = term_env.from_string("{{ text | truncate(10) }}")
        result = t.render(text="This is a very long piece of text")
        # Should be truncated
        assert len(result) <= 15  # 10 + suffix + possible reset

    def test_wrap_alias(self, term_env: Environment):
        # "wrap" should be an alias for wordwrap in terminal mode
        assert "wrap" in term_env._filters
        assert term_env._filters["wrap"] is term_env._filters["wordwrap"]

    def test_center_ansi_aware(self, term_env: Environment):
        t = term_env.from_string("{{ text | center(20) }}")
        result = t.render(text="hi")
        # "hi" centered in 20 chars should have padding
        assert "hi" in result
        assert len(result) >= 20
