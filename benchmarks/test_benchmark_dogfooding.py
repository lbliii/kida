"""Benchmarks for t-string dogfooding RFC.

Establishes baselines for string-building patterns in Kida internals
to validate whether t-string conversion provides performance benefits.

Run with:
    uv run pytest benchmarks/test_benchmark_dogfooding.py --benchmark-only

Save baseline:
    uv run pytest benchmarks/test_benchmark_dogfooding.py --benchmark-save=dogfooding-baseline

Compare after changes:
    uv run pytest benchmarks/test_benchmark_dogfooding.py --benchmark-compare=dogfooding-baseline
"""

from __future__ import annotations

import sys
from io import StringIO
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


# =============================================================================
# ParseError Benchmarks
# =============================================================================


@pytest.mark.benchmark(group="dogfooding:parse-error")
def test_parse_error_format_short(benchmark: BenchmarkFixture) -> None:
    """ParseError._format() with short source (10 lines)."""
    from kida._types import Token, TokenType
    from kida.parser.errors import ParseError

    token = Token(TokenType.NAME, "undefined_var", 10, 5)
    source = "{% for item in items %}\n" * 9 + "{{ undefined_var }}"
    error = ParseError("Undefined variable", token, source, "test.html")

    benchmark(error._format)


@pytest.mark.benchmark(group="dogfooding:parse-error")
def test_parse_error_format_long(benchmark: BenchmarkFixture) -> None:
    """ParseError._format() with long source (100 lines)."""
    from kida._types import Token, TokenType
    from kida.parser.errors import ParseError

    token = Token(TokenType.NAME, "undefined_var", 50, 5)
    source = "{% for item in items %}\n" * 49 + "{{ undefined_var }}\n" + "{% end %}\n" * 50
    error = ParseError("Undefined variable", token, source, "template.html")

    benchmark(error._format)


@pytest.mark.benchmark(group="dogfooding:parse-error")
def test_parse_error_format_with_suggestion(benchmark: BenchmarkFixture) -> None:
    """ParseError._format() with suggestion text."""
    from kida._types import Token, TokenType
    from kida.parser.errors import ParseError

    token = Token(TokenType.NAME, "titl", 5, 8)
    source = "<h1>{{ titl }}</h1>"
    error = ParseError(
        "Undefined variable 'titl'",
        token,
        source,
        "article.html",
        suggestion="Did you mean 'title'?",
    )

    benchmark(error._format)


# =============================================================================
# xmlattr Benchmarks
# =============================================================================


@pytest.mark.benchmark(group="dogfooding:xmlattr")
def test_xmlattr_single(benchmark: BenchmarkFixture) -> None:
    """xmlattr() with 1 attribute."""
    from kida.utils.html import xmlattr

    attrs = {"class": "btn"}
    benchmark(xmlattr, attrs, allow_events=True)


@pytest.mark.benchmark(group="dogfooding:xmlattr")
def test_xmlattr_typical(benchmark: BenchmarkFixture) -> None:
    """xmlattr() with 5 attributes (typical use case)."""
    from kida.utils.html import xmlattr

    attrs = {
        "class": "btn btn-primary",
        "id": "submit-form",
        "data-action": "submit",
        "aria-label": "Submit the form",
        "disabled": "disabled",
    }
    benchmark(xmlattr, attrs, allow_events=True)


@pytest.mark.benchmark(group="dogfooding:xmlattr")
def test_xmlattr_many(benchmark: BenchmarkFixture) -> None:
    """xmlattr() with 10 attributes."""
    from kida.utils.html import xmlattr

    attrs = {
        "class": "card card-body shadow-sm",
        "id": "user-profile-card",
        "data-user-id": "12345",
        "data-role": "admin",
        "data-status": "active",
        "aria-label": "User profile card",
        "aria-describedby": "profile-description",
        "tabindex": "0",
        "role": "article",
        "title": "View user profile",
    }
    benchmark(xmlattr, attrs, allow_events=True)


@pytest.mark.benchmark(group="dogfooding:xmlattr")
def test_xmlattr_with_escaping(benchmark: BenchmarkFixture) -> None:
    """xmlattr() with values requiring HTML escaping."""
    from kida.utils.html import xmlattr

    attrs = {
        "data-json": '{"key": "value", "html": "<b>bold</b>"}',
        "title": "Click here & learn more",
        "aria-label": "User's profile <admin>",
    }
    benchmark(xmlattr, attrs, allow_events=True)


# =============================================================================
# Debug Filter Benchmarks
# =============================================================================


class MockPage:
    """Mock page object for debug filter benchmarks."""

    def __init__(self, title: str, weight: int | None) -> None:
        self.title = title
        self.weight = weight


@pytest.fixture
def mock_pages_small() -> list[MockPage]:
    """5 mock pages."""
    return [MockPage(f"Page {i}", i if i % 2 else None) for i in range(5)]


@pytest.fixture
def mock_pages_medium() -> list[MockPage]:
    """20 mock pages."""
    return [MockPage(f"Page {i}", i if i % 3 else None) for i in range(20)]


@pytest.fixture
def suppress_stderr():
    """Context manager to suppress stderr during debug filter tests."""
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    yield
    sys.stderr = old_stderr


@pytest.mark.benchmark(group="dogfooding:debug")
def test_debug_filter_small_list(
    benchmark: BenchmarkFixture, mock_pages_small: list[MockPage], suppress_stderr
) -> None:
    """_filter_debug with 5 objects."""
    from kida.environment.filters import _filter_debug

    benchmark(_filter_debug, mock_pages_small, "pages", 5)


@pytest.mark.benchmark(group="dogfooding:debug")
def test_debug_filter_medium_list(
    benchmark: BenchmarkFixture, mock_pages_medium: list[MockPage], suppress_stderr
) -> None:
    """_filter_debug with 20 objects (shows truncation)."""
    from kida.environment.filters import _filter_debug

    benchmark(_filter_debug, mock_pages_medium, "pages", 5)


@pytest.mark.benchmark(group="dogfooding:debug")
def test_debug_filter_dict(benchmark: BenchmarkFixture, suppress_stderr) -> None:
    """_filter_debug with dictionary."""
    from kida.environment.filters import _filter_debug

    data = {
        "title": "My Page",
        "weight": 10,
        "draft": False,
        "tags": ["python", "templates"],
        "author": None,
    }
    benchmark(_filter_debug, data, "config", 10)


@pytest.mark.benchmark(group="dogfooding:debug")
def test_debug_filter_none(benchmark: BenchmarkFixture, suppress_stderr) -> None:
    """_filter_debug with None value."""
    from kida.environment.filters import _filter_debug

    benchmark(_filter_debug, None, "missing")


# =============================================================================
# filesizeformat Benchmarks
# =============================================================================


@pytest.mark.benchmark(group="dogfooding:filesizeformat")
def test_filesizeformat_bytes(benchmark: BenchmarkFixture) -> None:
    """filesizeformat with small value (bytes)."""
    from kida.environment.filters import _filter_filesizeformat

    benchmark(_filter_filesizeformat, 512)


@pytest.mark.benchmark(group="dogfooding:filesizeformat")
def test_filesizeformat_megabytes(benchmark: BenchmarkFixture) -> None:
    """filesizeformat with typical value (MB)."""
    from kida.environment.filters import _filter_filesizeformat

    benchmark(_filter_filesizeformat, 1_500_000)  # ~1.5 MB


@pytest.mark.benchmark(group="dogfooding:filesizeformat")
def test_filesizeformat_gigabytes_binary(benchmark: BenchmarkFixture) -> None:
    """filesizeformat with large value (GiB, binary mode)."""
    from kida.environment.filters import _filter_filesizeformat

    benchmark(_filter_filesizeformat, 2_500_000_000, binary=True)  # ~2.3 GiB


# =============================================================================
# Comparison: f-string vs t-string (when available)
# =============================================================================


@pytest.mark.benchmark(group="dogfooding:comparison")
def test_fstring_multi_interpolation(benchmark: BenchmarkFixture) -> None:
    """Baseline: f-string with 5 interpolations."""
    header = "Parse Error: Undefined variable"
    line_num = 42
    error_line = "{{ undefined_var }}"
    pointer = "   ^^^^^^^^^^^^^^^"
    filename = "template.html"

    def build():
        return f"""{header}
  --> {filename}:{line_num}
   |
{line_num:>3} | {error_line}
   | {pointer}"""

    benchmark(build)


@pytest.mark.benchmark(group="dogfooding:comparison")
def test_tstring_multi_interpolation(benchmark: BenchmarkFixture) -> None:
    """t-string with 5 interpolations (requires Python 3.14+)."""
    from kida import k

    if k is None:
        pytest.skip("t-strings require Python 3.14+")

    header = "Parse Error: Undefined variable"
    line_num = 42
    error_line = "{{ undefined_var }}"
    pointer = "   ^^^^^^^^^^^^^^^"
    filename = "template.html"

    def build():
        return k(
            t"""{header}
  --> {filename}:{line_num}
   |
{line_num:>3} | {error_line}
   | {pointer}"""
        )

    benchmark(build)


@pytest.mark.benchmark(group="dogfooding:comparison")
def test_list_join_pattern(benchmark: BenchmarkFixture) -> None:
    """Baseline: list accumulation + join pattern."""
    items = [("class", "btn"), ("id", "submit"), ("disabled", "true")]

    def build():
        parts = []
        for key, val in items:
            parts.append(f'{key}="{val}"')
        return " ".join(parts)

    benchmark(build)
