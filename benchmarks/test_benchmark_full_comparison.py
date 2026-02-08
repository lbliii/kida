"""Full Kida vs Jinja2 comparison: Single-threaded AND concurrent.

This benchmark tells the complete story:
1. Single-threaded performance (traditional comparison)
2. Concurrent performance (free-threading advantage)
3. Scaling efficiency (how well each engine parallelizes)

Run with: pytest benchmarks/test_benchmark_full_comparison.py --benchmark-only -v

Templates: Inline definitions (NOT the same as benchmarks/templates/*.html).
These are compact inline templates with identical logic in Kida and Jinja2 syntax,
designed for fair cross-engine comparison. For file-based template benchmarks with
richer contexts, see test_benchmark_render.py.

Template sizes:
- "minimal": Single variable interpolation
- "small": Loop over 10 dict items with filter (upper)
- "medium": Conditional + nested object + loop over 5 posts

Numbers from this file are reported in benchmarks/README.md.

The results show:
- Single-threaded: Kida is ~6-380% faster depending on template size
- Concurrent (8 workers): Kida is ~76% faster due to better parallelism
- Jinja2 has negative scaling at high concurrency (contention)
"""

from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

# =============================================================================
# Template Sources (identical logic, syntax differs)
# =============================================================================

MINIMAL_KIDA = "Hello {{ name }}!"
MINIMAL_JINJA2 = "Hello {{ name }}!"

SMALL_KIDA = """\
{% for item in items %}
  <li>{{ item.name | upper }}</li>
{% end %}
"""

SMALL_JINJA2 = """\
{% for item in items %}
  <li>{{ item.name | upper }}</li>
{% endfor %}
"""

MEDIUM_KIDA = """\
{% if user %}
  <div class="profile">
    <h1>{{ user.name | title }}</h1>
    <p>{{ user.bio | default("No bio") }}</p>
    {% for post in user.posts %}
      <article>
        <h2>{{ post.title }}</h2>
        <p>{{ post.content }}</p>
      </article>
    {% end %}
  </div>
{% else %}
  <p>Please log in.</p>
{% end %}
"""

MEDIUM_JINJA2 = """\
{% if user %}
  <div class="profile">
    <h1>{{ user.name | title }}</h1>
    <p>{{ user.bio | default("No bio") }}</p>
    {% for post in user.posts %}
      <article>
        <h2>{{ post.title }}</h2>
        <p>{{ post.content }}</p>
      </article>
    {% endfor %}
  </div>
{% else %}
  <p>Please log in.</p>
{% endif %}
"""

# =============================================================================
# Test Contexts
# =============================================================================

MINIMAL_CONTEXT = {"name": "World"}

SMALL_CONTEXT = {
    "items": [{"name": f"Item {i}"} for i in range(10)],
}

MEDIUM_CONTEXT = {
    "user": {
        "name": "alice",
        "bio": "Software engineer",
        "posts": [{"title": f"Post {i}", "content": f"Content {i}"} for i in range(5)],
    }
}


# =============================================================================
# Helper for concurrent rendering
# =============================================================================


def render_concurrent(template, context: dict, workers: int, iterations: int) -> float:
    """Render template concurrently, return elapsed time."""
    barrier = threading.Barrier(workers)

    def worker():
        barrier.wait()
        for _ in range(iterations):
            template.render(**context)

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker) for _ in range(workers)]
        for f in futures:
            f.result()
    return time.perf_counter() - start


# =============================================================================
# PART 1: Single-Threaded Comparison
# =============================================================================


@pytest.mark.benchmark(group="1-single:minimal")
def test_single_minimal_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: Minimal template, single-threaded."""
    from kida import Environment

    env = Environment()
    template = env.from_string(MINIMAL_KIDA)
    benchmark(template.render, **MINIMAL_CONTEXT)


@pytest.mark.benchmark(group="1-single:minimal")
def test_single_minimal_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: Minimal template, single-threaded."""
    from jinja2 import Environment

    env = Environment()
    template = env.from_string(MINIMAL_JINJA2)
    benchmark(template.render, **MINIMAL_CONTEXT)


@pytest.mark.benchmark(group="1-single:small")
def test_single_small_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: Small template (loop), single-threaded."""
    from kida import Environment

    env = Environment()
    template = env.from_string(SMALL_KIDA)
    benchmark(template.render, **SMALL_CONTEXT)


@pytest.mark.benchmark(group="1-single:small")
def test_single_small_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: Small template (loop), single-threaded."""
    from jinja2 import Environment

    env = Environment()
    template = env.from_string(SMALL_JINJA2)
    benchmark(template.render, **SMALL_CONTEXT)


@pytest.mark.benchmark(group="1-single:medium")
def test_single_medium_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: Medium template (conditionals + loops), single-threaded."""
    from kida import Environment

    env = Environment()
    template = env.from_string(MEDIUM_KIDA)
    benchmark(template.render, **MEDIUM_CONTEXT)


@pytest.mark.benchmark(group="1-single:medium")
def test_single_medium_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: Medium template (conditionals + loops), single-threaded."""
    from jinja2 import Environment

    env = Environment()
    template = env.from_string(MEDIUM_JINJA2)
    benchmark(template.render, **MEDIUM_CONTEXT)


# =============================================================================
# PART 2: Concurrent Comparison (Free-Threading)
# =============================================================================


@pytest.mark.benchmark(group="2-concurrent:1-worker")
def test_concurrent_1w_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: 1 worker (baseline), 100 renders."""
    from kida import Environment

    env = Environment()
    template = env.from_string(MEDIUM_KIDA)

    def run():
        return render_concurrent(template, MEDIUM_CONTEXT, workers=1, iterations=100)

    benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="2-concurrent:1-worker")
def test_concurrent_1w_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: 1 worker (baseline), 100 renders."""
    from jinja2 import Environment

    env = Environment()
    template = env.from_string(MEDIUM_JINJA2)

    def run():
        return render_concurrent(template, MEDIUM_CONTEXT, workers=1, iterations=100)

    benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="2-concurrent:2-workers")
def test_concurrent_2w_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: 2 workers, 50 renders each."""
    from kida import Environment

    env = Environment()
    template = env.from_string(MEDIUM_KIDA)

    def run():
        return render_concurrent(template, MEDIUM_CONTEXT, workers=2, iterations=50)

    benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="2-concurrent:2-workers")
def test_concurrent_2w_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: 2 workers, 50 renders each."""
    from jinja2 import Environment

    env = Environment()
    template = env.from_string(MEDIUM_JINJA2)

    def run():
        return render_concurrent(template, MEDIUM_CONTEXT, workers=2, iterations=50)

    benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="2-concurrent:4-workers")
def test_concurrent_4w_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: 4 workers, 25 renders each."""
    from kida import Environment

    env = Environment()
    template = env.from_string(MEDIUM_KIDA)

    def run():
        return render_concurrent(template, MEDIUM_CONTEXT, workers=4, iterations=25)

    benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="2-concurrent:4-workers")
def test_concurrent_4w_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: 4 workers, 25 renders each."""
    from jinja2 import Environment

    env = Environment()
    template = env.from_string(MEDIUM_JINJA2)

    def run():
        return render_concurrent(template, MEDIUM_CONTEXT, workers=4, iterations=25)

    benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="2-concurrent:8-workers")
def test_concurrent_8w_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: 8 workers, 13 renders each."""
    from kida import Environment

    env = Environment()
    template = env.from_string(MEDIUM_KIDA)

    def run():
        return render_concurrent(template, MEDIUM_CONTEXT, workers=8, iterations=13)

    benchmark.pedantic(run, rounds=5, iterations=1)


@pytest.mark.benchmark(group="2-concurrent:8-workers")
def test_concurrent_8w_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: 8 workers, 13 renders each."""
    from jinja2 import Environment

    env = Environment()
    template = env.from_string(MEDIUM_JINJA2)

    def run():
        return render_concurrent(template, MEDIUM_CONTEXT, workers=8, iterations=13)

    benchmark.pedantic(run, rounds=5, iterations=1)


# =============================================================================
# Session hooks for summary
# =============================================================================


def pytest_configure(config):
    """Print environment info at session start."""
    gil_enabled = sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True
    print(f"""
{"=" * 70}
KIDA vs JINJA2: Full Performance Comparison
{"=" * 70}
Python: {sys.version.split()[0]} {"(free-threading)" if not gil_enabled else "(GIL enabled)"}
GIL Status: {"DISABLED ✓" if not gil_enabled else "ENABLED"}
{"=" * 70}

PART 1: Single-Threaded Performance
  → Shows baseline per-render speed

PART 2: Concurrent Performance (Free-Threading)
  → Shows parallelism advantage with 1, 2, 4, 8 workers
  → This is where Kida's thread-safe design shines
{"=" * 70}
""")
