"""Benchmarks for template introspection APIs.

Measures template_metadata(), list_blocks(), get_template_structure(),
and render_block() — used by Bengal, Chirp, and composition workflows.

Run with: pytest benchmarks/test_benchmark_introspection.py --benchmark-only -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from kida import Environment as KidaEnvironment
from kida import FileSystemLoader as KidaFileSystemLoader

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"

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


@pytest.mark.benchmark(group="introspection:template-metadata")
def test_template_metadata_small(benchmark: BenchmarkFixture) -> None:
    """template_metadata() on small template with blocks."""
    env = KidaEnvironment(preserve_ast=True, auto_reload=False)
    template = env.from_string(BLOCKS_TEMPLATE, name="introspection_bench")
    benchmark(template.template_metadata)


@pytest.mark.benchmark(group="introspection:template-metadata")
def test_template_metadata_complex(
    benchmark: BenchmarkFixture, kida_env_preserve_ast: KidaEnvironment
) -> None:
    """template_metadata() on complex inheritance chain."""
    template = kida_env_preserve_ast.get_template("complex/page.html")
    benchmark(template.template_metadata)


# =============================================================================
# list_blocks() benchmarks
# =============================================================================


@pytest.mark.benchmark(group="introspection:list-blocks")
def test_list_blocks_small(benchmark: BenchmarkFixture) -> None:
    """list_blocks() on template with 2 blocks."""
    env = KidaEnvironment(preserve_ast=True, auto_reload=False)
    template = env.from_string(BLOCKS_TEMPLATE, name="list_blocks_bench")
    benchmark(template.list_blocks)


@pytest.mark.benchmark(group="introspection:list-blocks")
def test_list_blocks_complex(
    benchmark: BenchmarkFixture, kida_env_preserve_ast: KidaEnvironment
) -> None:
    """list_blocks() on complex inheritance chain (multiple blocks)."""
    template = kida_env_preserve_ast.get_template("complex/page.html")
    benchmark(template.list_blocks)


# =============================================================================
# get_template_structure() benchmarks
# =============================================================================


@pytest.mark.benchmark(group="introspection:get-template-structure")
def test_get_template_structure_complex(
    benchmark: BenchmarkFixture, kida_env_preserve_ast: KidaEnvironment
) -> None:
    """get_template_structure() on complex inheritance chain."""
    benchmark(kida_env_preserve_ast.get_template_structure, "complex/page.html")


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
