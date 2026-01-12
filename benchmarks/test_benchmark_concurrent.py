"""Concurrent rendering benchmarks: Kida vs Jinja2 under free-threading.

This benchmark measures the REAL advantage of Kida on free-threaded Python:
- Single-threaded baseline for both engines
- Multi-threaded scaling with true parallelism (no GIL)

Run with: pytest benchmarks/test_benchmark_concurrent.py --benchmark-only -v
"""

from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from jinja2 import Environment as Jinja2Environment
from pytest_benchmark.fixture import BenchmarkFixture

from kida import Environment as KidaEnvironment

if TYPE_CHECKING:
    pass

# Template source (identical logic for fair comparison)
TEMPLATE_SOURCE_KIDA = """
{% for item in items %}
<div class="item">
  <h2>{{ item.name | upper }}</h2>
  <p>{{ item.description }}</p>
  {% if item.active %}
    <span class="active">Active</span>
  {% end %}
</div>
{% end %}
"""

TEMPLATE_SOURCE_JINJA2 = """
{% for item in items %}
<div class="item">
  <h2>{{ item.name | upper }}</h2>
  <p>{{ item.description }}</p>
  {% if item.active %}
    <span class="active">Active</span>
  {% endif %}
</div>
{% endfor %}
"""

# Test context
CONTEXT = {
    "items": [
        {"name": f"Item {i}", "description": f"Description {i}", "active": i % 2 == 0}
        for i in range(20)
    ]
}


def render_concurrent(
    template,
    context: dict,
    workers: int,
    iterations_per_worker: int,
) -> tuple[float, int]:
    """Render template concurrently and return (elapsed_time, total_renders)."""
    barrier = threading.Barrier(workers)
    render_count = 0
    lock = threading.Lock()

    def worker():
        nonlocal render_count
        barrier.wait()  # Synchronize start for max contention
        local_count = 0
        for _ in range(iterations_per_worker):
            template.render(**context)
            local_count += 1
        with lock:
            render_count += local_count

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker) for _ in range(workers)]
        for f in futures:
            f.result()
    elapsed = time.perf_counter() - start

    return elapsed, render_count


# =============================================================================
# Single-Threaded Baseline
# =============================================================================


@pytest.mark.benchmark(group="concurrent:baseline")
def test_baseline_kida(benchmark: BenchmarkFixture, kida_env: KidaEnvironment) -> None:
    """Kida: Single-threaded baseline (1 worker, 100 renders)."""
    template = kida_env.from_string(TEMPLATE_SOURCE_KIDA)

    def run():
        return render_concurrent(template, CONTEXT, workers=1, iterations_per_worker=100)

    elapsed, count = benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="concurrent:baseline")
def test_baseline_jinja2(benchmark: BenchmarkFixture, jinja2_env: Jinja2Environment) -> None:
    """Jinja2: Single-threaded baseline (1 worker, 100 renders)."""
    template = jinja2_env.from_string(TEMPLATE_SOURCE_JINJA2)

    def run():
        return render_concurrent(template, CONTEXT, workers=1, iterations_per_worker=100)

    elapsed, count = benchmark.pedantic(run, rounds=5, iterations=1)


# =============================================================================
# 2 Workers (2x parallelism)
# =============================================================================


@pytest.mark.benchmark(group="concurrent:2-workers")
def test_2workers_kida(benchmark: BenchmarkFixture, kida_env: KidaEnvironment) -> None:
    """Kida: 2 workers, 50 renders each (100 total)."""
    template = kida_env.from_string(TEMPLATE_SOURCE_KIDA)

    def run():
        return render_concurrent(template, CONTEXT, workers=2, iterations_per_worker=50)

    elapsed, count = benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="concurrent:2-workers")
def test_2workers_jinja2(benchmark: BenchmarkFixture, jinja2_env: Jinja2Environment) -> None:
    """Jinja2: 2 workers, 50 renders each (100 total)."""
    template = jinja2_env.from_string(TEMPLATE_SOURCE_JINJA2)

    def run():
        return render_concurrent(template, CONTEXT, workers=2, iterations_per_worker=50)

    elapsed, count = benchmark.pedantic(run, rounds=5, iterations=1)


# =============================================================================
# 4 Workers (4x parallelism)
# =============================================================================


@pytest.mark.benchmark(group="concurrent:4-workers")
def test_4workers_kida(benchmark: BenchmarkFixture, kida_env: KidaEnvironment) -> None:
    """Kida: 4 workers, 25 renders each (100 total)."""
    template = kida_env.from_string(TEMPLATE_SOURCE_KIDA)

    def run():
        return render_concurrent(template, CONTEXT, workers=4, iterations_per_worker=25)

    elapsed, count = benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="concurrent:4-workers")
def test_4workers_jinja2(benchmark: BenchmarkFixture, jinja2_env: Jinja2Environment) -> None:
    """Jinja2: 4 workers, 25 renders each (100 total)."""
    template = jinja2_env.from_string(TEMPLATE_SOURCE_JINJA2)

    def run():
        return render_concurrent(template, CONTEXT, workers=4, iterations_per_worker=25)

    elapsed, count = benchmark.pedantic(run, rounds=5, iterations=1)


# =============================================================================
# 8 Workers (8x parallelism)
# =============================================================================


@pytest.mark.benchmark(group="concurrent:8-workers")
def test_8workers_kida(benchmark: BenchmarkFixture, kida_env: KidaEnvironment) -> None:
    """Kida: 8 workers, 12-13 renders each (~100 total)."""
    template = kida_env.from_string(TEMPLATE_SOURCE_KIDA)

    def run():
        return render_concurrent(template, CONTEXT, workers=8, iterations_per_worker=13)

    elapsed, count = benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="concurrent:8-workers")
def test_8workers_jinja2(benchmark: BenchmarkFixture, jinja2_env: Jinja2Environment) -> None:
    """Jinja2: 8 workers, 12-13 renders each (~100 total)."""
    template = jinja2_env.from_string(TEMPLATE_SOURCE_JINJA2)

    def run():
        return render_concurrent(template, CONTEXT, workers=8, iterations_per_worker=13)

    elapsed, count = benchmark.pedantic(run, rounds=5, iterations=1)


# =============================================================================
# Summary: Print GIL status at session start
# =============================================================================


def pytest_configure(config):
    """Print free-threading status at test session start."""
    gil_enabled = sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True
    print(f"\n{'=' * 60}")
    print(f"Python {sys.version}")
    print(f"GIL enabled: {gil_enabled}")
    print(f"{'=' * 60}\n")
