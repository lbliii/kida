"""Benchmarks for Kida-specific features: pattern matching, etc.

Compares Kida {% match %} with Jinja2 {% if %}/{% elif %}/{% else %} equivalent.

Run with: pytest benchmarks/test_benchmark_features.py --benchmark-only -v
"""

from __future__ import annotations

import pytest
from jinja2 import Environment as Jinja2Environment
from pytest_benchmark.fixture import BenchmarkFixture

from kida import Environment as KidaEnvironment

# Pattern matching: 5 cases + default
MATCH_KIDA = """\
{% match status %}
{% case "active" %}Active user
{% case "pending" %}Pending verification
{% case "suspended" %}Account suspended
{% case "deleted" %}Account deleted
{% case "archived" %}Archived
{% case _ %}Unknown status
{% end %}
"""

MATCH_JINJA2 = """\
{% if status == "active" %}Active user
{% elif status == "pending" %}Pending verification
{% elif status == "suspended" %}Account suspended
{% elif status == "deleted" %}Account deleted
{% elif status == "archived" %}Archived
{% else %}Unknown status
{% endif %}
"""

# Contexts for different branch distribution
CONTEXT_FIRST = {"status": "active"}
CONTEXT_MIDDLE = {"status": "suspended"}
CONTEXT_LAST = {"status": "archived"}
CONTEXT_DEFAULT = {"status": "unknown"}


# =============================================================================
# Pattern matching benchmarks
# =============================================================================


@pytest.mark.benchmark(group="features:pattern-match:first-case")
def test_match_first_case_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: {% match %} hitting first case."""
    env = KidaEnvironment()
    template = env.from_string(MATCH_KIDA)
    benchmark(template.render, **CONTEXT_FIRST)


@pytest.mark.benchmark(group="features:pattern-match:first-case")
def test_match_first_case_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: {% if %}/{% elif %} hitting first branch."""
    env = Jinja2Environment()
    template = env.from_string(MATCH_JINJA2)
    benchmark(template.render, **CONTEXT_FIRST)


@pytest.mark.benchmark(group="features:pattern-match:middle-case")
def test_match_middle_case_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: {% match %} hitting middle case."""
    env = KidaEnvironment()
    template = env.from_string(MATCH_KIDA)
    benchmark(template.render, **CONTEXT_MIDDLE)


@pytest.mark.benchmark(group="features:pattern-match:middle-case")
def test_match_middle_case_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: {% if %}/{% elif %} hitting middle branch."""
    env = Jinja2Environment()
    template = env.from_string(MATCH_JINJA2)
    benchmark(template.render, **CONTEXT_MIDDLE)


@pytest.mark.benchmark(group="features:pattern-match:default-case")
def test_match_default_case_kida(benchmark: BenchmarkFixture) -> None:
    """Kida: {% match %} hitting default case."""
    env = KidaEnvironment()
    template = env.from_string(MATCH_KIDA)
    benchmark(template.render, **CONTEXT_DEFAULT)


@pytest.mark.benchmark(group="features:pattern-match:default-case")
def test_match_default_case_jinja2(benchmark: BenchmarkFixture) -> None:
    """Jinja2: {% if %}/{% elif %}/{% else %} hitting else."""
    env = Jinja2Environment()
    template = env.from_string(MATCH_JINJA2)
    benchmark(template.render, **CONTEXT_DEFAULT)
