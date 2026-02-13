"""Streaming render benchmarks: render() vs render_stream() (full consume).

Compares StringBuilder-based render() with generator-based render_stream()
for total time and time-to-first-chunk. Includes Jinja2 generate() comparison.

Run with: pytest benchmarks/test_benchmark_streaming.py --benchmark-only -v
"""

from __future__ import annotations

import time

import pytest
from jinja2 import Environment as Jinja2Environment
from pytest_benchmark.fixture import BenchmarkFixture

from kida import Environment as KidaEnvironment

# Inline templates for fair comparison (identical logic)
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

MINIMAL_CONTEXT = {"name": "World"}
SMALL_CONTEXT = {"items": [{"name": f"Item {i}"} for i in range(10)]}
MEDIUM_CONTEXT = {
    "user": {
        "name": "alice",
        "bio": "Software engineer",
        "posts": [
            {"title": f"Post {i}", "content": f"Content {i}"} for i in range(5)
        ],
    }
}


# =============================================================================
# render() vs render_stream() full consume
# =============================================================================


@pytest.mark.benchmark(group="streaming:render-vs-stream:minimal")
def test_render_minimal_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: render() for minimal template."""
    env = KidaEnvironment()
    template = env.from_string(MINIMAL_KIDA)
    benchmark(template.render, **MINIMAL_CONTEXT)


@pytest.mark.benchmark(group="streaming:render-vs-stream:minimal")
def test_render_stream_minimal_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: render_stream() full consume for minimal template."""
    env = KidaEnvironment()
    template = env.from_string(MINIMAL_KIDA)

    def run():
        return "".join(template.render_stream(**MINIMAL_CONTEXT))

    benchmark(run)


@pytest.mark.benchmark(group="streaming:render-vs-stream:small")
def test_render_small_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: render() for small template."""
    env = KidaEnvironment()
    template = env.from_string(SMALL_KIDA)
    benchmark(template.render, **SMALL_CONTEXT)


@pytest.mark.benchmark(group="streaming:render-vs-stream:small")
def test_render_stream_small_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: render_stream() full consume for small template."""
    env = KidaEnvironment()
    template = env.from_string(SMALL_KIDA)

    def run():
        return "".join(template.render_stream(**SMALL_CONTEXT))

    benchmark(run)


@pytest.mark.benchmark(group="streaming:render-vs-stream:medium")
def test_render_medium_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: render() for medium template."""
    env = KidaEnvironment()
    template = env.from_string(MEDIUM_KIDA)
    benchmark(template.render, **MEDIUM_CONTEXT)


@pytest.mark.benchmark(group="streaming:render-vs-stream:medium")
def test_render_stream_medium_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: render_stream() full consume for medium template."""
    env = KidaEnvironment()
    template = env.from_string(MEDIUM_KIDA)

    def run():
        return "".join(template.render_stream(**MEDIUM_CONTEXT))

    benchmark(run)


@pytest.mark.benchmark(group="streaming:render-vs-stream:medium")
def test_generate_medium_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: generate() full consume for medium template."""
    env = Jinja2Environment()
    template = env.from_string(MEDIUM_JINJA2)

    def run():
        return "".join(template.generate(**MEDIUM_CONTEXT))

    benchmark(run)


# =============================================================================
# Time to first chunk
# =============================================================================


def _time_to_first_chunk_kida(template, context: dict) -> float:
    """Measure time until first chunk is yielded (ns)."""
    stream = template.render_stream(**context)
    start = time.perf_counter_ns()
    next(stream)
    return time.perf_counter_ns() - start


@pytest.mark.benchmark(group="streaming:time-to-first-chunk:small")
def test_time_to_first_chunk_small_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: Time to first chunk for small template."""
    env = KidaEnvironment()
    template = env.from_string(SMALL_KIDA)
    benchmark(_time_to_first_chunk_kida, template, SMALL_CONTEXT)


@pytest.mark.benchmark(group="streaming:time-to-first-chunk:medium")
def test_time_to_first_chunk_medium_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: Time to first chunk for medium template."""
    env = KidaEnvironment()
    template = env.from_string(MEDIUM_KIDA)
    benchmark(_time_to_first_chunk_kida, template, MEDIUM_CONTEXT)
