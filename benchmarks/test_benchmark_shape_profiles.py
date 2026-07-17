"""Opt-in shape-profile scaling benchmark.

Run with: pytest benchmarks/test_benchmark_shape_profiles.py --benchmark-only -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kida.analysis import profile_source

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def _large_template(regions: int = 250) -> str:
    return "\n".join(
        f'{{% def card_{index}(item) %}}<article data-i="{index}">'
        "{{ item.title }}{% if item.active %}<strong>Active</strong>{% end %}"
        "</article>{% enddef %}"
        for index in range(regions)
    )


@pytest.mark.benchmark(group="analysis:shape-profiles")
def test_shape_profile_large_flat_component_corpus(benchmark: BenchmarkFixture) -> None:
    """Measure a 250-component corpus after checking its output shape."""
    source = _large_template()
    expected = profile_source(source, name="large-components.kida")
    assert len(expected.profiles) == 251
    assert expected.profiles[0].facts.node_count > 2_000

    result = benchmark(profile_source, source, name="large-components.kida")

    assert result == expected


@pytest.mark.benchmark(group="analysis:shape-profiles")
def test_shape_profile_deep_control_flow(benchmark: BenchmarkFixture) -> None:
    """Measure a deliberately deep but valid control-flow chain."""
    depth = 200
    source = "{% if true %}" * depth + "{{ value }}" + "{% end %}" * depth
    expected = profile_source(source, name="deep-control-flow.kida")
    assert len(expected.profiles) == 1
    assert expected.profiles[0].facts.max_depth >= depth

    result = benchmark(profile_source, source, name="deep-control-flow.kida")

    assert result == expected
