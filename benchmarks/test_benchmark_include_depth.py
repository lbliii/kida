"""Include depth scaling benchmarks.

Measures render time vs number of {% include %} calls (1, 10, 50, 100).
Validates O(n) scaling for include-heavy templates.

Run with: pytest benchmarks/test_benchmark_include_depth.py --benchmark-only -v
"""

from __future__ import annotations

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from kida import DictLoader, Environment

PARTIAL = "<li>•</li>"


def _build_include_env(count: int) -> tuple[Environment, str]:
    """Build env with base that has N static includes."""
    templates: dict[str, str] = {"partial.html": PARTIAL}
    includes = "\n".join('{% include "partial.html" %}' for _ in range(count))
    templates["base.html"] = f"<ul>\n{includes}\n</ul>"
    env = Environment(loader=DictLoader(templates))
    return env, "base.html"


@pytest.mark.benchmark(group="scaling:include-depth")
@pytest.mark.parametrize("count", [1, 10, 50, 100])
def test_include_depth_scaling(benchmark: BenchmarkFixture, count: int) -> None:
    """Render time for 1, 10, 50, 100 {% include %} directives."""
    env, template_name = _build_include_env(count)
    template = env.get_template(template_name)
    benchmark(template.render)
