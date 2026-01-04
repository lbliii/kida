"""Benchmarks for HTML escaping functions.

Run with: pytest benchmarks/ --benchmark-only

Or with detailed output:
    pytest benchmarks/ --benchmark-only --benchmark-verbose

For comparison with previous runs:
    pytest benchmarks/ --benchmark-compare

Requirements:
    pip install pytest-benchmark
"""

from __future__ import annotations

import pytest

from kida import Markup
from kida.utils.html import (
    css_escape,
    html_escape,
    js_escape,
    safe_url,
    url_is_safe,
    xmlattr,
)


# =============================================================================
# html_escape benchmarks
# =============================================================================


def test_escape_no_special(benchmark: pytest.BenchmarkFixture) -> None:
    """Fast path: no special characters.

    Target: <100ns
    """
    benchmark(html_escape, "Hello World no special chars here at all")


def test_escape_single_char(benchmark: pytest.BenchmarkFixture) -> None:
    """Single escapable character.

    Measures overhead of detecting and escaping one char.
    """
    benchmark(html_escape, "Hello & World")


def test_escape_many_special_chars(benchmark: pytest.BenchmarkFixture) -> None:
    """Many special characters.

    Target: <500ns
    """
    benchmark(html_escape, "<script>alert('xss');</script>" * 10)


def test_escape_with_nul(benchmark: pytest.BenchmarkFixture) -> None:
    """NUL byte handling (security feature).

    Verifies NUL stripping doesn't add significant overhead.
    """
    benchmark(html_escape, "\x00<script>\x00alert(1)\x00</script>\x00")


def test_escape_long_string_no_special(benchmark: pytest.BenchmarkFixture) -> None:
    """Long string with no special characters.

    Tests fast-path performance on larger inputs.
    """
    text = "This is a long string without any special HTML characters. " * 50
    benchmark(html_escape, text)


def test_escape_long_string_with_special(benchmark: pytest.BenchmarkFixture) -> None:
    """Long string with scattered special characters.

    Realistic content with occasional escaping needed.
    """
    text = "User said: 'Hello & goodbye' at <time> on day #1. " * 50
    benchmark(html_escape, text)


# =============================================================================
# Markup class benchmarks
# =============================================================================


def test_markup_creation(benchmark: pytest.BenchmarkFixture) -> None:
    """Markup instance creation."""
    benchmark(Markup, "<b>bold</b>")


def test_markup_format(benchmark: pytest.BenchmarkFixture) -> None:
    """Markup.format() with escaping.

    Measures format string interpolation with auto-escaping.
    """
    m = Markup("<p>{}</p>")
    benchmark(m.format, "<script>alert(1)</script>")


def test_markup_format_multiple(benchmark: pytest.BenchmarkFixture) -> None:
    """Markup.format() with multiple arguments."""
    m = Markup("<p>{} {} {}</p>")
    benchmark(m.format, "<a>", "<b>", "<c>")


def test_markup_concat(benchmark: pytest.BenchmarkFixture) -> None:
    """Markup concatenation with escaping."""
    m = Markup("<b>")
    benchmark(lambda: m + "<script>")


def test_markup_join(benchmark: pytest.BenchmarkFixture) -> None:
    """Markup.join() with mixed content."""
    m = Markup(", ")
    items = ["<a>", Markup("<b>"), "<c>", Markup("<d>"), "<e>"]
    benchmark(m.join, items)


# =============================================================================
# Context-specific escaping benchmarks
# =============================================================================


def test_js_escape_simple(benchmark: pytest.BenchmarkFixture) -> None:
    """JavaScript escaping: simple string."""
    benchmark(js_escape, "Hello World")


def test_js_escape_with_quotes(benchmark: pytest.BenchmarkFixture) -> None:
    """JavaScript escaping: string with quotes.

    Target: <500ns
    """
    benchmark(js_escape, 'Hello "World" </script> `${x}`')


def test_js_escape_complex(benchmark: pytest.BenchmarkFixture) -> None:
    """JavaScript escaping: complex content."""
    content = "User input: \"<script>alert('xss')</script>\" with `template ${var}`"
    benchmark(js_escape, content)


def test_css_escape_simple(benchmark: pytest.BenchmarkFixture) -> None:
    """CSS escaping: simple string."""
    benchmark(css_escape, "simple-class-name")


def test_css_escape_with_special(benchmark: pytest.BenchmarkFixture) -> None:
    """CSS escaping: string with special chars."""
    benchmark(css_escape, "url('../path/to/image.png')")


# =============================================================================
# URL validation benchmarks
# =============================================================================


def test_url_is_safe_relative(benchmark: pytest.BenchmarkFixture) -> None:
    """URL validation: relative path (fast path).

    Target: <200ns
    """
    benchmark(url_is_safe, "/path/to/page")


def test_url_is_safe_absolute(benchmark: pytest.BenchmarkFixture) -> None:
    """URL validation: absolute safe URL.

    Target: <500ns
    """
    benchmark(url_is_safe, "https://example.com/path?query=1")


def test_url_is_safe_javascript(benchmark: pytest.BenchmarkFixture) -> None:
    """URL validation: javascript: protocol (must detect unsafe).

    Tests full validation path.
    """
    benchmark(url_is_safe, "javascript:alert(1)")


def test_safe_url_safe(benchmark: pytest.BenchmarkFixture) -> None:
    """safe_url() with safe URL."""
    benchmark(safe_url, "https://example.com")


def test_safe_url_unsafe(benchmark: pytest.BenchmarkFixture) -> None:
    """safe_url() with unsafe URL (returns fallback)."""
    benchmark(safe_url, "javascript:void(0)")


# =============================================================================
# xmlattr benchmarks
# =============================================================================


def test_xmlattr_simple(benchmark: pytest.BenchmarkFixture) -> None:
    """Simple attribute set.

    Target: <2μs for 2 attrs
    """
    benchmark(xmlattr, {"class": "btn", "id": "submit"}, allow_events=True)


def test_xmlattr_with_escaping(benchmark: pytest.BenchmarkFixture) -> None:
    """Attributes requiring escaping."""
    attrs = {"data-value": '<script>"test"</script>', "class": "btn"}
    benchmark(xmlattr, attrs, allow_events=True)


def test_xmlattr_many(benchmark: pytest.BenchmarkFixture) -> None:
    """Many attributes (5)."""
    attrs = {
        "class": "btn btn-primary",
        "id": "submit-form",
        "data-action": "submit",
        "aria-label": "Submit the form",
        "type": "submit",
    }
    benchmark(xmlattr, attrs, allow_events=True)


def test_xmlattr_with_none(benchmark: pytest.BenchmarkFixture) -> None:
    """Attributes with None values (skipped)."""
    attrs = {"class": "btn", "disabled": None, "id": "test", "hidden": None}
    benchmark(xmlattr, attrs, allow_events=True)


# =============================================================================
# Comparison benchmarks
# =============================================================================


def test_escape_vs_naive_chain(benchmark: pytest.BenchmarkFixture) -> None:
    """Compare optimized escape to naive chained .replace().

    This benchmark exists to verify our optimization is faster.
    """

    def naive_escape(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    content = "<script>alert('test & \"xss\"')</script>"
    benchmark(naive_escape, content)


def test_escape_optimized(benchmark: pytest.BenchmarkFixture) -> None:
    """Optimized escape for comparison."""
    content = "<script>alert('test & \"xss\"')</script>"
    benchmark(html_escape, content)

