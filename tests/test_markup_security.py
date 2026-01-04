"""Security tests for Markup and HTML escaping.

Tests XSS vectors, Unicode edge cases, and context-specific escaping.
Based on OWASP XSS Filter Evasion Cheat Sheet and MarkupSafe test patterns.

All regex patterns used are O(n) linear time (no ReDoS risk).

Test Categories:
- NUL byte handling: 5+ tests
- Unicode edge cases: 8+ tests
- Double-escape prevention: 4+ tests
- Markup operations: 12+ tests
- XSS vectors: 15+ tests
- xmlattr: 8+ tests
- striptags/unescape: 8+ tests
- js_escape: 10+ tests
- url_is_safe: 12+ tests
- format_html: 4+ tests
- SoftStr: 5+ tests
"""

import warnings

import pytest

from kida import Markup
from kida.utils.html import (
    JSString,
    SoftStr,
    css_escape,
    format_html,
    html_escape,
    js_escape,
    safe_url,
    strip_tags,
    url_is_safe,
    xmlattr,
)

# =============================================================================
# NUL Byte Handling Tests
# =============================================================================


class TestNULByteHandling:
    """NUL bytes can bypass filters in some contexts."""

    def test_nul_stripped_from_output(self) -> None:
        """NUL bytes should be removed entirely."""
        assert "\x00" not in html_escape("\x00<script>")

    def test_nul_before_tag(self) -> None:
        """NUL before tag name still escapes."""
        result = html_escape("\x00<script>")
        assert "&lt;script&gt;" in result

    def test_nul_in_tag(self) -> None:
        """NUL within tag name."""
        result = html_escape("<scr\x00ipt>")
        assert "&lt;" in result
        assert "\x00" not in result

    def test_nul_in_attribute(self) -> None:
        """NUL in attribute value."""
        result = html_escape('value="\x00test"')
        assert "\x00" not in result

    def test_multiple_nul_bytes(self) -> None:
        """Multiple NUL bytes all removed."""
        result = html_escape("\x00\x00<script>\x00")
        assert "\x00" not in result
        assert "&lt;script&gt;" in result

    def test_nul_only_string(self) -> None:
        """String with only NUL bytes becomes empty."""
        result = html_escape("\x00\x00\x00")
        assert result == ""

    def test_nul_between_special_chars(self) -> None:
        """NUL bytes between special characters are stripped."""
        result = html_escape("<\x00&\x00>")
        assert result == "&lt;&amp;&gt;"


# =============================================================================
# Unicode Edge Cases Tests
# =============================================================================


class TestUnicodeEdgeCases:
    """Unicode edge cases that could enable attacks."""

    def test_zero_width_joiner(self) -> None:
        """Zero-width joiner in tag name - still escapes < and >."""
        result = html_escape("<scr\u200dipt>")
        assert "&lt;" in result
        assert "&gt;" in result

    def test_zero_width_space(self) -> None:
        """Zero-width space - still escapes < and >."""
        result = html_escape("<\u200bscript>")
        assert "&lt;" in result

    def test_rtl_override_preserved(self) -> None:
        """RTL override should not crash and pass through."""
        result = html_escape("\u202ealert(1)")
        assert isinstance(result, str)
        assert "\u202e" in result  # RTL preserved, no < to escape

    def test_combining_characters(self) -> None:
        """Combining characters shouldn't break escaping."""
        result = html_escape("te\u0301st<b>")  # e + combining acute
        assert "&lt;b&gt;" in result
        assert "te\u0301st" in result  # Preserved

    def test_surrogate_pairs(self) -> None:
        """Emoji and other surrogate pairs."""
        result = html_escape("<b>Hello 👋 World</b>")
        assert "👋" in result
        assert "&lt;b&gt;" in result

    def test_fullwidth_brackets_passthrough(self) -> None:
        """Fullwidth brackets pass through (different codepoints).

        U+FF1C (＜) and U+FF1E (＞) are NOT HTML angle brackets.
        They are CJK fullwidth forms and should pass through unchanged.

        Note: Some browsers may still render these as angle-like characters,
        but they do NOT function as HTML tag delimiters. This is the correct
        behavior per HTML5 spec.
        """
        result = html_escape("\uff1cscript\uff1e")
        # Fullwidth brackets pass through unchanged
        assert "\uff1c" in result
        assert "\uff1e" in result
        # Real angle brackets would be escaped
        assert "&lt;" not in result

    def test_overlong_utf8_rejected(self) -> None:
        """Overlong UTF-8 sequences (if present) don't bypass escaping.

        Python 3 strings are decoded UTF-8, so overlong sequences would
        have already been rejected at decode time. This test documents
        that behavior.
        """
        # This is the normal < character
        result = html_escape("<")
        assert result == "&lt;"

    def test_bom_character(self) -> None:
        """BOM character should not break escaping."""
        result = html_escape("\ufeff<script>")
        assert "&lt;script&gt;" in result
        assert "\ufeff" in result  # BOM preserved


# =============================================================================
# Double-Escape Prevention Tests
# =============================================================================


class TestDoubleEscapePrevention:
    """Ensure no double-escaping occurs."""

    def test_markup_not_double_escaped(self) -> None:
        """Markup objects should not be re-escaped."""
        safe = Markup("&lt;already escaped&gt;")
        result = html_escape(safe)
        assert result == "&lt;already escaped&gt;"
        assert "&amp;lt;" not in result

    def test_entity_not_double_escaped(self) -> None:
        """Existing entities should not be re-escaped via Markup."""
        m = Markup("&amp;")
        result = str(m + "")  # Trigger concatenation
        assert result == "&amp;"
        assert "&amp;amp;" not in result

    def test_nested_markup_format(self) -> None:
        """Nested Markup.format() operations."""
        inner = Markup("<span>{}</span>").format("<xss>")
        outer = Markup("<div>{}</div>").format(inner)
        assert "<span>" in str(outer)
        assert "&lt;xss&gt;" in str(outer)
        assert "<xss>" not in str(outer)

    def test_triple_nested_format(self) -> None:
        """Triple nested formatting still prevents double-escape."""
        a = Markup("<a>{}</a>").format("<x>")
        b = Markup("<b>{}</b>").format(a)
        c = Markup("<c>{}</c>").format(b)
        result = str(c)
        assert "<a>" in result
        assert "<b>" in result
        assert "<c>" in result
        assert "&lt;x&gt;" in result
        assert result.count("&lt;") == 1  # Only <x> escaped


# =============================================================================
# Markup Operations Tests
# =============================================================================


class TestMarkupOperations:
    """Markup class operations maintain safety invariants."""

    def test_add_escapes_plain_string(self) -> None:
        """+ operator escapes plain strings."""
        m = Markup("<b>") + "<script>"
        assert "&lt;script&gt;" in str(m)
        assert "<b>" in str(m)

    def test_radd_escapes_plain_string(self) -> None:
        """Reverse + escapes plain strings."""
        m = "<script>" + Markup("<b>")
        assert "&lt;script&gt;" in str(m)
        assert "<b>" in str(m)

    def test_mod_escapes_string_arg(self) -> None:
        """% formatting escapes string arguments."""
        m = Markup("<p>%s</p>") % "<script>"
        assert "&lt;script&gt;" in str(m)

    def test_mod_escapes_tuple_args(self) -> None:
        """% formatting escapes tuple arguments."""
        m = Markup("<p>%s %s</p>") % ("<a>", "<b>")
        assert "&lt;a&gt;" in str(m)
        assert "&lt;b&gt;" in str(m)

    def test_mod_escapes_dict_args(self) -> None:
        """% formatting escapes dict arguments."""
        m = Markup("<p>%(x)s</p>") % {"x": "<script>"}
        assert "&lt;script&gt;" in str(m)

    def test_format_escapes_positional(self) -> None:
        """format() escapes positional arguments."""
        m = Markup("<p>{} {}</p>").format("<a>", "<b>")
        assert "&lt;a&gt;" in str(m)
        assert "&lt;b&gt;" in str(m)

    def test_format_escapes_keyword(self) -> None:
        """format() escapes keyword arguments."""
        m = Markup("<p>{x}</p>").format(x="<script>")
        assert "&lt;script&gt;" in str(m)

    def test_join_escapes_elements(self) -> None:
        """join() escapes non-Markup elements."""
        m = Markup(", ").join(["<a>", "<b>", "<c>"])
        result = str(m)
        assert "&lt;a&gt;" in result
        assert "&lt;b&gt;" in result
        assert "&lt;c&gt;" in result

    def test_join_preserves_markup_elements(self) -> None:
        """join() preserves Markup elements."""
        m = Markup(", ").join([Markup("<b>"), "plain", Markup("<i>")])
        result = str(m)
        assert "<b>" in result  # Preserved
        assert "<i>" in result  # Preserved
        assert "plain" in result  # Not escaped (no special chars)

    def test_mul_returns_markup(self) -> None:
        """Multiplication returns Markup."""
        m = Markup("<b>") * 3
        assert isinstance(m, Markup)
        assert str(m) == "<b><b><b>"

    def test_string_methods_return_markup(self) -> None:
        """String methods return Markup instances."""
        m = Markup("<B>Test</B>")
        assert isinstance(m.lower(), Markup)
        assert isinstance(m.upper(), Markup)
        assert isinstance(m.strip(), Markup)
        assert isinstance(m.replace("B", "I"), Markup)


# =============================================================================
# Known XSS Vectors Tests
# =============================================================================


class TestKnownXSSVectors:
    """Known XSS attack patterns from OWASP and security research."""

    @pytest.mark.parametrize(
        ("vector", "must_escape"),
        [
            # Basic script injection
            ("<script>alert(1)</script>", True),
            ("<SCRIPT>alert(1)</SCRIPT>", True),
            ("<ScRiPt>alert(1)</ScRiPt>", True),
            # Event handlers (angle brackets must be escaped)
            ("<img src=x onerror=alert(1)>", True),
            ("<svg onload=alert(1)>", True),
            ("<body onload=alert(1)>", True),
            ("<div onmouseover=alert(1)>", True),
            # Breaking out of attributes
            ('"><script>alert(1)</script>', True),
            ("'><script>alert(1)</script>", True),
            # Protocol handlers (contain angle brackets)
            ("<a href=javascript:alert(1)>", True),
            ("<iframe src=javascript:alert(1)>", True),
            # Nested/malformed tags
            ("<<script>script>alert(1)<</script>/script>", True),
            ("<script<script>>alert(1)</script>", True),
            # Character encoding tricks
            ("<script>alert(String.fromCharCode(88,83,83))</script>", True),
            # Data URLs with script (contain angle brackets)
            ("<a href='data:text/html,<script>alert(1)</script>'>", True),
        ],
    )
    def test_xss_vectors_escaped(self, vector: str, must_escape: bool) -> None:
        """Common XSS vectors should be safely escaped."""
        result = html_escape(vector)
        if must_escape:
            # Should not contain unescaped angle brackets
            assert "<script>" not in result.lower()
            assert "<img" not in result.lower() or "onerror" not in result.lower()
            # Should contain escaped characters
            assert "&lt;" in result


# =============================================================================
# xmlattr Tests
# =============================================================================


class TestXmlattr:
    """xmlattr() function tests."""

    def test_basic_attributes(self) -> None:
        """Basic attribute generation."""
        result = str(xmlattr({"class": "btn", "id": "submit"}, allow_events=True))
        assert 'class="btn"' in result
        assert 'id="submit"' in result

    def test_escapes_quotes_in_values(self) -> None:
        """Double quotes in values must be escaped."""
        result = str(xmlattr({"data-value": 'test"value'}, allow_events=True))
        assert "&quot;" in result
        assert 'data-value="test&quot;value"' in result

    def test_escapes_angle_brackets(self) -> None:
        """Angle brackets in values must be escaped."""
        result = str(xmlattr({"title": "<script>alert(1)</script>"}, allow_events=True))
        assert "&lt;" in result
        assert "<script>" not in result

    def test_escapes_ampersand(self) -> None:
        """Ampersands in values must be escaped."""
        result = str(xmlattr({"data-query": "a=1&b=2"}, allow_events=True))
        assert "&amp;" in result

    def test_none_values_skipped(self) -> None:
        """None values should be omitted."""
        result = str(xmlattr({"class": "btn", "disabled": None}, allow_events=True))
        assert "class" in result
        assert "disabled" not in result

    def test_empty_dict(self) -> None:
        """Empty dict returns empty Markup."""
        result = xmlattr({})
        assert str(result) == ""
        assert isinstance(result, Markup)

    def test_boolean_false_included(self) -> None:
        """Boolean False should be included (not None)."""
        result = str(xmlattr({"data-active": False}, allow_events=True))
        assert "data-active" in result

    def test_event_handler_warning(self) -> None:
        """Event handler attributes should trigger warning by default."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            xmlattr({"onclick": "alert(1)"})
            assert len(w) == 1
            assert "onclick" in str(w[0].message)
            assert "JavaScript" in str(w[0].message)

    def test_event_handler_allow_events(self) -> None:
        """allow_events=True suppresses warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = str(xmlattr({"onclick": "handler()"}, allow_events=True))
            assert len(w) == 0
            assert "onclick" in result

    def test_event_handler_strip_events(self) -> None:
        """strip_events=True removes event handlers."""
        result = str(xmlattr({"onclick": "alert(1)", "class": "btn"}, strip_events=True))
        assert "onclick" not in result
        assert "class" in result

    def test_invalid_attr_name_strict(self) -> None:
        """Invalid attribute names raise ValueError in strict mode."""
        with pytest.raises(ValueError, match="Invalid attribute name"):
            xmlattr({"invalid name": "value"})

    def test_invalid_attr_name_non_strict(self) -> None:
        """Invalid attribute names are skipped with warning in non-strict mode."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = str(xmlattr({"invalid name": "value", "valid": "ok"}, strict=False))
            assert len(w) == 1
            assert "Invalid attribute name" in str(w[0].message)
            assert "invalid" not in result
            assert "valid" in result


# =============================================================================
# striptags Tests
# =============================================================================


class TestStriptags:
    """striptags method tests.

    Note: striptags is for DISPLAY ONLY, not security. It removes visible
    tags from content for rendering purposes. For security, always escape
    user input with html_escape() or use Markup properly.
    """

    def test_basic_strip(self) -> None:
        """Basic tag stripping."""
        m = Markup("<p>Hello <b>World</b></p>")
        assert m.striptags() == "Hello World"

    def test_preserves_text(self) -> None:
        """Text content is preserved."""
        m = Markup("<div><span>Keep this</span></div>")
        assert "Keep this" in m.striptags()

    def test_nested_tags(self) -> None:
        """Nested tags are all stripped."""
        m = Markup("<div><p><b><i>Deep</i></b></p></div>")
        assert m.striptags() == "Deep"

    def test_malformed_tags(self) -> None:
        """Malformed tags handled best-effort (display only)."""
        m = Markup("<div><p>Text</div>")
        result = m.striptags()
        assert "Text" in result


# =============================================================================
# unescape Tests
# =============================================================================


class TestUnescape:
    """unescape method tests."""

    def test_basic_unescape(self) -> None:
        """Basic entity unescaping."""
        m = Markup("&lt;script&gt;")
        assert m.unescape() == "<script>"

    def test_returns_plain_str(self) -> None:
        """unescape returns plain str, not Markup."""
        m = Markup("&lt;b&gt;")
        result = m.unescape()
        assert not isinstance(result, Markup)
        assert isinstance(result, str)

    def test_numeric_entities(self) -> None:
        """Numeric entities are unescaped."""
        m = Markup("&#60;&#62;")
        assert m.unescape() == "<>"

    def test_named_entities(self) -> None:
        """Named entities are unescaped."""
        m = Markup("&amp;&quot;&#39;")
        assert m.unescape() == "&\"'"


# =============================================================================
# JavaScript Escaping Tests
# =============================================================================


class TestJSEscape:
    """JavaScript string escaping tests."""

    def test_basic_string(self) -> None:
        """Basic string passes through."""
        assert js_escape("Hello World") == "Hello World"

    def test_double_quotes(self) -> None:
        """Double quotes are escaped."""
        result = js_escape('Hello "World"')
        assert '\\"' in result
        assert result == 'Hello \\"World\\"'

    def test_single_quotes(self) -> None:
        """Single quotes are escaped."""
        result = js_escape("Hello 'World'")
        assert "\\'" in result

    def test_backslash(self) -> None:
        """Backslashes are escaped."""
        result = js_escape("path\\to\\file")
        assert "\\\\" in result

    def test_newlines(self) -> None:
        """Newlines are escaped."""
        result = js_escape("line1\nline2")
        assert "\\n" in result
        assert "\n" not in result

    def test_script_tag_breakout(self) -> None:
        """</script> cannot break out of script context."""
        result = js_escape("</script>")
        assert "</script>" not in result
        assert "\\x3c" in result

    def test_template_literal_backtick(self) -> None:
        """Backticks are escaped (template literals)."""
        result = js_escape("`template`")
        assert "\\`" in result

    def test_template_literal_interpolation(self) -> None:
        """${...} interpolation is escaped."""
        result = js_escape("${user.name}")
        assert "\\$" in result

    def test_line_separator(self) -> None:
        """U+2028 line separator is escaped."""
        result = js_escape("line\u2028break")
        assert "\\u2028" in result
        assert "\u2028" not in result

    def test_paragraph_separator(self) -> None:
        """U+2029 paragraph separator is escaped."""
        result = js_escape("para\u2029break")
        assert "\\u2029" in result
        assert "\u2029" not in result

    def test_nul_byte(self) -> None:
        """NUL bytes are escaped (not stripped in JS context)."""
        result = js_escape("test\x00value")
        assert "\\x00" in result


class TestJSString:
    """JSString class tests."""

    def test_basic_jsstring(self) -> None:
        """JSString wraps a string."""
        s = JSString("test")
        assert str(s) == "test"

    def test_repr(self) -> None:
        """JSString has informative repr."""
        s = JSString("test")
        assert "JSString" in repr(s)
        assert "test" in repr(s)


# =============================================================================
# CSS Escaping Tests
# =============================================================================


class TestCSSEscape:
    """CSS context escaping tests."""

    def test_basic_string(self) -> None:
        """Basic string passes through."""
        assert css_escape("test") == "test"

    def test_quotes(self) -> None:
        """Quotes are escaped."""
        assert '\\"' in css_escape('test"value')
        assert "\\'" in css_escape("test'value")

    def test_parentheses(self) -> None:
        """Parentheses are escaped (protect url())."""
        result = css_escape("url(attack)")
        assert "\\(" in result
        assert "\\)" in result

    def test_angle_brackets(self) -> None:
        """Angle brackets are escaped."""
        result = css_escape("<script>")
        assert "\\3c " in result
        assert "\\3e " in result

    def test_nul_stripped(self) -> None:
        """NUL bytes are stripped in CSS context."""
        result = css_escape("test\x00value")
        assert "\x00" not in result


# =============================================================================
# URL Validation Tests
# =============================================================================


class TestURLIsSafe:
    """URL protocol validation tests."""

    def test_http_safe(self) -> None:
        """HTTP URLs are safe."""
        assert url_is_safe("http://example.com")
        assert url_is_safe("HTTP://EXAMPLE.COM")

    def test_https_safe(self) -> None:
        """HTTPS URLs are safe."""
        assert url_is_safe("https://example.com/path?query=1")

    def test_mailto_safe(self) -> None:
        """mailto: URLs are safe."""
        assert url_is_safe("mailto:user@example.com")

    def test_tel_safe(self) -> None:
        """tel: URLs are safe."""
        assert url_is_safe("tel:+1234567890")

    def test_relative_safe(self) -> None:
        """Relative URLs are safe."""
        assert url_is_safe("/path/to/page")
        assert url_is_safe("./relative")
        assert url_is_safe("../parent")
        assert url_is_safe("#anchor")
        assert url_is_safe("?query=param")

    def test_protocol_relative_safe(self) -> None:
        """Protocol-relative URLs are safe."""
        assert url_is_safe("//example.com/path")

    def test_javascript_unsafe(self) -> None:
        """javascript: URLs are unsafe."""
        assert not url_is_safe("javascript:alert(1)")
        assert not url_is_safe("JAVASCRIPT:alert(1)")
        assert not url_is_safe("JavaScript:void(0)")

    def test_vbscript_unsafe(self) -> None:
        """vbscript: URLs are unsafe."""
        assert not url_is_safe("vbscript:msgbox(1)")

    def test_data_unsafe_by_default(self) -> None:
        """data: URLs are unsafe by default."""
        assert not url_is_safe("data:text/html,<script>alert(1)</script>")

    def test_data_safe_with_flag(self) -> None:
        """data: URLs can be allowed with allow_data=True."""
        assert url_is_safe("data:image/png;base64,ABC123", allow_data=True)

    def test_whitespace_stripped(self) -> None:
        """Whitespace is stripped before validation."""
        assert not url_is_safe("  javascript:alert(1)  ")
        assert url_is_safe("  https://example.com  ")

    def test_nul_stripped(self) -> None:
        """NUL bytes are stripped before validation."""
        assert not url_is_safe("java\x00script:alert(1)")
        assert url_is_safe("https://example\x00.com")

    def test_empty_safe(self) -> None:
        """Empty URL is safe."""
        assert url_is_safe("")


class TestSafeURL:
    """safe_url() function tests."""

    def test_safe_url_returns_url(self) -> None:
        """Safe URLs are returned as-is."""
        assert safe_url("https://example.com") == "https://example.com"

    def test_unsafe_url_returns_fallback(self) -> None:
        """Unsafe URLs return the fallback."""
        assert safe_url("javascript:alert(1)") == "#"

    def test_custom_fallback(self) -> None:
        """Custom fallback can be specified."""
        assert safe_url("javascript:void(0)", fallback="/home") == "/home"


# =============================================================================
# format_html Tests
# =============================================================================


class TestFormatHTML:
    """format_html() utility tests."""

    def test_basic_format(self) -> None:
        """Basic formatting with escaping."""
        result = format_html("<p>Hello, {name}!</p>", name="<World>")
        assert str(result) == "<p>Hello, &lt;World&gt;!</p>"
        assert isinstance(result, Markup)

    def test_multiple_args(self) -> None:
        """Multiple arguments are escaped."""
        result = format_html("<p>{} {}</p>", "<a>", "<b>")
        assert "&lt;a&gt;" in str(result)
        assert "&lt;b&gt;" in str(result)

    def test_preserves_markup_args(self) -> None:
        """Markup arguments are not double-escaped."""
        safe = Markup("<b>bold</b>")
        result = format_html("<p>{}</p>", safe)
        assert "<b>bold</b>" in str(result)
        assert "&lt;b&gt;" not in str(result)

    def test_format_string_not_escaped(self) -> None:
        """The format string itself is not escaped."""
        result = format_html("<a href='{url}'>{text}</a>", url="/page", text="<Click>")
        assert "<a href='/page'>" in str(result)
        assert "&lt;Click&gt;" in str(result)


# =============================================================================
# SoftStr Tests
# =============================================================================


class TestSoftStr:
    """SoftStr lazy evaluation tests."""

    def test_lazy_evaluation(self) -> None:
        """Function is not called until str() is called."""
        called = []

        def factory() -> str:
            called.append(True)
            return "result"

        soft = SoftStr(factory)
        assert len(called) == 0  # Not called yet
        assert str(soft) == "result"
        assert len(called) == 1

    def test_cached_result(self) -> None:
        """Result is cached after first evaluation."""
        call_count = [0]

        def factory() -> str:
            call_count[0] += 1
            return f"result-{call_count[0]}"

        soft = SoftStr(factory)
        assert str(soft) == "result-1"
        assert str(soft) == "result-1"  # Same result
        assert call_count[0] == 1  # Only called once

    def test_html_protocol_escapes(self) -> None:
        """__html__() escapes the resolved value."""
        soft = SoftStr(lambda: "<script>")
        assert soft.__html__() == "&lt;script&gt;"

    def test_html_protocol_preserves_markup(self) -> None:
        """__html__() preserves Markup values."""
        soft = SoftStr(lambda: Markup("<b>safe</b>"))
        assert soft.__html__() == "<b>safe</b>"

    def test_bool(self) -> None:
        """__bool__ triggers evaluation."""
        soft = SoftStr(lambda: "")
        assert not bool(soft)
        soft2 = SoftStr(lambda: "content")
        assert bool(soft2)

    def test_len(self) -> None:
        """__len__ triggers evaluation."""
        soft = SoftStr(lambda: "test")
        assert len(soft) == 4

    def test_repr_unresolved(self) -> None:
        """repr shows unresolved state."""
        soft = SoftStr(lambda: "test")
        assert "unresolved" in repr(soft)

    def test_repr_resolved(self) -> None:
        """repr shows resolved value."""
        soft = SoftStr(lambda: "test")
        str(soft)  # Force evaluation
        assert "test" in repr(soft)


# =============================================================================
# strip_tags Standalone Function Tests
# =============================================================================


class TestStripTagsFunction:
    """strip_tags() standalone function tests."""

    def test_basic_strip(self) -> None:
        """Basic tag stripping via function."""
        result = strip_tags("<p>Hello <b>World</b></p>")
        assert result == "Hello World"

    def test_returns_str(self) -> None:
        """strip_tags returns str, not Markup."""
        result = strip_tags("<p>test</p>")
        assert isinstance(result, str)
        assert not isinstance(result, Markup)
