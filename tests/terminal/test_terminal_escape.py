"""Tests for terminal ANSI escape sanitization and Styled class.

Tests ansi_sanitize() security guarantees and Styled operator behavior.
Mirrors the structure of test_markup_security.py for HTML mode.

Test Categories:
- ansi_sanitize: plain text, SGR preservation, dangerous stripping, fast path
- __terminal__ protocol: objects implementing the protocol
- Styled operations: concatenation, formatting, join, repr
"""

from __future__ import annotations

from kida.utils.terminal_escape import Styled, ansi_sanitize

# =============================================================================
# ansi_sanitize() Tests
# =============================================================================


class TestAnsiSanitizePlainText:
    """Plain text without ANSI escapes passes through unchanged."""

    def test_plain_ascii(self) -> None:
        """Simple ASCII text is unchanged."""
        assert ansi_sanitize("hello world") == "hello world"

    def test_empty_string(self) -> None:
        """Empty string returns empty."""
        assert ansi_sanitize("") == ""

    def test_unicode_text(self) -> None:
        """Unicode text without ESC byte passes through."""
        assert ansi_sanitize("cafe\u0301 \u2603 \U0001f600") == "cafe\u0301 \u2603 \U0001f600"

    def test_fast_path_no_esc(self) -> None:
        """No ESC byte means immediate return without regex work."""
        text = "a" * 10_000
        assert ansi_sanitize(text) == text


class TestAnsiSanitizeSafeSGR:
    """Safe SGR (styling) sequences are preserved."""

    def test_red_foreground(self) -> None:
        """SGR color code preserved."""
        s = "\033[31mred\033[0m"
        assert ansi_sanitize(s) == s

    def test_bold(self) -> None:
        """SGR bold preserved."""
        s = "\033[1mbold\033[0m"
        assert ansi_sanitize(s) == s

    def test_reset(self) -> None:
        """SGR reset preserved."""
        s = "\033[0m"
        assert ansi_sanitize(s) == s

    def test_compound_sgr(self) -> None:
        """SGR with multiple parameters preserved."""
        s = "\033[1;31;42mstyle\033[0m"
        assert ansi_sanitize(s) == s

    def test_256_color(self) -> None:
        """256-color SGR preserved."""
        s = "\033[38;5;196mred\033[0m"
        assert ansi_sanitize(s) == s


class TestAnsiSanitizeDangerous:
    """Dangerous ANSI sequences are stripped."""

    def test_cursor_up(self) -> None:
        """Cursor movement up stripped."""
        assert ansi_sanitize("\033[2Atext") == "text"

    def test_cursor_home(self) -> None:
        """Cursor home stripped."""
        assert ansi_sanitize("\033[Htext") == "text"

    def test_screen_clear(self) -> None:
        """Screen clear stripped."""
        assert ansi_sanitize("\033[2Jtext") == "text"

    def test_line_clear(self) -> None:
        """Line clear stripped."""
        assert ansi_sanitize("\033[Ktext") == "text"

    def test_osc_title(self) -> None:
        """OSC title-set sequence stripped."""
        assert ansi_sanitize("\033]0;evil title\007text") == "text"

    def test_device_status_report(self) -> None:
        """Device control (status report) stripped."""
        assert ansi_sanitize("\033[6ntext") == "text"

    def test_cursor_down(self) -> None:
        """Cursor movement down stripped."""
        assert ansi_sanitize("\033[5Btext") == "text"

    def test_cursor_forward(self) -> None:
        """Cursor movement forward stripped."""
        assert ansi_sanitize("\033[10Ctext") == "text"


class TestAnsiSanitizeMixed:
    """Mixed safe and dangerous sequences: safe kept, dangerous stripped."""

    def test_safe_and_dangerous(self) -> None:
        """SGR preserved, cursor movement stripped."""
        s = "\033[31mred\033[2Ahidden\033[0m"
        result = ansi_sanitize(s)
        assert "\033[31m" in result  # SGR preserved
        assert "\033[0m" in result  # reset preserved
        assert "\033[2A" not in result  # cursor up stripped
        assert "hidden" in result  # text preserved

    def test_safe_between_dangerous(self) -> None:
        """Safe SGR surrounded by dangerous sequences."""
        s = "\033[2J\033[1mbold\033[0m\033[K"
        assert ansi_sanitize(s) == "\033[1mbold\033[0m"

    def test_multiple_dangerous(self) -> None:
        """Multiple dangerous sequences all stripped."""
        s = "\033[2J\033[H\033[Khello"
        assert ansi_sanitize(s) == "hello"


class TestAnsiSanitizeTypeCoercion:
    """Non-string input is converted to string."""

    def test_integer(self) -> None:
        """Integer is converted to string."""
        assert ansi_sanitize(42) == "42"

    def test_none(self) -> None:
        """None is converted to 'None'."""
        assert ansi_sanitize(None) == "None"

    def test_float(self) -> None:
        """Float is converted to string."""
        assert ansi_sanitize(3.14) == "3.14"


# =============================================================================
# __terminal__ Protocol Tests
# =============================================================================


class TestTerminalProtocol:
    """Objects with __terminal__() bypass sanitization."""

    def test_terminal_protocol_returns_result(self) -> None:
        """__terminal__() return value is used directly."""

        class SafeTerminal:
            def __terminal__(self) -> str:
                return "\033[2Jkept"

        result = ansi_sanitize(SafeTerminal())
        # Dangerous sequences preserved because __terminal__ is trusted
        assert result == "\033[2Jkept"

    def test_terminal_protocol_over_str(self) -> None:
        """__terminal__() takes priority over __str__()."""

        class Dual:
            def __str__(self) -> str:
                return "wrong"

            def __terminal__(self) -> str:
                return "correct"

        assert ansi_sanitize(Dual()) == "correct"

    def test_styled_passes_through(self) -> None:
        """Styled objects pass through via __terminal__ protocol."""
        s = Styled("\033[2Jclear")
        assert ansi_sanitize(s) == "\033[2Jclear"


# =============================================================================
# Styled Class Tests
# =============================================================================


class TestStyledTerminalProtocol:
    """Styled implements the __terminal__ protocol."""

    def test_terminal_returns_self(self) -> None:
        """__terminal__() returns self."""
        s = Styled("text")
        assert s.__terminal__() is s

    def test_isinstance_str(self) -> None:
        """Styled is a str subclass."""
        s = Styled("text")
        assert isinstance(s, str)


class TestStyledAdd:
    """Styled + str sanitizes the str side."""

    def test_add_sanitizes_dangerous(self) -> None:
        """+ operator strips dangerous sequences from plain str."""
        result = Styled("\033[1mbold\033[0m") + "\033[2Jevil"
        assert isinstance(result, Styled)
        assert "\033[2J" not in result
        assert "evil" in result
        assert "\033[1mbold\033[0m" in result

    def test_add_preserves_safe_in_rhs(self) -> None:
        """+ operator preserves SGR in plain str."""
        result = Styled("a") + "\033[31mred\033[0m"
        assert "\033[31m" in result

    def test_radd_sanitizes_dangerous(self) -> None:
        """Reverse + strips dangerous sequences from plain str."""
        result = "\033[2Jevil" + Styled("\033[1mbold\033[0m")
        assert isinstance(result, Styled)
        assert "\033[2J" not in result
        assert "evil" in result

    def test_radd_preserves_safe_in_lhs(self) -> None:
        """Reverse + preserves SGR in plain str."""
        result = "\033[31mred\033[0m" + Styled("b")
        assert "\033[31m" in result

    def test_styled_plus_styled_no_double_sanitize(self) -> None:
        """Styled + Styled does not sanitize either side."""
        a = Styled("\033[2Jclear")
        b = Styled("\033[Hhome")
        result = a + b
        assert isinstance(result, Styled)
        # Both dangerous sequences preserved (both sides trusted)
        assert "\033[2J" in result
        assert "\033[H" in result


class TestStyledMul:
    """Styled * n returns Styled."""

    def test_mul_returns_styled(self) -> None:
        """Multiplication returns Styled instance."""
        s = Styled("ab")
        result = s * 3
        assert isinstance(result, Styled)
        assert result == "ababab"


class TestStyledMod:
    """Styled % args sanitizes arguments."""

    def test_mod_sanitizes_string_arg(self) -> None:
        """% with string arg sanitizes dangerous sequences."""
        result = Styled("hello %s") % "\033[2Jevil"
        assert isinstance(result, Styled)
        assert "\033[2J" not in result
        assert "evil" in result

    def test_mod_sanitizes_tuple_args(self) -> None:
        """% with tuple args sanitizes each string."""
        result = Styled("%s and %s") % ("\033[2Ja", "\033[Hb")
        assert "\033[2J" not in result
        assert "\033[H" not in result
        assert "a and b" in result

    def test_mod_sanitizes_dict_args(self) -> None:
        """% with dict args sanitizes string values."""
        result = Styled("%(x)s") % {"x": "\033[2Jevil"}
        assert "\033[2J" not in result
        assert "evil" in result

    def test_mod_preserves_styled_arg(self) -> None:
        """% preserves Styled arguments without sanitization."""
        safe = Styled("\033[2Jkept")
        result = Styled("val: %s") % safe
        assert "\033[2J" in result

    def test_mod_passes_int_through(self) -> None:
        """% passes non-string args through unchanged."""
        result = Styled("num: %d") % 42
        assert result == "num: 42"


class TestStyledFormat:
    """Styled.format() sanitizes arguments."""

    def test_format_sanitizes_positional(self) -> None:
        """format() sanitizes positional string args."""
        result = Styled("hello {}").format("\033[2Jevil")
        assert isinstance(result, Styled)
        assert "\033[2J" not in result
        assert "evil" in result

    def test_format_sanitizes_keyword(self) -> None:
        """format() sanitizes keyword string args."""
        result = Styled("hello {name}").format(name="\033[Hbad")
        assert "\033[H" not in result
        assert "bad" in result

    def test_format_preserves_styled_arg(self) -> None:
        """format() preserves Styled arguments."""
        safe = Styled("\033[2Jkept")
        result = Styled("val: {}").format(safe)
        assert "\033[2J" in result


class TestStyledJoin:
    """Styled.join() sanitizes non-Styled elements."""

    def test_join_sanitizes_plain_strings(self) -> None:
        """join() sanitizes plain string elements."""
        result = Styled(", ").join(["\033[2Ja", "\033[Hb"])
        assert isinstance(result, Styled)
        assert "\033[2J" not in result
        assert "\033[H" not in result
        assert "a, b" in result

    def test_join_preserves_styled_elements(self) -> None:
        """join() preserves Styled elements."""
        result = Styled(", ").join([Styled("\033[2Jkept"), "plain"])
        assert "\033[2J" in result
        assert "plain" in result


class TestStyledConstructor:
    """Styled constructor handles __terminal__ protocol objects."""

    def test_from_terminal_protocol_object(self) -> None:
        """Constructor calls __terminal__() on protocol objects."""

        class SafeObj:
            def __terminal__(self) -> str:
                return "\033[1mfrom protocol\033[0m"

        s = Styled(SafeObj())
        assert s == "\033[1mfrom protocol\033[0m"
        assert isinstance(s, Styled)

    def test_from_plain_string(self) -> None:
        """Constructor accepts plain strings."""
        s = Styled("hello")
        assert s == "hello"

    def test_default_empty(self) -> None:
        """Default constructor produces empty string."""
        s = Styled()
        assert s == ""


class TestStyledRepr:
    """Styled repr format."""

    def test_repr(self) -> None:
        """repr wraps with Styled(...)."""
        s = Styled("hello")
        assert repr(s) == "Styled('hello')"

    def test_repr_with_escapes(self) -> None:
        """repr shows escape sequences."""
        s = Styled("\033[1mbold\033[0m")
        r = repr(s)
        assert r.startswith("Styled(")
        assert r.endswith(")")
