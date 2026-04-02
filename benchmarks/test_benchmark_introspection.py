"""Benchmarks for template introspection APIs.

Measures template_metadata(), list_blocks(), get_template_structure(),
required_context(), validate_context(), and render_block() — used by Bengal,
Chirp, and composition workflows.

Cached accessor benchmarks batch repeated calls so CI compares meaningful work
instead of a few hundred nanoseconds of Python call overhead.

Run with: pytest benchmarks/test_benchmark_introspection.py --benchmark-only -v
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from kida import Environment as KidaEnvironment
from kida import FileSystemLoader as KidaFileSystemLoader

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_benchmark.fixture import BenchmarkFixture

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
ACCESSOR_CALLS_PER_ROUND = 8192
CONTEXT_CALLS_PER_ROUND = 1024

# Template with blocks, no extends (for list_blocks, template_metadata)
BLOCKS_TEMPLATE = """\
{% block title %}Page Title{% end %}
{% block content %}
<article>
    <h1>{{ title }}</h1>
    {% for item in items %}
        <li>{{ item }}</li>
    {% end %}
</article>
{% end %}
"""

VALIDATION_TEMPLATE = """\
<h1>{{ title }}</h1>
<p>By {{ author.name }}</p>
<p>Section: {{ page.section }}</p>
"""

VALIDATION_CONTEXT = {
    "title": "Benchmark",
    "author": {"name": "Ada"},
    "page": {"section": "guides"},
}


def _run_cached_batch(
    func: Callable[[], object | None],
    iterations: int,
) -> object | None:
    """Run a cached accessor enough times to drown out call overhead."""
    result: object | None = None
    for _ in range(iterations):
        result = func()
    return result


def _compile_and_analyze_small_template() -> object | None:
    """Benchmark the first metadata call, not just the cache-hit accessor."""
    env = KidaEnvironment(preserve_ast=True, auto_reload=False)
    template = env.from_string(BLOCKS_TEMPLATE, name="introspection_first_call")
    return template.template_metadata()


def _get_template_structure_complex(env: KidaEnvironment) -> object | None:
    """Benchmark cached structure lookup on a preloaded complex template."""
    return env.get_template_structure("complex/page.html")


@pytest.fixture(scope="session")
def kida_env_preserve_ast() -> KidaEnvironment:
    """Kida env with preserve_ast=True for introspection benchmarks."""
    loader = KidaFileSystemLoader(str(TEMPLATE_DIR))
    return KidaEnvironment(
        loader=loader,
        auto_reload=False,
        preserve_ast=True,
    )


# =============================================================================
# template_metadata() benchmarks
# =============================================================================


@pytest.mark.benchmark(group="introspection:template-metadata-cached")
def test_template_metadata_small_cached_batch(benchmark: BenchmarkFixture) -> None:
    """Cached template_metadata() on a small template, batched for stability."""
    env = KidaEnvironment(preserve_ast=True, auto_reload=False)
    template = env.from_string(BLOCKS_TEMPLATE, name="introspection_bench")
    template.template_metadata()  # Warm the metadata cache before timing.
    benchmark(_run_cached_batch, template.template_metadata, ACCESSOR_CALLS_PER_ROUND)


@pytest.mark.benchmark(group="introspection:template-metadata-cached")
def test_template_metadata_complex_cached_batch(
    benchmark: BenchmarkFixture, kida_env_preserve_ast: KidaEnvironment
) -> None:
    """Cached template_metadata() on a complex inheritance chain."""
    template = kida_env_preserve_ast.get_template("complex/page.html")
    template.template_metadata()  # Warm the metadata cache before timing.
    benchmark(_run_cached_batch, template.template_metadata, ACCESSOR_CALLS_PER_ROUND)


@pytest.mark.benchmark(group="introspection:template-metadata-first-call")
def test_template_metadata_small_first_call(benchmark: BenchmarkFixture) -> None:
    """First template_metadata() call, including analysis and cache population."""
    benchmark(_compile_and_analyze_small_template)


# =============================================================================
# list_blocks() benchmarks
# =============================================================================


@pytest.mark.benchmark(group="introspection:list-blocks-cached")
def test_list_blocks_small_cached_batch(benchmark: BenchmarkFixture) -> None:
    """Cached list_blocks() on a small template, batched for stability."""
    env = KidaEnvironment(preserve_ast=True, auto_reload=False)
    template = env.from_string(BLOCKS_TEMPLATE, name="list_blocks_bench")
    template.list_blocks()  # Warm the metadata cache before timing.
    benchmark(_run_cached_batch, template.list_blocks, ACCESSOR_CALLS_PER_ROUND)


@pytest.mark.benchmark(group="introspection:list-blocks-cached")
def test_list_blocks_complex_cached_batch(
    benchmark: BenchmarkFixture, kida_env_preserve_ast: KidaEnvironment
) -> None:
    """Cached list_blocks() on a complex inheritance chain, batched."""
    template = kida_env_preserve_ast.get_template("complex/page.html")
    template.list_blocks()  # Warm the metadata cache before timing.
    benchmark(_run_cached_batch, template.list_blocks, ACCESSOR_CALLS_PER_ROUND)


# =============================================================================
# context-validation benchmarks
# =============================================================================


@pytest.mark.benchmark(group="introspection:required-context-cached")
def test_required_context_small_cached_batch(benchmark: BenchmarkFixture) -> None:
    """Cached required_context() on a small template, batched for stability."""
    env = KidaEnvironment(preserve_ast=True, auto_reload=False)
    template = env.from_string(VALIDATION_TEMPLATE, name="required_context_bench")
    template.required_context()  # Warm dependency analysis before timing.
    benchmark(_run_cached_batch, template.required_context, CONTEXT_CALLS_PER_ROUND)


@pytest.mark.benchmark(group="introspection:validate-context-cached")
def test_validate_context_small_cached_batch(benchmark: BenchmarkFixture) -> None:
    """validate_context() with all required keys present, batched."""
    env = KidaEnvironment(preserve_ast=True, auto_reload=False)
    template = env.from_string(VALIDATION_TEMPLATE, name="validate_context_bench")
    template.template_metadata()  # Warm dependency analysis before timing.
    benchmark(
        lambda: _run_cached_batch(
            lambda: template.validate_context(VALIDATION_CONTEXT),
            CONTEXT_CALLS_PER_ROUND,
        )
    )


# =============================================================================
# get_template_structure() benchmarks
# =============================================================================


@pytest.mark.benchmark(group="introspection:get-template-structure-cached")
def test_get_template_structure_complex_cached_batch(
    benchmark: BenchmarkFixture, kida_env_preserve_ast: KidaEnvironment
) -> None:
    """Cached get_template_structure() on a complex inheritance chain, batched."""
    kida_env_preserve_ast.get_template_structure("complex/page.html")
    benchmark(
        _run_cached_batch,
        lambda: _get_template_structure_complex(kida_env_preserve_ast),
        ACCESSOR_CALLS_PER_ROUND,
    )


# =============================================================================
# render_block() benchmarks
# =============================================================================


@pytest.mark.benchmark(group="introspection:render-block")
def test_render_block_small(benchmark: BenchmarkFixture) -> None:
    """render_block() single block vs full render."""
    env = KidaEnvironment(preserve_ast=True, auto_reload=False)
    template = env.from_string(BLOCKS_TEMPLATE, name="render_block_bench")
    context = {"title": "Benchmark", "items": ["a", "b", "c"]}
    benchmark(template.render_block, "content", **context)


@pytest.mark.benchmark(group="introspection:render-block")
def test_render_block_complex(
    benchmark: BenchmarkFixture,
    kida_env_preserve_ast: KidaEnvironment,
) -> None:
    """render_block() on complex template (page_content block)."""
    from benchmarks.fixtures.context_complex import COMPLEX_CONTEXT

    template = kida_env_preserve_ast.get_template("complex/page.html")
    benchmark(template.render_block, "page_content", **COMPLEX_CONTEXT)


@pytest.mark.benchmark(group="introspection:render-block")
def test_render_full_vs_block_complex(
    benchmark: BenchmarkFixture,
    kida_env_preserve_ast: KidaEnvironment,
) -> None:
    """Full render() for comparison with render_block()."""
    from benchmarks.fixtures.context_complex import COMPLEX_CONTEXT

    template = kida_env_preserve_ast.get_template("complex/page.html")
    benchmark(template.render, **COMPLEX_CONTEXT)


# =============================================================================
# preserve_ast tradeoff benchmarks
# =============================================================================

MEDIUM_SOURCE = """\
{% for item in items %}
<div id="{{ item.id }}">{{ item.name }} - {{ item.data.x }}/{{ item.data.y }}</div>
{% end %}
"""


@pytest.mark.benchmark(group="introspection:preserve-ast", min_rounds=20)
def test_compile_preserve_ast_true(benchmark: BenchmarkFixture) -> None:
    """from_string() with preserve_ast=True (keeps AST for introspection)."""
    env = KidaEnvironment(preserve_ast=True)
    benchmark(env.from_string, MEDIUM_SOURCE, name="preserve_ast_bench")


@pytest.mark.benchmark(group="introspection:preserve-ast", min_rounds=20)
def test_compile_preserve_ast_false(benchmark: BenchmarkFixture) -> None:
    """from_string() with preserve_ast=False (minimal memory footprint)."""
    env = KidaEnvironment(preserve_ast=False)
    benchmark(env.from_string, MEDIUM_SOURCE, name="no_ast_bench")
