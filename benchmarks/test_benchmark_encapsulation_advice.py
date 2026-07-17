"""Opt-in multi-root encapsulation-advice scaling benchmarks.

Run with: pytest benchmarks/test_benchmark_encapsulation_advice.py --benchmark-only -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kida.inspection import TemplateRoot, advise_encapsulation_roots

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_benchmark.fixture import BenchmarkFixture


def _write_component_graph(root: Path, *, count: int, caller_count: int) -> TemplateRoot:
    root.mkdir()
    definitions = ['{% def base(label: str) %}<button type="button">{{ label }}</button>{% end %}']
    imports: list[str] = []
    calls: list[str] = []
    for index in range(count):
        name = f"wrapper_{index}"
        definitions.append(f"{{% def {name}(label: str) %}}{{{{ base(label=label) }}}}{{% end %}}")
        imports.append(name)
        calls.extend(
            f'{{{{ {name}(label="Item {call_index}") }}}}' for call_index in range(caller_count)
        )
    (root / "components.kida").write_text("\n".join(definitions), encoding="utf-8")
    (root / "page.kida").write_text(
        f'{{% from "app/components.kida" import {", ".join(imports)} %}}\n' + "\n".join(calls),
        encoding="utf-8",
    )
    return TemplateRoot("app", root)


@pytest.mark.benchmark(group="analysis:encapsulation-advice")
def test_encapsulation_advice_large_single_caller_graph(
    benchmark: BenchmarkFixture,
    tmp_path: Path,
) -> None:
    """Measure 250 independently actionable pass-through definitions."""
    root = _write_component_graph(tmp_path / "single", count=250, caller_count=1)
    expected = advise_encapsulation_roots((root,))
    assert len(expected.diagnostics) == 250

    result = benchmark(advise_encapsulation_roots, (root,))

    assert result == expected


@pytest.mark.benchmark(group="analysis:encapsulation-advice")
def test_encapsulation_advice_reused_wrapper_negative_graph(
    benchmark: BenchmarkFixture,
    tmp_path: Path,
) -> None:
    """Measure 250 reused wrappers without manufacturing flatten advice."""
    root = _write_component_graph(tmp_path / "reused", count=250, caller_count=2)
    expected = advise_encapsulation_roots((root,))
    assert expected.diagnostics == ()

    result = benchmark(advise_encapsulation_roots, (root,))

    assert result == expected
