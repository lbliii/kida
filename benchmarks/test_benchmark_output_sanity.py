"""Benchmark smoke tests with output-sanity assertions."""

from __future__ import annotations

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from kida import DictLoader, Environment


def _build_env() -> Environment:
    templates = {
        "item": '<li class="member">{{ name }}</li>',
        "base": "{% block content %}{% endblock %}",
        "child": '{% extends "base" %}{% block content %}{% include "item" %}{% endblock %}',
        "stream": "{% for i in range(count) %}<span>{{ i }}</span>{% endfor %}",
        "loop": "{% for x in items %}<li>{{ x }}</li>{% endfor %}",
    }
    return Environment(loader=DictLoader(templates))


@pytest.mark.benchmark(group="render-output-sanity:small")
def test_benchmark_render_small_template_output_sanity(benchmark: BenchmarkFixture) -> None:
    env = _build_env()
    template = env.get_template("loop")
    context = {"items": [f"item-{i}" for i in range(20)]}
    result = benchmark(template.render, **context)
    assert result.count("<li>") == 20
    assert result.count("</li>") == 20


@pytest.mark.benchmark(group="render-output-sanity:inheritance")
def test_benchmark_inherited_blocks_output_not_duplicated(benchmark: BenchmarkFixture) -> None:
    env = _build_env()
    template = env.get_template("child")
    result = benchmark(template.render, name="name-1")
    assert result.count('<li class="member">') == 1
    assert result.count("</li>") == 1


@pytest.mark.benchmark(group="render-output-sanity:stream")
def test_benchmark_stream_output_equals_render_output(benchmark: BenchmarkFixture) -> None:
    env = _build_env()
    template = env.get_template("stream")
    context = {"count": 250}

    def run_stream() -> str:
        return "".join(template.render_stream(**context))

    stream_output = benchmark(run_stream)
    render_output = template.render(**context)
    assert stream_output == render_output


@pytest.mark.benchmark(group="render-output-sanity:include")
def test_benchmark_include_depth_output_count_matches_include_count(
    benchmark: BenchmarkFixture,
) -> None:
    templates = {
        "partial.html": "<li>•</li>",
        "base.html": "\n".join('{% include "partial.html" %}' for _ in range(40)),
    }
    env = Environment(loader=DictLoader(templates))
    template = env.get_template("base.html")
    result = benchmark(template.render)
    assert result.count("<li>•</li>") == 40
