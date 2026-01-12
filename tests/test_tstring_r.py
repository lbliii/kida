"""Tests for the r-tag composable regex patterns.

Tests the ComposablePattern class and r() tag function for:
- Pattern composition with automatic non-capturing groups
- ReDoS vulnerability detection
- Syntax validation
- Pattern compilation and matching
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from kida.tstring import ComposablePattern, PatternError, r

# =============================================================================
# ComposablePattern Tests
# =============================================================================


class TestComposablePattern:
    """Tests for ComposablePattern class."""

    def test_basic_creation(self) -> None:
        """Pattern can be created with valid regex."""
        pattern = ComposablePattern(r"[a-zA-Z_][a-zA-Z0-9_]*")
        assert pattern.pattern == r"[a-zA-Z_][a-zA-Z0-9_]*"

    def test_compile_returns_pattern(self) -> None:
        """compile() returns a compiled re.Pattern."""
        pattern = ComposablePattern(r"\d+")
        compiled = pattern.compile()
        assert isinstance(compiled, re.Pattern)
        assert compiled.match("123") is not None
        assert compiled.match("abc") is None

    def test_compile_caches_result(self) -> None:
        """compile() caches result for flags=0."""
        pattern = ComposablePattern(r"\d+")
        compiled1 = pattern.compile()
        compiled2 = pattern.compile()
        assert compiled1 is compiled2

    def test_compile_with_flags_not_cached(self) -> None:
        """compile() with flags doesn't use cache."""
        pattern = ComposablePattern(r"[a-z]+")
        compiled_default = pattern.compile()
        compiled_ignorecase = pattern.compile(re.IGNORECASE)
        # Different objects
        assert compiled_default is not compiled_ignorecase
        # Different behavior
        assert compiled_default.match("ABC") is None
        assert compiled_ignorecase.match("ABC") is not None

    def test_or_operator_combines_patterns(self) -> None:
        """| operator combines patterns with non-capturing groups."""
        name = ComposablePattern(r"[a-zA-Z_]+")
        number = ComposablePattern(r"\d+")
        combined = name | number
        assert combined.pattern == r"(?:[a-zA-Z_]+)|(?:\d+)"

    def test_or_with_string(self) -> None:
        """| operator works with raw string."""
        name = ComposablePattern(r"[a-zA-Z_]+")
        combined = name | r"\d+"
        assert combined.pattern == r"(?:[a-zA-Z_]+)|(?:\d+)"

    def test_chained_or(self) -> None:
        """Multiple | operations chain correctly."""
        a = ComposablePattern(r"a+")
        b = ComposablePattern(r"b+")
        c = ComposablePattern(r"c+")
        combined = a | b | c
        assert "(?:a+)" in combined.pattern
        assert "(?:b+)" in combined.pattern
        assert "(?:c+)" in combined.pattern

    def test_combined_pattern_matches(self) -> None:
        """Combined pattern matches correctly."""
        name = ComposablePattern(r"[a-zA-Z_]+")
        number = ComposablePattern(r"\d+")
        combined = name | number
        compiled = combined.compile()

        assert compiled.match("hello") is not None
        assert compiled.match("123") is not None
        assert compiled.match("@@@") is None

    def test_repr(self) -> None:
        """repr() shows pattern."""
        pattern = ComposablePattern(r"\d+")
        assert repr(pattern) == "ComposablePattern('\\\\d+')"


class TestComposablePatternValidation:
    """Tests for pattern validation."""

    def test_invalid_regex_raises(self) -> None:
        """Invalid regex syntax raises PatternError."""
        with pytest.raises(PatternError, match="Invalid regex syntax"):
            ComposablePattern(r"[unclosed")

    def test_unbalanced_parens_raises(self) -> None:
        """Unbalanced parentheses raise PatternError."""
        with pytest.raises(PatternError, match="Invalid regex syntax"):
            ComposablePattern(r"(unclosed")

    def test_redos_nested_plus_raises(self) -> None:
        """Nested quantifiers (a+)+ are detected as ReDoS risk."""
        with pytest.raises(PatternError, match="ReDoS"):
            ComposablePattern(r"(a+)+")

    def test_redos_nested_star_plus_raises(self) -> None:
        """Nested quantifiers (a*)+ are detected as ReDoS risk."""
        with pytest.raises(PatternError, match="ReDoS"):
            ComposablePattern(r"(a*)+")

    def test_redos_dotstar_plus_raises(self) -> None:
        """Pattern (.*)+  is detected as ReDoS risk."""
        with pytest.raises(PatternError, match="ReDoS"):
            ComposablePattern(r"(.*)+")

    def test_safe_patterns_pass(self) -> None:
        """Safe patterns pass validation."""
        # These should not raise
        ComposablePattern(r"[a-z]+")  # Simple quantifier
        ComposablePattern(r"\d{1,10}")  # Bounded quantifier
        ComposablePattern(r"(a|b)+")  # Alternation with quantifier
        ComposablePattern(r"(?:foo|bar)+")  # Non-capturing with quantifier

    def test_validation_can_be_disabled(self) -> None:
        """validate=False skips ReDoS check."""
        # This would normally raise
        pattern = ComposablePattern(r"(a+)+", validate=False)
        assert pattern.pattern == r"(a+)+"


# =============================================================================
# r() Tag Tests
# =============================================================================


def _make_template(strings: tuple[str, ...], *values: str) -> SimpleNamespace:
    """Create a mock t-string template for testing."""
    interpolations = tuple(SimpleNamespace(value=v) for v in values)
    return SimpleNamespace(strings=strings, interpolations=interpolations)


class TestRTag:
    """Tests for the r() tag function."""

    def test_simple_pattern(self) -> None:
        """r-tag with no interpolations returns pattern as-is."""
        template = _make_template((r"\d+",))
        result = r(template)
        assert result.pattern == r"\d+"

    def test_single_interpolation(self) -> None:
        """Single interpolation is wrapped in non-capturing group."""
        name_pat = r"[a-zA-Z_]+"
        template = _make_template(("", ""), name_pat)
        result = r(template)
        assert result.pattern == f"(?:{name_pat})"

    def test_multiple_interpolations(self) -> None:
        """Multiple interpolations are each wrapped."""
        name_pat = r"[a-zA-Z_]+"
        number_pat = r"\d+"
        template = _make_template(("", "|", ""), name_pat, number_pat)
        result = r(template)
        assert result.pattern == f"(?:{name_pat})|(?:{number_pat})"

    def test_mixed_literal_and_interpolation(self) -> None:
        """Literal parts and interpolations combine correctly."""
        digits_pat = r"\d+"
        template = _make_template(("prefix_", "_suffix"), digits_pat)
        result = r(template)
        assert result.pattern == f"prefix_(?:{digits_pat})_suffix"

    def test_composable_pattern_interpolation(self) -> None:
        """ComposablePattern can be interpolated."""
        name_pattern = ComposablePattern(r"[a-zA-Z_]+")
        template = _make_template(("^", "$"), name_pattern)
        result = r(template)
        assert result.pattern == r"^(?:[a-zA-Z_]+)$"

    def test_result_can_be_compiled(self) -> None:
        """r-tag result can be compiled and used for matching."""
        name_pat = r"[a-zA-Z_][a-zA-Z0-9_]*"
        integer_pat = r"\d+"
        template = _make_template(("", "|", ""), name_pat, integer_pat)
        result = r(template)
        compiled = result.compile()

        assert compiled.match("variable_name") is not None
        assert compiled.match("123") is not None
        assert compiled.match("@@@") is None

    def test_nested_composition(self) -> None:
        """r-tag results can be composed further."""
        name_pat = r"[a-zA-Z_]+"
        template1 = _make_template(("", ""), name_pat)
        name_pattern = r(template1)

        integer_pat = r"\d+"
        template2 = _make_template(("", "|", ""), name_pattern, integer_pat)
        combined = r(template2)

        compiled = combined.compile()
        assert compiled.match("hello") is not None
        assert compiled.match("123") is not None

    def test_type_error_on_invalid_template(self) -> None:
        """r-tag raises TypeError for non-template input."""
        with pytest.raises(TypeError, match="t-string template"):
            r("not a template")  # type: ignore

    def test_type_error_on_invalid_interpolation(self) -> None:
        """r-tag raises TypeError for non-string/pattern interpolation."""
        template = _make_template(("", ""), 123)  # Integer, not string
        with pytest.raises(TypeError, match="str or ComposablePattern"):
            r(template)

    def test_redos_in_interpolation_detected(self) -> None:
        """ReDoS in final composed pattern is detected."""
        # The r-tag wraps interpolations in (?:...), so (a+)+ becomes ((?:a+))+
        # which is still potentially dangerous. Test with a pattern that
        # remains dangerous after wrapping.
        dangerous_pat = r"(a+)+"  # Already dangerous
        template = _make_template(("", ""), dangerous_pat)
        with pytest.raises(PatternError, match="ReDoS"):
            r(template)


class TestRTagRealWorldPatterns:
    """Tests with realistic lexer patterns."""

    def test_identifier_pattern(self) -> None:
        """Typical identifier pattern works."""
        name_pat = r"[a-zA-Z_][a-zA-Z0-9_]*"
        template = _make_template(("^", "$"), name_pat)
        result = r(template)
        compiled = result.compile()

        assert compiled.match("valid_name") is not None
        assert compiled.match("_private") is not None
        assert compiled.match("123invalid") is None

    def test_string_literal_pattern(self) -> None:
        """String literal pattern works."""
        single_pat = r"'[^']*'"
        double_pat = r'"[^"]*"'
        template = _make_template(("", "|", ""), single_pat, double_pat)
        result = r(template)
        compiled = result.compile()

        assert compiled.match("'hello'") is not None
        assert compiled.match('"world"') is not None
        assert compiled.match("unquoted") is None

    def test_number_pattern(self) -> None:
        """Number pattern (integer or float) works."""
        integer_pat = r"\d+"
        float_pat = r"\d+\.\d+"
        # Float first (longer match)
        template = _make_template(("", "|", ""), float_pat, integer_pat)
        result = r(template)
        compiled = result.compile()

        match_int = compiled.match("123")
        assert match_int is not None
        assert match_int.group() == "123"

        match_float = compiled.match("123.456")
        assert match_float is not None
        assert match_float.group() == "123.456"

    def test_delimiter_pattern(self) -> None:
        """Template delimiter pattern works."""
        var_start_pat = r"\{\{"
        block_start_pat = r"\{%"
        comment_start_pat = r"\{#"
        template = _make_template(
            ("(", "|", "|", ")"),
            var_start_pat,
            block_start_pat,
            comment_start_pat,
        )
        result = r(template)
        compiled = result.compile()

        assert compiled.search("Hello {{ name }}") is not None
        assert compiled.search("{% if x %}") is not None
        assert compiled.search("{# comment #}") is not None
        assert compiled.search("No delimiters") is None
