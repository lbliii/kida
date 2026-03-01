"""Compilation scaling benchmarks: inheritance, filter chains, CoW, partial eval, cache.

Targeted benchmarks for the concerns raised in the Kida Maturity Epic:
- Inheritance depth: 1, 5, 10, 25, 50 levels of extends
- Filter chain: 1, 10, 50, 100, 200 (max allowed)
- Copy-on-write: add_filter 10, 100, 500, 1000 times
- Partial evaluator: compile time for 10, 50, 100 nested attribute lookups
- Template cache contention: get_template throughput under 1, 4, 8, 16 threads

Run with: pytest benchmarks/test_benchmark_scaling_depth.py --benchmark-only -v
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from kida import DictLoader, Environment


def _build_inheritance_env(depth: int) -> tuple[Environment, str]:
    templates: dict[str, str] = {"base.html": "{% block content %}Base {{ value }}{% end %}"}
    for i in range(1, depth + 1):
        parent = "base.html" if i == 1 else f"level_{i - 1}.html"
        templates[f"level_{i}.html"] = (
            '{% extends "' + parent + '" %}{% block content %}Level ' + str(i) + "{% end %}"
        )
    env = Environment(loader=DictLoader(templates))
    return env, f"level_{depth}.html"


# =============================================================================
# Inheritance depth scaling
# =============================================================================


@pytest.mark.benchmark(group="scaling-depth:inheritance")
@pytest.mark.parametrize("depth", [1, 5, 10, 25, 50])
def test_inheritance_depth_scaling(
    benchmark: BenchmarkFixture, depth: int
) -> None:
    """Compile + render time for 1, 5, 10, 25, 50 levels of extends."""
    env, template_name = _build_inheritance_env(depth)
    template = env.get_template(template_name)
    benchmark(template.render, value="x")


# =============================================================================
# Filter chain scaling
# =============================================================================


@pytest.mark.benchmark(group="scaling-depth:filters")
@pytest.mark.parametrize("count", [1, 10, 50, 100, 200])
def test_filter_chain_scaling(
    benchmark: BenchmarkFixture, count: int
) -> None:
    """Render time for 1, 10, 50, 100, 200 filters in a chain (max allowed)."""
    filters = " | ".join(["escape" for _ in range(count)])
    env = Environment()
    template = env.from_string(f"{{{{ value | {filters} }}}}")
    benchmark(template.render, value="<script>alert(1)</script>")


# =============================================================================
# Copy-on-write: add_filter scaling
# =============================================================================


@pytest.mark.benchmark(group="scaling-depth:add-filter")
@pytest.mark.parametrize("count", [10, 100, 500, 1000])
def test_add_filter_scaling(benchmark: BenchmarkFixture, count: int) -> None:
    """Time to register N filters via add_filter (O(n^2) total, each call copies dict)."""

    def add_n_filters() -> None:
        env = Environment()
        for i in range(count):
            env.add_filter(f"f{i}", lambda x, i=i: str(x) + str(i))

    benchmark(add_n_filters)


@pytest.mark.benchmark(group="scaling-depth:update-filters")
@pytest.mark.parametrize("count", [10, 100, 500, 1000])
def test_update_filters_scaling(benchmark: BenchmarkFixture, count: int) -> None:
    """Time to register N filters via update_filters (O(n) batch)."""

    def update_n_filters() -> None:
        env = Environment()
        env.update_filters({f"f{i}": (lambda x, i=i: str(x) + str(i)) for i in range(count)})

    benchmark(update_n_filters)


# =============================================================================
# Partial evaluator: nested attribute chain scaling
# =============================================================================


@pytest.mark.benchmark(group="scaling-depth:partial-eval")
@pytest.mark.parametrize("depth", [10, 50, 100])
def test_partial_eval_attribute_chain(
    benchmark: BenchmarkFixture, depth: int
) -> None:
    """Compile time for expressions with N nested attribute lookups."""
    chain = ".".join(f"a{i}" for i in range(depth))
    env = Environment()
    # Build nested dict: {a0: {a1: {a2: ... {aN: "leaf"}}}}
    static: dict[str, object] = {"leaf": "leaf"}
    for i in range(depth - 1, -1, -1):
        static = {f"a{i}": static}

    def compile_and_render() -> str:
        template = env.from_string(f"{{{{ {chain} }}}}")
        return template.render(**static)

    benchmark(compile_and_render)


# =============================================================================
# Template cache contention: get_template throughput
# =============================================================================


def _get_template_throughput(
    env: Environment,
    template_name: str,
    workers: int,
    iterations_per_worker: int,
) -> tuple[float, int]:
    """Concurrent get_template on shared env; return (elapsed, total gets)."""
    barrier = threading.Barrier(workers)
    count = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal count
        barrier.wait()
        for _ in range(iterations_per_worker):
            env.get_template(template_name)
            with lock:
                count += 1

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(worker) for _ in range(workers)]
        for f in futures:
            f.result()
    return time.perf_counter() - start, count


@pytest.mark.benchmark(group="scaling-depth:cache-contention")
@pytest.mark.parametrize("workers", [1, 4, 8, 16])
def test_get_template_cache_contention(
    benchmark: BenchmarkFixture, workers: int
) -> None:
    """get_template throughput under 1, 4, 8, 16 threads (RLock serialization)."""
    env = Environment(loader=DictLoader({"t.html": "{{ x }}"}))
    iterations = max(1, 100 // workers)

    def run() -> tuple[float, int]:
        return _get_template_throughput(env, "t.html", workers, iterations)

    benchmark.pedantic(run, rounds=5, iterations=1)
