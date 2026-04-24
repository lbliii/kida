"""Full compile pipeline benchmarks: lex → parse → compile.

Measures env.from_string() for the full pipeline. Reuses template sizes
from test_benchmark_lexer.py.

Run with: pytest benchmarks/test_benchmark_compile_pipeline.py --benchmark-only -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kida import Environment

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

COMPILE_CALLS_PER_ROUND = 16
LARGE_COMPILE_CALLS_PER_ROUND = 4

# Reuse template sizes from test_benchmark_lexer.py
MINIMAL = "{{ name }}"

SMALL = """\
{% for item in items %}
  <li>{{ item.name | upper }}</li>
{% end %}
"""

MEDIUM = """\
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

LARGE = MEDIUM * 20


def _compile_batch(source: str, iterations: int) -> int:
    env = Environment(auto_reload=False, preserve_ast=False)
    compiled = 0
    for i in range(iterations):
        template = env.from_string(source, name=f"compile-pipeline-{i}")
        compiled += template.name is not None
    return compiled


@pytest.mark.benchmark(group="compile:pipeline:minimal")
def test_compile_minimal(benchmark: BenchmarkFixture) -> None:
    """Full pipeline: minimal template."""
    total = benchmark(_compile_batch, MINIMAL, COMPILE_CALLS_PER_ROUND)
    assert total == COMPILE_CALLS_PER_ROUND


@pytest.mark.benchmark(group="compile:pipeline:small")
def test_compile_small(benchmark: BenchmarkFixture) -> None:
    """Full pipeline: small template."""
    total = benchmark(_compile_batch, SMALL, COMPILE_CALLS_PER_ROUND)
    assert total == COMPILE_CALLS_PER_ROUND


@pytest.mark.benchmark(group="compile:pipeline:medium")
def test_compile_medium(benchmark: BenchmarkFixture) -> None:
    """Full pipeline: medium template."""
    total = benchmark(_compile_batch, MEDIUM, COMPILE_CALLS_PER_ROUND)
    assert total == COMPILE_CALLS_PER_ROUND


@pytest.mark.benchmark(group="compile:pipeline:large")
def test_compile_large(benchmark: BenchmarkFixture) -> None:
    """Full pipeline: large template."""
    total = benchmark(_compile_batch, LARGE, LARGE_COMPILE_CALLS_PER_ROUND)
    assert total == LARGE_COMPILE_CALLS_PER_ROUND
