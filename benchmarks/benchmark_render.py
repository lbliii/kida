"""Template rendering benchmarks: Kida vs Jinja2.

Run with: pytest benchmarks/benchmark_render.py --benchmark-only
Compare: pytest benchmarks/benchmark_render.py --benchmark-compare
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
