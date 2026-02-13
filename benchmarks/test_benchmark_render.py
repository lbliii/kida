"""Template rendering benchmarks: Kida vs Jinja2 (file-based templates).

Templates: File-based from benchmarks/templates/ with rich contexts from
benchmarks/fixtures/. These are more realistic than the inline templates in
test_benchmark_full_comparison.py, but use different template sources and contexts.

Template sizes:
- "minimal": Single variable (templates/minimal.html)
- "small": 12 context vars, loop over 5 string items (templates/small.html)
- "medium": ~100 context vars, multiple loops with filters (templates/medium.html)
- "large": 1000 loop items (templates/large.html)
- "complex": 3-level template inheritance chain (templates/complex/)

Numbers from this file are reported in site/content/docs/about/performance.md.

Run with: pytest benchmarks/test_benchmark_render.py --benchmark-only
Compare: pytest benchmarks/test_benchmark_render.py --benchmark-compare
"""

from __future__ import annotations

import pytest
from jinja2 import Environment as Jinja2Environment
from pytest_benchmark.fixture import BenchmarkFixture

from kida import Environment as KidaEnvironment


@pytest.mark.benchmark(group="render:minimal")
def test_render_minimal_kida(benchmark: BenchmarkFixture, kida_env: KidaEnvironment) -> None:
    template = kida_env.get_template("minimal.html")
    benchmark(template.render, name="Benchmark")


@pytest.mark.benchmark(group="render:minimal")
def test_render_minimal_jinja2(benchmark: BenchmarkFixture, jinja2_env: Jinja2Environment) -> None:
    template = jinja2_env.get_template("minimal.html")
    benchmark(template.render, name="Benchmark")


@pytest.mark.benchmark(group="render:small")
def test_render_small_kida(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    small_context: dict[str, object],
) -> None:
    template = kida_env.get_template("small.html")
    benchmark(template.render, **small_context)


@pytest.mark.benchmark(group="render:small")
def test_render_small_jinja2(
    benchmark: BenchmarkFixture,
    jinja2_env: Jinja2Environment,
    small_context: dict[str, object],
) -> None:
    template = jinja2_env.get_template("small.html")
    benchmark(template.render, **small_context)


@pytest.mark.benchmark(group="render:medium")
def test_render_medium_kida(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    medium_context: dict[str, object],
) -> None:
    template = kida_env.get_template("medium.html")
    benchmark(template.render, **medium_context)


@pytest.mark.benchmark(group="render:profiling-overhead")
def test_render_medium_profiling_off_kida(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    medium_context: dict[str, object],
) -> None:
    """Kida: Sync render baseline (profiling disabled)."""
    template = kida_env.get_template("medium.html")
    benchmark(template.render, **medium_context)


@pytest.mark.benchmark(group="render:profiling-overhead")
def test_render_medium_profiling_on_kida(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    medium_context: dict[str, object],
) -> None:
    """Kida: Sync render with profiled_render() context (profiling enabled)."""
    from kida.render_accumulator import profiled_render

    template = kida_env.get_template("medium.html")

    def run():
        with profiled_render():
            return template.render(**medium_context)

    benchmark(run)


@pytest.mark.benchmark(group="render:medium")
def test_render_medium_jinja2(
    benchmark: BenchmarkFixture,
    jinja2_env: Jinja2Environment,
    medium_context: dict[str, object],
) -> None:
    template = jinja2_env.get_template("medium.html")
    benchmark(template.render, **medium_context)


@pytest.mark.benchmark(group="render:large")
def test_render_large_kida(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    large_context: dict[str, object],
) -> None:
    template = kida_env.get_template("large.html")
    benchmark(template.render, **large_context)


@pytest.mark.benchmark(group="render:large")
def test_render_large_jinja2(
    benchmark: BenchmarkFixture,
    jinja2_env: Jinja2Environment,
    large_context: dict[str, object],
) -> None:
    template = jinja2_env.get_template("large.html")
    benchmark(template.render, **large_context)


@pytest.mark.benchmark(group="render:complex")
def test_render_complex_kida(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    complex_context: dict[str, object],
) -> None:
    template = kida_env.get_template("complex/page.html")
    benchmark(template.render, **complex_context)


@pytest.mark.benchmark(group="render:complex")
def test_render_complex_jinja2(
    benchmark: BenchmarkFixture,
    jinja2_env: Jinja2Environment,
    complex_context: dict[str, object],
) -> None:
    template = jinja2_env.get_template("complex/page.html")
    benchmark(template.render, **complex_context)


# =============================================================================
# Async Rendering (Kida: render_async via asyncio.to_thread)
# =============================================================================


@pytest.mark.benchmark(group="render-async:medium")
def test_render_async_medium_kida(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    medium_context: dict[str, object],
) -> None:
    """Kida: Async render (asyncio.to_thread) for medium template."""
    import asyncio

    template = kida_env.get_template("medium.html")

    def run():
        return asyncio.run(template.render_async(**medium_context))

    benchmark(run)


@pytest.mark.benchmark(group="render-async:medium")
def test_render_sync_medium_kida_baseline(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    medium_context: dict[str, object],
) -> None:
    """Kida: Sync render baseline for async comparison."""
    template = kida_env.get_template("medium.html")
    benchmark(template.render, **medium_context)


@pytest.mark.benchmark(group="render-async:large")
def test_render_async_large_kida(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    large_context: dict[str, object],
) -> None:
    """Kida: Async render (asyncio.to_thread) for large template."""
    import asyncio

    template = kida_env.get_template("large.html")

    def run():
        return asyncio.run(template.render_async(**large_context))

    benchmark(run)


@pytest.mark.benchmark(group="render-async:large")
def test_render_sync_large_kida_baseline(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    large_context: dict[str, object],
) -> None:
    """Kida: Sync render baseline for async comparison."""
    template = kida_env.get_template("large.html")
    benchmark(template.render, **large_context)


# =============================================================================
# Compilation Benchmarks (all template sizes)
# =============================================================================


@pytest.mark.benchmark(group="compile:small")
def test_compile_small_kida(
    benchmark: BenchmarkFixture, kida_env: KidaEnvironment, template_loader
) -> None:
    source = template_loader("small.html", engine="kida")
    benchmark(kida_env.from_string, source)


@pytest.mark.benchmark(group="compile:small")
def test_compile_small_jinja2(
    benchmark: BenchmarkFixture,
    jinja2_env: Jinja2Environment,
    template_loader,
) -> None:
    source = template_loader("small.html", engine="jinja2")
    benchmark(jinja2_env.from_string, source)


@pytest.mark.benchmark(group="compile:medium")
def test_compile_medium_kida(
    benchmark: BenchmarkFixture, kida_env: KidaEnvironment, template_loader
) -> None:
    source = template_loader("medium.html", engine="kida")
    benchmark(kida_env.from_string, source)


@pytest.mark.benchmark(group="compile:medium")
def test_compile_medium_jinja2(
    benchmark: BenchmarkFixture,
    jinja2_env: Jinja2Environment,
    template_loader,
) -> None:
    source = template_loader("medium.html", engine="jinja2")
    benchmark(jinja2_env.from_string, source)


@pytest.mark.benchmark(group="compile:large")
def test_compile_large_kida(
    benchmark: BenchmarkFixture, kida_env: KidaEnvironment, template_loader
) -> None:
    source = template_loader("large.html", engine="kida")
    benchmark(kida_env.from_string, source)


@pytest.mark.benchmark(group="compile:large")
def test_compile_large_jinja2(
    benchmark: BenchmarkFixture,
    jinja2_env: Jinja2Environment,
    template_loader,
) -> None:
    source = template_loader("large.html", engine="jinja2")
    benchmark(jinja2_env.from_string, source)


@pytest.mark.benchmark(group="compile:complex")
def test_compile_complex_kida(
    benchmark: BenchmarkFixture, kida_env: KidaEnvironment, template_loader
) -> None:
    source = template_loader("complex/page.html", engine="kida")
    benchmark(kida_env.from_string, source)


@pytest.mark.benchmark(group="compile:complex")
def test_compile_complex_jinja2(
    benchmark: BenchmarkFixture,
    jinja2_env: Jinja2Environment,
    template_loader,
) -> None:
    source = template_loader("complex/page.html", engine="jinja2")
    benchmark(jinja2_env.from_string, source)


# =============================================================================
# Bytecode cache: compile vs load from cache
# =============================================================================


@pytest.mark.benchmark(group="compile:bytecode-cache-hit")
def test_load_from_bytecode_cache_kida(
    benchmark: BenchmarkFixture, kida_env: KidaEnvironment
) -> None:
    """Kida: get_template() when bytecode cache is warm (cache hit)."""
    # Warm the cache
    kida_env.get_template("small.html")

    def run():
        return kida_env.get_template("small.html")

    benchmark(run)


@pytest.mark.benchmark(group="compile:bytecode-cache-hit")
def test_compile_from_string_kida(
    benchmark: BenchmarkFixture, kida_env: KidaEnvironment, template_loader
) -> None:
    """Kida: from_string() compiles from source (no bytecode cache)."""
    source = template_loader("small.html", engine="kida")
    benchmark(kida_env.from_string, source)


# =============================================================================
# Kida Specific Features
# =============================================================================


@pytest.mark.benchmark(group="kida:t-string")
def test_render_t_string_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: Optimized t-string interpolation (k-tag)."""
    from kida import k

    def run():
        name = "World"
        items = ["a", "b", "c"]
        # Use t-string literal for zero-parser-overhead interpolation
        return k(t"Hello {name}, items: {items}")

    benchmark(run)


@pytest.mark.benchmark(group="kida:fragment-cache-hit")
def test_render_fragment_cache_kida(benchmark: BenchmarkFixture, kida_env: KidaEnvironment) -> None:
    """Kida: Fragment caching via {% cache %} (cache hit).

    This feature is unique to Kida and provides significant speedups for
    partially static templates.
    """
    source = """
    {% cache "bench-key", ttl=300 %}
        <ul>
        {% for i in range(100) %}
            <li>Item {{ i }}</li>
        {% end %}
        </ul>
    {% end %}
    """
    template = kida_env.from_string(source)
    # Warm up the cache
    template.render()
    # Benchmark cache hit performance
    benchmark(template.render)


@pytest.mark.benchmark(group="kida:fragment-cache-cold")
def test_render_fragment_cache_cold_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: Fragment caching via {% cache %} (cold, first render).

    Measures first render when fragment cache is empty (new env per iteration).
    """
    source = """
    {% cache "bench-key", ttl=300 %}
        <ul>
        {% for i in range(100) %}
            <li>Item {{ i }}</li>
        {% end %}
        </ul>
    {% end %}
    """

    def run():
        env = KidaEnvironment()
        template = env.from_string(source)
        return template.render()

    benchmark(run)
