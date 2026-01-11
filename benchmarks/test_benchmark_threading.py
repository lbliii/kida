"""Concurrency benchmarks to validate thread-safety."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from kida import Environment

TEMPLATE_SOURCE = """
{% for item in items %}
{{ item }}
{% end %}
"""


def render_concurrently(env: Environment, workers: int, iterations: int) -> float:
    """Render a simple template concurrently and return elapsed time (s)."""
    template = env.from_string(TEMPLATE_SOURCE)
    barrier = threading.Barrier(workers)

    def worker() -> None:
        barrier.wait()
        for _ in range(iterations):
            template.render(items=("a", "b", "c", "d"))

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker) for _ in range(workers)]
        for future in futures:
            future.result()
    end = time.perf_counter()
    return end - start


@pytest.mark.benchmark(group="threading:render")
@pytest.mark.parametrize("workers", [1, 2, 4, 8])
def test_threaded_render(
    benchmark: BenchmarkFixture, kida_env: Environment, workers: int, gc_disabled
) -> None:
    # Use pedantic mode for better statistical control in concurrent tests
    benchmark.pedantic(
        render_concurrently,
        args=(kida_env, workers, 100),
        rounds=5,
        iterations=1,
    )
