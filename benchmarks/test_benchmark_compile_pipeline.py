"""Full compile pipeline benchmarks: lex → parse → compile.

Measures env.from_string() for the full pipeline. Reuses template sizes
from test_benchmark_lexer.py.

Run with: pytest benchmarks/test_benchmark_compile_pipeline.py --benchmark-only -v
"""

from __future__ import annotations

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from kida import Environment

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


@pytest.mark.benchmark(group="compile:pipeline:minimal")
def test_compile_minimal(benchmark: BenchmarkFixture) -> None:
    """Full pipeline: minimal template."""
    env = Environment()
    benchmark(env.from_string, MINIMAL)


@pytest.mark.benchmark(group="compile:pipeline:small")
def test_compile_small(benchmark: BenchmarkFixture) -> None:
    """Full pipeline: small template."""
    env = Environment()
    benchmark(env.from_string, SMALL)


@pytest.mark.benchmark(group="compile:pipeline:medium")
def test_compile_medium(benchmark: BenchmarkFixture) -> None:
    """Full pipeline: medium template."""
    env = Environment()
    benchmark(env.from_string, MEDIUM)


@pytest.mark.benchmark(group="compile:pipeline:large")
def test_compile_large(benchmark: BenchmarkFixture) -> None:
    """Full pipeline: large template."""
    env = Environment()
    benchmark(env.from_string, LARGE)
