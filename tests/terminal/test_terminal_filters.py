"""Comprehensive tests for terminal filters, icons, and boxes."""

from __future__ import annotations

import pytest

from kida.environment.filters._terminal import make_terminal_filters
from kida.utils.terminal_boxes import BoxSet
from kida.utils.terminal_escape import Styled
from kida.utils.terminal_icons import IconSet

# =============================================================================
# Fixtures
# =============================================================================

RESET = "\033[0m"


@pytest.fixture()
def f_color():
    """Filter dict with color=True, unicode=True."""
    return make_terminal_filters(color=True, unicode=True)


@pytest.fixture()
def f_nocolor():
    """Filter dict with color=False, unicode=True."""
    return make_terminal_filters(color=False, unicode=True)


@pytest.fixture()
def f_ascii():
    """Filter dict with color=True, unicode=False."""
    return make_terminal_filters(color=True, unicode=False)


@pytest.fixture()
def f_plain():
    """Filter dict with color=False, unicode=False."""
    return make_terminal_filters(color=False, unicode=False)


# =============================================================================
# Color Filters
# =============================================================================


class TestColorFilters:
    def test_red_with_color(self, f_color):
        result = f_color["red"]("hello")
        assert result == f"\033[31mhello{RESET}"
        assert isinstance(result, Styled)

    def test_red_no_color_returns_plain(self, f_nocolor):
        result = f_nocolor["red"]("hello")
        assert result == "hello"
        assert "\033[" not in result
        assert isinstance(result, Styled)

    def test_bold_with_color(self, f_color):
        result = f_color["bold"]("text")
        assert result == f"\033[1mtext{RESET}"

    def test_green_with_color(self, f_color):
        result = f_color["green"]("ok")
        assert result == f"\033[32mok{RESET}"

    def test_chaining_red_then_bold(self, f_color):
        """Applying red then bold produces nested ANSI codes."""
        step1 = f_color["red"]("inner")
        step2 = f_color["bold"](step1)
        # bold wraps the already-red text
        assert step2 == f"\033[1m\033[31minner{RESET}{RESET}"

    def test_decoration_no_color(self, f_nocolor):
        result = f_nocolor["bold"]("text")
        assert result == "text"
        assert isinstance(result, Styled)


# =============================================================================
# Extended Color (fg / bg)
# =============================================================================


class TestExtendedColor:
    def test_fg_with_int_256(self, f_color):
        result = f_color["fg"]("hi", 202)
        assert result == f"\033[38;5;202mhi{RESET}"

    def test_fg_with_hex_string(self, f_color):
        result = f_color["fg"]("hi", "#ff8800")
        assert result == f"\033[38;2;255;136;0mhi{RESET}"

    def test_bg_with_named_int(self, f_color):
        result = f_color["bg"]("bg", 42)
        assert result == f"\033[48;5;42mbg{RESET}"

    def test_bg_with_hex(self, f_color):
        result = f_color["bg"]("x", "#00ff00")
        assert result == f"\033[48;2;0;255;0mx{RESET}"

    def test_fg_no_color(self, f_nocolor):
        result = f_nocolor["fg"]("hi", 202)
        assert result == "hi"
        assert "\033[" not in result

    def test_bg_no_color(self, f_nocolor):
        result = f_nocolor["bg"]("x", "#00ff00")
        assert result == "x"


# =============================================================================
# Layout: pad
# =============================================================================


class TestPadFilter:
    def test_pad_left_default(self, f_color):
        result = f_color["pad"]("hi", 10)
        assert result == "hi        "
        assert len(result) == 10

    def test_pad_right(self, f_color):
        result = f_color["pad"]("hi", 10, align="right")
        assert result == "        hi"

    def test_pad_center(self, f_color):
        result = f_color["pad"]("hi", 10, align="center")
        # "hi" is 2 chars, should be roughly centered in 10
        assert len(result) == 10
        assert "hi" in result

    def test_pad_with_ansi_text(self, f_color):
        """Pad should use visible width, not raw string length."""
        colored = f_color["red"]("hi")  # has ANSI codes but visible len = 2
        result = f_color["pad"](colored, 10)
        # The visible length should be 10, raw length will be longer
        assert isinstance(result, Styled)
        # Strip ANSI to check visible padding
        import re

        visible = re.sub(r"\033\[[^m]*m", "", str(result))
        assert len(visible) == 10


# =============================================================================
# Badge
# =============================================================================


class TestBadgeFilter:
    def test_pass_with_color_unicode(self, f_color):
        result = f_color["badge"]("pass")
        # Should be green check icon: \033[32m✓\033[0m
        assert "\033[32m" in result
        assert "\u2713" in result  # check mark

    def test_fail_with_color_unicode(self, f_color):
        result = f_color["badge"]("fail")
        # Should be red cross icon: \033[31m✗\033[0m
        assert "\033[31m" in result
        assert "\u2717" in result  # cross mark

    def test_unknown_status_plain_text(self, f_color):
        result = f_color["badge"]("custom")
        assert result == "custom"

    def test_pass_no_color(self, f_nocolor):
        result = f_nocolor["badge"]("pass")
        assert result == "[PASS]"

    def test_fail_no_color(self, f_nocolor):
        result = f_nocolor["badge"]("fail")
        assert result == "[FAIL]"

    def test_badge_case_insensitive(self, f_nocolor):
        result = f_nocolor["badge"]("PASS")
        assert result == "[PASS]"

    def test_badge_ascii_icons(self, f_ascii):
        """color=True, unicode=False → uses ASCII icon chars."""
        result = f_ascii["badge"]("pass")
        assert "\033[32m" in result
        assert "[ok]" in result  # ASCII fallback for check


# =============================================================================
# Bar
# =============================================================================


class TestBarFilter:
    def test_bar_zero(self, f_color):
        result = f_color["bar"](0.0, width=10)
        assert "\u2591" * 10 in result  # all empty
        assert "0%" in result

    def test_bar_half(self, f_color):
        result = f_color["bar"](0.5, width=10)
        assert "\u2588" * 5 in result  # half filled
        assert "\u2591" * 5 in result  # half empty
        assert "50%" in result

    def test_bar_full(self, f_color):
        result = f_color["bar"](1.0, width=10)
        assert "\u2588" * 10 in result  # all filled
        assert "100%" in result

    def test_bar_no_pct(self, f_color):
        result = f_color["bar"](0.5, width=10, show_pct=False)
        assert "%" not in result

    def test_bar_ascii(self, f_plain):
        """unicode=False uses # and - with brackets."""
        result = f_plain["bar"](0.5, width=10)
        assert "#" * 5 in result
        assert "-" * 5 in result
        assert result.startswith("[")

    def test_bar_clamps(self, f_color):
        """Values outside 0-1 are clamped."""
        result_neg = f_color["bar"](-0.5, width=10)
        assert "0%" in result_neg
        result_over = f_color["bar"](1.5, width=10)
        assert "100%" in result_over


# =============================================================================
# KV
# =============================================================================


class TestKVFilter:
    def test_kv_basic(self, f_color):
        result = f_color["kv"]("Name", "Alice", width=20)
        assert "Name" in result
        assert "Alice" in result
        assert "\u00b7" in result  # middle dot fill

    def test_kv_ascii_fill(self, f_plain):
        """unicode=False uses . instead of middle dot."""
        result = f_plain["kv"]("Key", "Val", width=20)
        assert "." in result
        assert "\u00b7" not in result


# =============================================================================
# Table
# =============================================================================


class TestTableFilter:
    def test_table_list_of_dicts(self, f_color):
        data = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
        result = f_color["table"](data)
        assert "Alice" in result
        assert "Bob" in result
        assert "name" in result
        assert "age" in result

    def test_table_custom_headers(self, f_color):
        data = [{"name": "Alice", "age": "30"}]
        result = f_color["table"](data, headers=["name"])
        assert "name" in result
        assert "age" not in result  # excluded by custom headers

    def test_table_ascii_borders(self, f_plain):
        """unicode=False → ASCII box characters."""
        data = [{"x": "1"}]
        result = f_plain["table"](data)
        assert "+" in result  # ASCII corners
        assert "-" in result  # ASCII horizontal
        assert "|" in result  # ASCII vertical

    def test_table_unicode_borders(self, f_color):
        data = [{"x": "1"}]
        result = f_color["table"](data)
        # Default "light" style uses Unicode box-drawing
        assert "\u250c" in result or "\u2502" in result  # ┌ or │

    def test_table_empty_data(self, f_color):
        result = f_color["table"]([])
        assert result == ""

    def test_table_returns_styled(self, f_color):
        data = [{"a": "1"}]
        result = f_color["table"](data)
        assert isinstance(result, Styled)


# =============================================================================
# Tree
# =============================================================================


class TestTreeFilter:
    def test_tree_nested_dict(self, f_color):
        data = {"root": {"child1": {}, "child2": {"leaf": {}}}}
        result = f_color["tree"](data)
        assert "\u2514" in result  # └ last branch
        assert "\u251c" in result or "\u2514" in result  # connectors present

    def test_tree_ascii(self, f_plain):
        data = {"root": {"child": {}}}
        result = f_plain["tree"](data)
        assert "\\" in result or "|" in result  # ASCII connectors

    def test_tree_non_dict(self, f_color):
        result = f_color["tree"]("just a string")
        assert result == "just a string"

    def test_tree_returns_styled(self, f_color):
        result = f_color["tree"]({"a": {"b": {}}})
        assert isinstance(result, Styled)


# =============================================================================
# IconSet
# =============================================================================


class TestIconSet:
    def test_check_unicode(self):
        icons = IconSet(unicode=True)
        assert icons.check == "\u2713"
        assert isinstance(icons.check, Styled)

    def test_check_ascii(self):
        icons = IconSet(unicode=False)
        assert icons.check == "[ok]"
        assert isinstance(icons.check, Styled)

    def test_cross_unicode(self):
        icons = IconSet(unicode=True)
        assert icons.cross == "\u2717"

    def test_cross_ascii(self):
        icons = IconSet(unicode=False)
        assert icons.cross == "[FAIL]"

    def test_unknown_icon_raises(self):
        icons = IconSet(unicode=True)
        with pytest.raises(AttributeError, match="Unknown icon"):
            icons.nonexistent_icon  # noqa: B018

    def test_unknown_icon_suggestion(self):
        icons = IconSet(unicode=True)
        with pytest.raises(AttributeError, match="did you mean"):
            icons.chekc  # noqa: B018  # close to "check"

    def test_repr(self):
        icons = IconSet(unicode=True)
        assert repr(icons) == "IconSet(unicode=True)"


# =============================================================================
# BoxSet
# =============================================================================


class TestBoxSet:
    def test_round_tl_unicode(self):
        box = BoxSet(unicode=True)
        assert box.round.tl == "\u256d"  # ╭

    def test_ascii_tl(self):
        box = BoxSet(unicode=True)
        assert box.ascii.tl == "+"

    def test_unicode_false_always_ascii(self):
        box = BoxSet(unicode=False)
        # Even requesting "round" returns ASCII
        assert box.round.tl == "+"
        assert box.heavy.tl == "+"

    def test_unknown_style_raises(self):
        box = BoxSet(unicode=True)
        with pytest.raises(AttributeError, match="Unknown box style"):
            box.nonexistent_style  # noqa: B018

    def test_repr(self):
        box = BoxSet(unicode=False)
        assert repr(box) == "BoxSet(unicode=False)"


# =============================================================================
# Syntax
# =============================================================================


class TestSyntaxFilter:
    def test_json_keys_cyan(self, f_color):
        result = f_color["syntax"]('{"name": "Alice"}', language="json")
        assert "\033[36m" in result  # cyan for keys
        assert isinstance(result, Styled)

    def test_json_string_values_green(self, f_color):
        result = f_color["syntax"]('{"name": "Alice"}', language="json")
        assert "\033[32m" in result  # green for string values

    def test_json_numbers_yellow(self, f_color):
        result = f_color["syntax"]('{"age": 30}', language="json")
        assert "\033[33m" in result  # yellow for numbers

    def test_json_booleans_magenta(self, f_color):
        result = f_color["syntax"]('{"active": true}', language="json")
        assert "\033[35m" in result  # magenta for booleans

    def test_json_null_magenta(self, f_color):
        result = f_color["syntax"]('{"value": null}', language="json")
        assert "\033[35m" in result  # magenta for null

    def test_json_braces_dim(self, f_color):
        result = f_color["syntax"]('{"a": 1}', language="json")
        assert "\033[2m" in result  # dim for braces

    def test_json_default_language(self, f_color):
        """Default language parameter is json."""
        result = f_color["syntax"]('{"x": 1}')
        assert "\033[36m" in result  # cyan keys

    def test_yaml_keys_cyan(self, f_color):
        result = f_color["syntax"]("name: Alice", language="yaml")
        assert "\033[36m" in result  # cyan for keys

    def test_yaml_string_values_green(self, f_color):
        result = f_color["syntax"]('name: "Alice"', language="yaml")
        assert "\033[32m" in result  # green for string values

    def test_yaml_numbers_yellow(self, f_color):
        result = f_color["syntax"]("age: 30", language="yaml")
        assert "\033[33m" in result  # yellow for numbers

    def test_yaml_booleans_magenta(self, f_color):
        result = f_color["syntax"]("active: true", language="yaml")
        assert "\033[35m" in result  # magenta for booleans

    def test_yaml_comments_dim(self, f_color):
        result = f_color["syntax"]("# this is a comment", language="yaml")
        assert "\033[2m" in result  # dim for comments

    def test_yml_alias(self, f_color):
        """'yml' is accepted as an alias for yaml."""
        result = f_color["syntax"]("key: 42", language="yml")
        assert "\033[36m" in result  # cyan for keys

    def test_unknown_language_unstyled(self, f_color):
        result = f_color["syntax"]("some content", language="unknown")
        assert result == "some content"
        assert "\033[" not in result
        assert isinstance(result, Styled)

    def test_no_color_returns_plain(self, f_nocolor):
        result = f_nocolor["syntax"]('{"name": "Alice"}', language="json")
        assert "\033[" not in result
        assert result == '{"name": "Alice"}'
        assert isinstance(result, Styled)

    def test_multiline_json(self, f_color):
        content = '{\n  "name": "Alice",\n  "age": 30\n}'
        result = f_color["syntax"](content, language="json")
        assert "\n" in result
        assert "\033[36m" in result  # cyan keys
        assert "\033[33m" in result  # yellow numbers

    def test_multiline_yaml(self, f_color):
        content = "name: Alice\nage: 30\n# comment"
        result = f_color["syntax"](content, language="yaml")
        assert "\n" in result
        assert "\033[36m" in result  # cyan keys

    def test_ansi_injection_sanitized(self, f_color):
        """Dangerous ANSI sequences in input are stripped before highlighting."""
        malicious = '{"key": "\033[2Jclear screen"}'
        result = f_color["syntax"](malicious, language="json")
        # Dangerous cursor/screen control sequence should be stripped
        assert "\033[2J" not in result
        assert "clear screen" in result

    def test_json_key_whitespace_preserved(self, f_color):
        """Whitespace between key and colon is preserved."""
        content = '{"name" : "Alice"}'
        result = f_color["syntax"](content, language="json")
        # The space before colon should be preserved
        assert " :" in result

    def test_yaml_inline_comment(self, f_color):
        """Inline YAML comments are dimmed without corrupting key styling."""
        content = "port: 8080 # default port"
        result = f_color["syntax"](content, language="yaml")
        assert "\033[36m" in result  # cyan for key
        assert "\033[2m" in result  # dim for comment
        assert "# default port" in result or "\033[2m# default port" in result


# =============================================================================
# Integration: Environment with autoescape="terminal"
# =============================================================================


class TestEnvironmentIntegration:
    def test_terminal_filters_registered(self):
        from kida import Environment

        env = Environment(autoescape="terminal", terminal_color="basic", terminal_unicode=True)
        tmpl = env.from_string("{{ x | red }}")
        result = tmpl.render(x="hello")
        assert "\033[31m" in result
        assert "hello" in result

    def test_badge_end_to_end(self):
        from kida import Environment

        env = Environment(autoescape="terminal", terminal_color="basic", terminal_unicode=True)
        tmpl = env.from_string("{{ status | badge }}")
        result = tmpl.render(status="pass")
        assert "\033[32m" in result  # green
        assert "\u2713" in result  # check mark

    def test_columns_global_available(self):
        from kida import Environment

        env = Environment(
            autoescape="terminal",
            terminal_color="basic",
            terminal_unicode=True,
            terminal_width=120,
        )
        tmpl = env.from_string("{{ columns }}")
        result = tmpl.render()
        assert result == "120"

    def test_icons_global_available(self):
        from kida import Environment

        env = Environment(autoescape="terminal", terminal_color="basic", terminal_unicode=True)
        tmpl = env.from_string("{{ icons.check }}")
        result = tmpl.render()
        assert "\u2713" in result

    def test_no_color_mode(self):
        from kida import Environment

        env = Environment(autoescape="terminal", terminal_color="none", terminal_unicode=True)
        tmpl = env.from_string("{{ x | red }}")
        result = tmpl.render(x="hello")
        assert "\033[" not in result
        assert "hello" in result
