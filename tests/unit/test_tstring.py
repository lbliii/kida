"""Unit tests for kida.tstring — k-tag and r-tag."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from kida.tstring import ComposablePattern, PatternError, k, r

# ---------------------------------------------------------------------------
# Helpers — build SimpleNamespace t-string stand-ins
# ---------------------------------------------------------------------------


def _make_tstr(strings: list[str], interpolations: list[object]) -> SimpleNamespace:
    return SimpleNamespace(
        strings=strings,
        interpolations=[SimpleNamespace(value=v) for v in interpolations],
    )


# ---------------------------------------------------------------------------
# k-tag: basic escaping
# ---------------------------------------------------------------------------


class TestKTag:
    def test_plain_value_escaped(self) -> None:
        tmpl = _make_tstr(["Hello ", "!"], ["<World>"])
        assert k(tmpl) == "Hello &lt;World&gt;!"

    def test_html_interface_respected(self) -> None:
        class HtmlLike:
            def __html__(self) -> str:
                return "<b>safe</b>"

        tmpl = _make_tstr(["Welcome ", "!"], [HtmlLike()])
        assert k(tmpl) == "Welcome <b>safe</b>!"

    def test_empty_template(self) -> None:
        tmpl = _make_tstr([""], [])
        assert k(tmpl) == ""

    def test_no_interpolations(self) -> None:
        tmpl = _make_tstr(["just text"], [])
        assert k(tmpl) == "just text"

    def test_integer_interpolation(self) -> None:
        tmpl = _make_tstr(["count: ", ""], [42])
        assert k(tmpl) == "count: 42"

    def test_float_interpolation(self) -> None:
        tmpl = _make_tstr(["pi: ", ""], [3.14])
        assert k(tmpl) == "pi: 3.14"

    def test_none_interpolation(self) -> None:
        tmpl = _make_tstr(["value: ", ""], [None])
        assert k(tmpl) == "value: None"

    def test_bool_interpolation(self) -> None:
        tmpl = _make_tstr(["flag: ", ""], [True])
        assert k(tmpl) == "flag: True"

    def test_multiple_interpolations(self) -> None:
        # Strings are literal (not escaped), only interpolations are escaped
        tmpl = _make_tstr(["Hello ", " and ", "!"], ["<Alice>", "<Bob>"])
        assert k(tmpl) == "Hello &lt;Alice&gt; and &lt;Bob&gt;!"

    def test_ampersand_escaped(self) -> None:
        tmpl = _make_tstr(["", ""], ["rock & roll"])
        assert k(tmpl) == "rock &amp; roll"

    def test_quote_escaped(self) -> None:
        tmpl = _make_tstr(["", ""], ['say "hello"'])
        result = k(tmpl)
        assert "&quot;" in result or "&#34;" in result

    def test_adjacent_interpolations(self) -> None:
        """Strings list has empty string between consecutive interpolations."""
        tmpl = _make_tstr(["", "", ""], ["<a>", "<b>"])
        assert k(tmpl) == "&lt;a&gt;&lt;b&gt;"


# ---------------------------------------------------------------------------
# r-tag: composable regex patterns
# ---------------------------------------------------------------------------


class TestRTag:
    def test_basic_composition(self) -> None:
        name_pat = "[a-zA-Z_]+"
        tmpl = _make_tstr(["", ""], [name_pat])
        result = r(tmpl)
        assert isinstance(result, ComposablePattern)
        assert result.compile().match("hello")

    def test_two_patterns_composed(self) -> None:
        tmpl = _make_tstr(["", "|", ""], ["[a-z]+", r"\d+"])
        result = r(tmpl)
        assert result.compile().match("abc")
        assert result.compile().match("123")

    def test_composable_pattern_interpolation(self) -> None:
        pat = ComposablePattern("[a-z]+")
        tmpl = _make_tstr(["^", "$"], [pat])
        result = r(tmpl)
        assert result.compile().match("hello")

    def test_invalid_type_raises(self) -> None:
        tmpl = _make_tstr(["", ""], [42])
        with pytest.raises(TypeError, match="str or ComposablePattern"):
            r(tmpl)

    def test_not_template_raises(self) -> None:
        with pytest.raises(TypeError, match="t-string template"):
            r("not a template")  # type: ignore[arg-type]

    def test_empty_pattern(self) -> None:
        tmpl = _make_tstr([""], [])
        result = r(tmpl)
        assert result.pattern == ""


# ---------------------------------------------------------------------------
# ComposablePattern
# ---------------------------------------------------------------------------


class TestComposablePattern:
    def test_compile_caches(self) -> None:
        pat = ComposablePattern("[a-z]+")
        compiled1 = pat.compile()
        compiled2 = pat.compile()
        assert compiled1 is compiled2

    def test_compile_with_flags_not_cached(self) -> None:
        import re

        pat = ComposablePattern("[a-z]+")
        compiled_default = pat.compile()
        compiled_ignorecase = pat.compile(re.IGNORECASE)
        assert compiled_default is not compiled_ignorecase
        assert compiled_ignorecase.match("ABC")

    def test_or_operator(self) -> None:
        a = ComposablePattern("[a-z]+")
        b = ComposablePattern(r"\d+")
        combined = a | b
        assert "(?:" in combined.pattern
        assert combined.compile().match("abc")
        assert combined.compile().match("123")

    def test_or_with_string(self) -> None:
        a = ComposablePattern("[a-z]+")
        combined = a | r"\d+"
        assert combined.compile().match("abc")
        assert combined.compile().match("123")

    def test_repr(self) -> None:
        pat = ComposablePattern("[a-z]+")
        assert repr(pat) == "ComposablePattern('[a-z]+')"

    def test_pattern_property(self) -> None:
        pat = ComposablePattern("[a-z]+")
        assert pat.pattern == "[a-z]+"

    def test_invalid_syntax_raises(self) -> None:
        with pytest.raises(PatternError, match="Invalid regex syntax"):
            ComposablePattern("[invalid")

    def test_redos_detection(self) -> None:
        with pytest.raises(PatternError, match="ReDoS"):
            ComposablePattern("(a+)+")

    def test_redos_skip_validation(self) -> None:
        # Should not raise when validate=False
        pat = ComposablePattern("(a+)+", validate=False)
        assert pat.pattern == "(a+)+"
