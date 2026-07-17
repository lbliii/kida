"""Opt-in extraction-advice scaling benchmarks.

Run with: pytest benchmarks/test_benchmark_extraction_advice.py --benchmark-only -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kida.analysis import advise_extraction_source

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def _repeated_forms(count: int = 250) -> str:
    return "\n".join(
        f'<form action="{{{{ item.url }}}}" data-index="{index}">\n'
        f'  <button aria-describedby="help-{index}">Run</button>\n'
        f'  <small id="help-{index}">{{{{ item.name }}}}</small>\n'
        "</form>"
        for index in range(count)
    )


@pytest.mark.benchmark(group="analysis:extraction-advice")
def test_extraction_advice_large_repeated_sibling_corpus(
    benchmark: BenchmarkFixture,
) -> None:
    """Measure 250 equivalent interactive siblings after output sanity."""
    source = _repeated_forms()
    expected = advise_extraction_source(source, name="actions.kida")
    assert len(expected.diagnostics) == 1
    assert len(expected.diagnostics[0].related_locations) == 249

    result = benchmark(advise_extraction_source, source, name="actions.kida")

    assert result == expected


@pytest.mark.benchmark(group="analysis:extraction-advice")
def test_extraction_advice_deep_non_candidate_control_flow(
    benchmark: BenchmarkFixture,
) -> None:
    """Measure a deep valid negative case without manufacturing advice."""
    depth = 200
    source = "{% if true %}" * depth + "{{ value }}" + "{% end %}" * depth
    expected = advise_extraction_source(source, name="deep-control-flow.kida")
    assert expected.diagnostics == ()

    result = benchmark(advise_extraction_source, source, name="deep-control-flow.kida")

    assert result == expected
