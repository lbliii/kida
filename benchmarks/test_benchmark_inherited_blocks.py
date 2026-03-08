"""Benchmarks for inherited block resolution hot paths.

Run with:
    pytest benchmarks/test_benchmark_inherited_blocks.py --benchmark-only -v
"""

from __future__ import annotations

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from kida import DictLoader, Environment


def _build_env() -> Environment:
    """Create a multi-level inheritance graph with mixed block types."""
    templates = {
        "base": (
            "{% block header %}base-header{% endblock %}"
            "{% block sidebar %}base-sidebar{% endblock %}"
            "{% block content %}base-content{% endblock %}"
            "{% fragment oob %}<div>base-oob</div>{% end %}"
        ),
        "layout": (
            '{% extends "base" %}'
            "{% block header %}layout-header{% endblock %}"
            "{% block content %}layout-content{% endblock %}"
        ),
        "page": ('{% extends "layout" %}{% block content %}page-content{% endblock %}'),
    }
    return Environment(loader=DictLoader(templates), auto_reload=False)


@pytest.mark.benchmark(group="inherited-blocks:render-block")
def test_benchmark_inherited_render_block(benchmark: BenchmarkFixture) -> None:
    """Benchmark repeated parent-block rendering through child template."""
    env = _build_env()
    template = env.get_template("page")

    def run() -> str:
        return template.render_block("sidebar")

    result = benchmark(run)
    assert "base-sidebar" in result


@pytest.mark.benchmark(group="inherited-blocks:list-blocks")
def test_benchmark_inherited_list_blocks(benchmark: BenchmarkFixture) -> None:
    """Benchmark repeated inherited block discovery."""
    env = _build_env()
    template = env.get_template("page")

    def run() -> list[str]:
        return template.list_blocks()

    blocks = benchmark(run)
    assert "header" in blocks
    assert "sidebar" in blocks
    assert "content" in blocks
    assert "oob" in blocks


@pytest.mark.benchmark(group="inherited-blocks:bengal-like-cached-template")
def test_benchmark_bengal_like_cached_template(benchmark: BenchmarkFixture) -> None:
    """Simulate Bengal-style repeated inherited block rendering on one template."""
    env = _build_env()
    template = env.get_template("page")
    contexts = [{"page_id": i, "title": f"Page {i}", "active": i % 2 == 0} for i in range(300)]

    def run() -> int:
        # Bengal often renders many inherited fragments repeatedly during build/warm paths.
        output_len = 0
        for ctx in contexts:
            output_len += len(template.render_block("sidebar", **ctx))
            output_len += len(template.render_block("oob", **ctx))
        return output_len

    total_len = benchmark(run)
    assert total_len > 0


@pytest.mark.benchmark(group="inherited-blocks:bengal-like-get-template")
def test_benchmark_bengal_like_get_template_each_time(benchmark: BenchmarkFixture) -> None:
    """Simulate dev-like path where get_template() is hit for many pages."""
    env = _build_env()
    page_count = 200

    def run() -> int:
        total_len = 0
        for i in range(page_count):
            template = env.get_template("page")
            total_len += len(template.render_block("sidebar", page_id=i))
        return total_len

    total_len = benchmark(run)
    assert total_len > 0
