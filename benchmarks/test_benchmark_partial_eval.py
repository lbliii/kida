"""Benchmark partial evaluation and compiler optimizations.

Measures the rendering speedup when templates are compiled with
static_context, demonstrating compile-time constant folding, dead
branch elimination, and filter evaluation.

Run with: pytest benchmarks/test_benchmark_partial_eval.py --benchmark-only -v
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kida import Environment

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


# =============================================================================
# Static data (known at compile time in real apps: site config, nav, settings)
# =============================================================================


@dataclass(frozen=True, slots=True)
class SiteConfig:
    title: str
    url: str
    description: str
    author: str
    lang: str
    nav: tuple[dict[str, str], ...]


SITE = SiteConfig(
    title="Kida Documentation",
    url="https://lbliii.github.io/kida",
    description="A Python template engine for HTML, terminal, and streaming",
    author="lbliii",
    lang="en",
    nav=(
        {"title": "Home", "url": "/", "active": True},
        {"title": "Docs", "url": "/docs/", "active": False},
        {"title": "API", "url": "/api/", "active": False},
        {"title": "Blog", "url": "/blog/", "active": False},
        {"title": "GitHub", "url": "https://github.com/lbliii/kida", "active": False},
    ),
)

SETTINGS = {
    "debug": False,
    "show_analytics": True,
    "show_footer_links": True,
    "theme": "dark",
    "version": "0.3.1",
}


# =============================================================================
# Templates
# =============================================================================

# Template with many static expressions that benefit from partial eval
TEMPLATE_WITH_STATIC = """\
<!DOCTYPE html>
<html lang="{{ site.lang }}">
<head>
    <meta charset="utf-8">
    <title>{{ site.title }} - {{ page_title }}</title>
    <meta name="description" content="{{ site.description }}">
    <meta name="author" content="{{ site.author }}">
    <link rel="canonical" href="{{ site.url }}">
</head>
<body class="theme-{{ settings.theme }}">
    <nav>
        {% for item in site.nav %}
        <a href="{{ item.url }}"{% if item.active %} class="active"{% end %}>{{ item.title }}</a>
        {% end %}
    </nav>
    <main>
        <h1>{{ page_title }}</h1>
        {% for item in items %}
        <article>
            <h2>{{ item.name | upper }}</h2>
            <p>{{ item.description | default("No description") | truncate(100) }}</p>
        </article>
        {% end %}
    </main>
    {% if settings.debug %}
    <div class="debug-panel">
        <p>Debug mode enabled</p>
        <p>Version: {{ settings.version }}</p>
    </div>
    {% end %}
    <footer>
        <p>{{ site.title }} v{{ settings.version }} by {{ site.author }}</p>
        {% if settings.show_footer_links %}
        <nav>
            {% for item in site.nav %}
            <a href="{{ item.url }}">{{ item.title }}</a>
            {% end %}
        </nav>
        {% end %}
    </footer>
</body>
</html>
"""

# Dynamic page data (different per request, not known at compile time)
PAGE_ITEMS = [
    {"name": f"Article {i}", "description": f"Description for article {i} with some longer text"}
    for i in range(50)
]


# =============================================================================
# Benchmarks: With vs Without static_context
# =============================================================================


class TestPartialEvalBenchmarks:
    """Compare rendering speed with and without partial evaluation."""

    def test_render_no_static_context(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: everything resolved at runtime."""
        env = Environment(autoescape=False)
        tpl = env.from_string(TEMPLATE_WITH_STATIC)

        def render() -> str:
            return tpl.render(
                site=SITE,
                settings=SETTINGS,
                page_title="Benchmarks",
                items=PAGE_ITEMS,
            )

        result = benchmark(render)
        assert "Kida Documentation" in result

    def test_render_with_static_context(self, benchmark: BenchmarkFixture) -> None:
        """Optimized: site config and settings folded at compile time.

        Note: site.nav is still passed at render time for the for loop,
        but all {{ site.X }} and {{ settings.X }} expressions in non-loop
        contexts are folded to constants at compile time.
        """
        env = Environment(autoescape=False)
        tpl = env.from_string(
            TEMPLATE_WITH_STATIC,
            static_context={"site": SITE, "settings": SETTINGS},
        )

        def render() -> str:
            return tpl.render(
                site=SITE,  # Still needed for for-loop iteration
                settings=SETTINGS,
                page_title="Benchmarks",
                items=PAGE_ITEMS,
            )

        result = benchmark(render)
        assert "Kida Documentation" in result

    def test_render_with_static_context_and_inlining(self, benchmark: BenchmarkFixture) -> None:
        """Optimized: static context + component inlining."""
        env = Environment(autoescape=False, inline_components=True)
        tpl = env.from_string(
            TEMPLATE_WITH_STATIC,
            static_context={"site": SITE, "settings": SETTINGS},
        )

        def render() -> str:
            return tpl.render(
                site=SITE,
                settings=SETTINGS,
                page_title="Benchmarks",
                items=PAGE_ITEMS,
            )

        result = benchmark(render)
        assert "Kida Documentation" in result

    def test_render_with_html_escaping_no_static(self, benchmark: BenchmarkFixture) -> None:
        """Baseline with autoescape=True."""
        env = Environment(autoescape=True)
        tpl = env.from_string(TEMPLATE_WITH_STATIC)

        def render() -> str:
            return tpl.render(
                site=SITE,
                settings=SETTINGS,
                page_title="Benchmarks",
                items=PAGE_ITEMS,
            )

        result = benchmark(render)
        assert "Kida Documentation" in result

    def test_render_with_html_escaping_static(self, benchmark: BenchmarkFixture) -> None:
        """Optimized with autoescape=True + static context."""
        env = Environment(autoescape=True)
        tpl = env.from_string(
            TEMPLATE_WITH_STATIC,
            static_context={"site": SITE, "settings": SETTINGS},
        )

        def render() -> str:
            return tpl.render(
                site=SITE,
                settings=SETTINGS,
                page_title="Benchmarks",
                items=PAGE_ITEMS,
            )

        result = benchmark(render)
        assert "Kida Documentation" in result


# =============================================================================
# Filter chain folding benchmark
# =============================================================================

FILTER_CHAIN_TEMPLATE = """\
<header>{{ title | upper }}</header>
<meta name="description" content="{{ description | truncate(100) }}">
<meta name="keywords" content="{{ keywords | join(', ') }}">
<p class="{{ status | lower }}">{{ status | capitalize }}</p>
<span>{{ count | abs }} items ({{ price | round(2) }})</span>
{% if show_debug %}
<div class="debug">{{ debug_info | default("none") }}</div>
{% end %}
"""


class TestFilterFoldingBenchmarks:
    """Measure filter chain evaluation with static vs dynamic values."""

    def test_filter_chains_dynamic(self, benchmark: BenchmarkFixture) -> None:
        """All filter inputs are dynamic — filters run at render time."""
        env = Environment(autoescape=False)
        tpl = env.from_string(FILTER_CHAIN_TEMPLATE)
        ctx = {
            "title": "hello world",
            "description": "A long description that goes on and on " * 5,
            "keywords": ["python", "templates", "kida"],
            "status": "ACTIVE",
            "count": -42,
            "price": 19.999,
            "show_debug": False,
            "debug_info": None,
        }

        result = benchmark(tpl.render, **ctx)
        assert "HELLO WORLD" in result

    def test_filter_chains_static(self, benchmark: BenchmarkFixture) -> None:
        """All filter inputs from static context — filters evaluated at compile time."""
        env = Environment(autoescape=False)
        ctx = {
            "title": "hello world",
            "description": "A long description that goes on and on " * 5,
            "keywords": ["python", "templates", "kida"],
            "status": "ACTIVE",
            "count": -42,
            "price": 19.999,
            "show_debug": False,
            "debug_info": None,
        }
        tpl = env.from_string(
            FILTER_CHAIN_TEMPLATE,
            static_context=ctx,
        )

        result = benchmark(tpl.render)
        assert "HELLO WORLD" in result


# =============================================================================
# Optimization gap benchmarks — baseline for epic-partial-eval-enhancement
# =============================================================================

# Static for-loop: nav with 5 items, all known at compile time
STATIC_FOR_TEMPLATE = """\
<nav>
{% for item in nav %}
<a href="{{ item.url }}">{{ item.title }}</a>
{% end %}
</nav>
"""

NAV_ITEMS = (
    {"title": "Home", "url": "/"},
    {"title": "Docs", "url": "/docs/"},
    {"title": "API", "url": "/api/"},
    {"title": "Blog", "url": "/blog/"},
    {"title": "GitHub", "url": "/github"},
)

# Set/Let chain: assignment propagation
SET_CHAIN_TEMPLATE = """\
{% set theme = config.theme %}\
{% set label = config.label | upper %}\
Theme: {{ theme }}, Label: {{ label }}\
"""

# Partial BoolOp: short-circuit with one static operand
PARTIAL_BOOLOP_TEMPLATE = """\
{% if show_banner and has_content %}BANNER{% end %}\
{% if is_admin or is_guest %}ACCESS{% end %}\
"""


class TestStaticForLoopBenchmarks:
    """Measure rendering of for-loops with static vs dynamic iterables."""

    def test_static_for_dynamic(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: nav items passed at runtime."""
        env = Environment(autoescape=False)
        tpl = env.from_string(STATIC_FOR_TEMPLATE)

        result = benchmark(tpl.render, nav=NAV_ITEMS)
        assert "Home" in result

    def test_static_for_with_static_context(self, benchmark: BenchmarkFixture) -> None:
        """Optimized: nav items known at compile time."""
        env = Environment(autoescape=False)
        tpl = env.from_string(
            STATIC_FOR_TEMPLATE,
            static_context={"nav": NAV_ITEMS},
        )

        result = benchmark(tpl.render, nav=NAV_ITEMS)
        assert "Home" in result


class TestSetChainBenchmarks:
    """Measure set/let chain rendering with static vs dynamic values."""

    def test_set_chain_dynamic(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: config passed at runtime."""
        env = Environment(autoescape=False)
        tpl = env.from_string(SET_CHAIN_TEMPLATE)
        ctx = {"config": {"theme": "dark", "label": "hello"}}

        result = benchmark(tpl.render, **ctx)
        assert "dark" in result

    def test_set_chain_static(self, benchmark: BenchmarkFixture) -> None:
        """Optimized: config known at compile time."""
        env = Environment(autoescape=False)
        ctx = {"config": {"theme": "dark", "label": "hello"}}
        tpl = env.from_string(
            SET_CHAIN_TEMPLATE,
            static_context=ctx,
        )

        result = benchmark(tpl.render, **ctx)
        assert "dark" in result


class TestPartialBoolOpBenchmarks:
    """Measure partial BoolOp simplification."""

    def test_boolop_dynamic(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: all operands dynamic."""
        env = Environment(autoescape=False)
        tpl = env.from_string(PARTIAL_BOOLOP_TEMPLATE)
        ctx = {
            "show_banner": False,
            "has_content": True,
            "is_admin": True,
            "is_guest": False,
        }

        result = benchmark(tpl.render, **ctx)
        assert "ACCESS" in result

    def test_boolop_partial_static(self, benchmark: BenchmarkFixture) -> None:
        """Optimized: one operand per BoolOp is static."""
        env = Environment(autoescape=False)
        tpl = env.from_string(
            PARTIAL_BOOLOP_TEMPLATE,
            static_context={"show_banner": False, "is_admin": True},
        )

        result = benchmark(
            tpl.render,
            show_banner=False,
            has_content=True,
            is_admin=True,
            is_guest=False,
        )
        assert "ACCESS" in result
