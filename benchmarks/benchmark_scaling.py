"""Scaling characteristics benchmarks."""

from __future__ import annotations

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from kida import DictLoader, Environment


@pytest.mark.benchmark(group="scaling:variables")
@pytest.mark.parametrize("count", [10, 100, 1000, 10000])
def test_variable_scaling(benchmark: BenchmarkFixture, kida_env: Environment, count: int) -> None:
    # Use discrete variable tags to isolate variable access from loop overhead
    template_source = "".join([f"{{{{ v{i} }}}}" for i in range(count)])
    template = kida_env.from_string(template_source)
    context = {f"v{i}": str(i) for i in range(count)}
    benchmark(template.render, **context)


@pytest.mark.benchmark(group="scaling:loops")
@pytest.mark.parametrize("count", [10, 100, 1000, 5000])
def test_loop_iteration_scaling(
    benchmark: BenchmarkFixture, kida_env: Environment, count: int
) -> None:
    template = kida_env.from_string("{% for item in items %}{{ item }}{% end %}")
    items = list(range(count))
    benchmark(template.render, items=items)


@pytest.mark.benchmark(group="scaling:filters")
@pytest.mark.parametrize("depth", [1, 5, 10, 20])
def test_filter_chain_depth(benchmark: BenchmarkFixture, kida_env: Environment, depth: int) -> None:
    filters = " | ".join(["escape" for _ in range(depth)])
    template = kida_env.from_string(f"{{{{ value | {filters} }}}}")
    benchmark(template.render, value="<script>alert(1)</script>")


def _build_inheritance_env(depth: int) -> tuple[Environment, str]:
    templates: dict[str, str] = {"base.html": "{% block content %}Base {{ value }}{% end %}"}
    for i in range(1, depth + 1):
        parent = "base.html" if i == 1 else f"level_{i - 1}.html"
        templates[f"level_{i}.html"] = (
            f'{{% extends "{parent}" %}}{{% block content %}}Level ' + str(i) + "{% end %}"
        )
    env = Environment(loader=DictLoader(templates))
    return env, f"level_{depth}.html"


@pytest.mark.benchmark(group="scaling:inheritance")
@pytest.mark.parametrize("depth", [1, 3, 5, 10])
def test_inheritance_depth(benchmark: BenchmarkFixture, depth: int) -> None:
    env, template_name = _build_inheritance_env(depth)
    template = env.get_template(template_name)
    benchmark(template.render, value="x")
