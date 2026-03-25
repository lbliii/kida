"""Unit tests for kida.utils.csp — CSP nonce injection utilities."""

from __future__ import annotations

from kida.utils.csp import csp_nonce_filter, csp_nonce_global, inject_csp_nonce
from kida.utils.html import Markup

# ---------------------------------------------------------------------------
# inject_csp_nonce
# ---------------------------------------------------------------------------


class TestInjectCspNonce:
    """Tests for the inject_csp_nonce function."""

    def test_injects_nonce_into_script_tag(self) -> None:
        html = "<script>alert(1)</script>"
        result = inject_csp_nonce(html, "abc123")
        assert result == '<script nonce="abc123">alert(1)</script>'

    def test_injects_nonce_into_style_tag(self) -> None:
        html = "<style>body{}</style>"
        result = inject_csp_nonce(html, "abc123")
        assert result == '<style nonce="abc123">body{}</style>'

    def test_injects_into_multiple_tags(self) -> None:
        html = "<script>a</script><style>b</style><script>c</script>"
        result = inject_csp_nonce(html, "n1")
        assert result.count('nonce="n1"') == 3

    def test_preserves_existing_attributes(self) -> None:
        html = '<script type="module">x</script>'
        result = inject_csp_nonce(html, "abc")
        assert 'type="module"' in result
        assert 'nonce="abc"' in result

    def test_skips_tag_with_existing_nonce(self) -> None:
        html = '<script nonce="old">x</script>'
        result = inject_csp_nonce(html, "new")
        assert result == '<script nonce="old">x</script>'

    def test_skips_existing_nonce_case_insensitive(self) -> None:
        html = '<script Nonce="old">x</script>'
        result = inject_csp_nonce(html, "new")
        assert 'Nonce="old"' in result
        assert result.lower().count("nonce") == 1  # only the original

    def test_empty_nonce_returns_unchanged(self) -> None:
        html = "<script>x</script>"
        assert inject_csp_nonce(html, "") == html

    def test_case_insensitive_tag_matching(self) -> None:
        html = "<Script>x</Script>"
        result = inject_csp_nonce(html, "abc")
        assert 'nonce="abc"' in result

    def test_html_escapes_nonce_value(self) -> None:
        html = "<script>x</script>"
        result = inject_csp_nonce(html, 'a"b<c>&d')
        # html.escape with quote=True escapes quotes and angle brackets
        assert '"' not in result.split('nonce="')[1].split('"')[0] or "&quot;" in result
        assert "<" not in result.split('nonce="')[1].split('"')[0]

    def test_no_script_or_style_tags(self) -> None:
        html = "<div>hello</div>"
        result = inject_csp_nonce(html, "abc")
        assert result == html

    def test_script_tag_with_no_attributes(self) -> None:
        result = inject_csp_nonce("<script>x</script>", "n")
        assert result == '<script nonce="n">x</script>'

    def test_style_with_attributes(self) -> None:
        html = '<style media="screen">body{}</style>'
        result = inject_csp_nonce(html, "n")
        assert 'media="screen"' in result
        assert 'nonce="n"' in result

    def test_returns_markup_when_input_is_markup(self) -> None:
        html = Markup("<script>x</script>")
        result = inject_csp_nonce(html, "abc")
        assert isinstance(result, Markup)
        assert 'nonce="abc"' in result

    def test_returns_plain_str_when_input_is_plain_str(self) -> None:
        html = "<script>x</script>"
        result = inject_csp_nonce(html, "abc")
        assert type(result) is str
        assert 'nonce="abc"' in result

    def test_preserves_markup_when_nonce_empty(self) -> None:
        html = Markup("<script>x</script>")
        result = inject_csp_nonce(html, "")
        assert isinstance(result, Markup)


# ---------------------------------------------------------------------------
# csp_nonce_filter
# ---------------------------------------------------------------------------


class TestCspNonceFilter:
    """Tests for the csp_nonce_filter template filter."""

    def test_with_explicit_nonce(self) -> None:
        result = csp_nonce_filter("<script>x</script>", nonce="abc")
        assert 'nonce="abc"' in result

    def test_without_nonce_returns_string(self) -> None:
        """When no nonce provided and no render context, returns str(value)."""
        result = csp_nonce_filter("<script>x</script>")
        assert result == "<script>x</script>"

    def test_non_string_value_converted(self) -> None:
        result = csp_nonce_filter(12345, nonce="abc")
        assert result == "12345"

    def test_with_render_context_meta(self) -> None:
        """When nonce is set in the render context meta, it is used."""
        from kida.render_context import render_context

        with render_context() as ctx:
            ctx.set_meta("csp_nonce", "from-ctx")
            result = csp_nonce_filter("<script>x</script>")
        assert 'nonce="from-ctx"' in result

    def test_explicit_nonce_overrides_context(self) -> None:
        """Explicit nonce parameter takes priority over context."""
        from kida.render_context import render_context

        with render_context() as ctx:
            ctx.set_meta("csp_nonce", "from-ctx")
            result = csp_nonce_filter("<script>x</script>", nonce="explicit")
        assert 'nonce="explicit"' in result

    def test_empty_nonce_in_context(self) -> None:
        """If context has empty nonce, returns plain string."""
        from kida.render_context import render_context

        with render_context() as ctx:
            ctx.set_meta("csp_nonce", "")
            result = csp_nonce_filter("<script>x</script>")
        assert "nonce" not in result

    def test_returns_markup_with_explicit_nonce(self) -> None:
        result = csp_nonce_filter("<script>x</script>", nonce="abc")
        assert isinstance(result, Markup)

    def test_returns_markup_without_nonce(self) -> None:
        """Even when no nonce is applied, the filter returns Markup."""
        result = csp_nonce_filter("<script>x</script>")
        assert isinstance(result, Markup)

    def test_preserves_existing_markup_input(self) -> None:
        """If input is already Markup, output stays Markup without re-wrapping."""
        value = Markup("<b>safe</b>")
        result = csp_nonce_filter(value)
        assert isinstance(result, Markup)
        assert result == "<b>safe</b>"

    def test_returns_markup_from_render_context(self) -> None:
        from kida.render_context import render_context

        with render_context() as ctx:
            ctx.set_meta("csp_nonce", "ctx-nonce")
            result = csp_nonce_filter("<script>x</script>")
        assert isinstance(result, Markup)
        assert 'nonce="ctx-nonce"' in result


# ---------------------------------------------------------------------------
# csp_nonce_global
# ---------------------------------------------------------------------------


class TestCspNonceGlobal:
    """Tests for the csp_nonce_global template global."""

    def test_returns_empty_outside_context(self) -> None:
        assert csp_nonce_global() == ""

    def test_returns_nonce_from_context(self) -> None:
        from kida.render_context import render_context

        with render_context() as ctx:
            ctx.set_meta("csp_nonce", "my-nonce")
            assert csp_nonce_global() == "my-nonce"

    def test_returns_empty_when_not_set(self) -> None:
        from kida.render_context import render_context

        with render_context():
            assert csp_nonce_global() == ""

    def test_returns_empty_for_none_value(self) -> None:
        from kida.render_context import render_context

        with render_context() as ctx:
            ctx.set_meta("csp_nonce", None)
            assert csp_nonce_global() == ""
