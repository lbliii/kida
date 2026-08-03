"""Contracts for keeping GitHub Actions benchmark artifacts economical."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_full_benchmark_artifact_drops_raw_timing_samples() -> None:
    workflow = (ROOT / ".github/workflows/tests.yml").read_text()

    assert "--benchmark-json=benchmark-results.raw.json" in workflow
    assert "del(.benchmarks[].stats.data)" in workflow
    assert "path: benchmark-results.json" in workflow
    assert "retention-days: 14" in workflow


def test_baseline_artifact_has_bounded_retention() -> None:
    workflow = (ROOT / ".github/workflows/benchmark-baseline.yml").read_text()

    assert "name: benchmark-baseline-linux" in workflow
    assert "retention-days: 14" in workflow
