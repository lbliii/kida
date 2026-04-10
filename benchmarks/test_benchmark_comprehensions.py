"""Benchmarks for list comprehension rendering performance.

Measures comprehension rendering at various iterable sizes and compares
against equivalent for-loop patterns to quantify overhead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

    from kida import Environment as KidaEnvironment


@pytest.mark.benchmark(group="comprehensions:basic")
@pytest.mark.parametrize("count", [10, 100, 1000])
def test_listcomp_render(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    count: int,
) -> None:
    """Benchmark basic list comprehension: [x * 2 for x in items]."""
    template = kida_env.from_string("{{ [x * 2 for x in items] }}")
    items = list(range(count))
    benchmark(template.render, items=items)


@pytest.mark.benchmark(group="comprehensions:filtered")
@pytest.mark.parametrize("count", [10, 100, 1000])
def test_listcomp_with_condition(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    count: int,
) -> None:
    """Benchmark filtered list comprehension: [x for x in items if x > threshold]."""
    template = kida_env.from_string("{{ [x for x in items if x > threshold] }}")
    items = list(range(count))
    benchmark(template.render, items=items, threshold=count // 2)


@pytest.mark.benchmark(group="comprehensions:for-loop-baseline")
@pytest.mark.parametrize("count", [10, 100, 1000])
def test_for_loop_baseline(
    benchmark: BenchmarkFixture,
    kida_env: KidaEnvironment,
    count: int,
) -> None:
    """Baseline: equivalent for-loop rendering for comparison."""
    template = kida_env.from_string(
        "{% for x in items %}{{ x * 2 }}{% if not loop.last %}, {% end %}{% end %}"
    )
    items = list(range(count))
    benchmark(template.render, items=items)
