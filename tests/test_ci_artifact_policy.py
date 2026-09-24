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


def test_full_suite_coverage_artifact_has_bounded_best_effort_retention() -> None:
    workflow = (ROOT / ".github/workflows/tests.yml").read_text()
    slow_tests = workflow.split("  slow-tests:\n", maxsplit=1)[1].split(
        "\n  # Benchmark regression check", maxsplit=1
    )[0]
    upload = slow_tests.split("- name: Upload full-suite coverage JSON\n", maxsplit=1)[1]

    assert "--cov-report=json:reports/coverage.json" in slow_tests
    assert "name: coverage-${{ github.sha }}" in upload
    assert "path: reports/coverage.json" in upload
    assert "retention-days: 14" in upload
    assert "if-no-files-found: warn" in upload
    assert "if: always()" in upload
    assert "continue-on-error: true" in upload
