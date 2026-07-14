"""Contract tests for the measurement-only cold-start phase runner."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "benchmarks" / "benchmark_cold_start_phases.py"
LINUX_BASELINE = (
    ROOT / "benchmarks" / "results" / "cold-start" / "2026-07-13-linux-aarch64-linuxkit.json"
)


@pytest.fixture(scope="module")
def cold_start_module():
    spec = importlib.util.spec_from_file_location("benchmark_cold_start_phases", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample(module, *, elapsed: float, peak: int | None) -> dict[str, object]:
    return {
        "elapsed_ms": elapsed,
        "python_current_bytes": peak,
        "python_peak_bytes": peak,
        "process_peak_rss_before_bytes": 100,
        "process_peak_rss_after_bytes": 200,
        "process_peak_rss_growth_bytes": 100,
        "kida_module_count": 2,
        "kida_source_loc": 20,
        "kida_modules": ["kida", "kida.environment"],
        "kida_modules_missing_source": [],
        "result_type": "str",
    }


def test_nearest_rank_p95_is_deterministic(cold_start_module) -> None:
    assert cold_start_module._nearest_rank_p95(list(range(1, 21))) == 19.0
    assert cold_start_module._nearest_rank_p95([3]) == 3.0


def test_summary_keeps_timing_and_memory_samples_separate(cold_start_module) -> None:
    timing = [
        _sample(cold_start_module, elapsed=1.0, peak=None),
        _sample(cold_start_module, elapsed=3.0, peak=None),
    ]
    memory = [
        _sample(cold_start_module, elapsed=50.0, peak=1000),
        _sample(cold_start_module, elapsed=70.0, peak=3000),
    ]

    summary = cold_start_module._summary(timing, memory)

    assert summary["elapsed_ms"]["median"] == 2.0
    assert summary["python_peak_bytes"]["median"] == 2000.0


def test_report_schema_runs_preflight_before_samples(
    cold_start_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, bool]] = []
    environment = {
        "platform_system": "Darwin",
        "python_implementation": "CPython",
        "free_threading_build": True,
        "gil_enabled": False,
    }

    def fake_worker(
        phase: str,
        *,
        template_dir: Path,
        cache_dir: Path,
        measure_memory: bool = False,
    ) -> dict[str, object]:
        del template_dir, cache_dir
        events.append((phase, measure_memory))
        if phase == "preflight":
            return {"passed": True}
        return _sample(
            cold_start_module,
            elapsed=1.0,
            peak=1024 if measure_memory else None,
        )

    monkeypatch.setattr(cold_start_module, "_environment_metadata", lambda: environment)
    monkeypatch.setattr(cold_start_module, "_run_worker", fake_worker)
    monkeypatch.setattr(
        cold_start_module,
        "_run_process_startup",
        lambda: _sample(cold_start_module, elapsed=1.0, peak=None),
    )

    report = cold_start_module.build_report(
        warmups=0,
        samples=2,
        memory_samples=1,
        require_linux_3_14t=False,
    )

    assert events[0] == ("preflight", False)
    assert report["schema_version"] == 1
    assert report["contract"] == "kida-cold-start-phases-v1"
    assert report["status"] == "development-only"
    assert set(report["phases"]) == set(cold_start_module.PHASES)
    assert report["phases"]["import_kida"]["summary"]["elapsed_ms"]["median"] == 1.0
    assert report["phases"]["import_kida"]["summary"]["python_peak_bytes"]["median"] == 1024.0


def test_official_guard_fails_before_measurement(
    cold_start_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cold_start_module,
        "_environment_metadata",
        lambda: {
            "platform_system": "Darwin",
            "python_implementation": "CPython",
            "free_threading_build": True,
            "gil_enabled": False,
        },
    )

    with pytest.raises(RuntimeError, match=r"Linux CPython 3\.14t"):
        cold_start_module.build_report(
            warmups=0,
            samples=1,
            memory_samples=1,
            require_linux_3_14t=True,
        )


def test_real_preflight_proves_source_warm_and_cache_output(
    cold_start_module,
    tmp_path: Path,
) -> None:
    template_dir = tmp_path / "templates"
    cache_dir = tmp_path / "cache"
    template_dir.mkdir()
    cache_dir.mkdir()
    (template_dir / cold_start_module.TEMPLATE_NAME).write_text(
        cold_start_module.TEMPLATE_SOURCE,
        encoding="utf-8",
    )

    result = cold_start_module._worker_preflight(template_dir, cache_dir)

    assert result["passed"] is True
    assert result["bytecode_cache_artifacts"]


def test_committed_linux_baseline_preserves_capture_contract(cold_start_module) -> None:
    report = json.loads(LINUX_BASELINE.read_text(encoding="utf-8"))

    assert report["schema_version"] == 1
    assert report["contract"] == "kida-cold-start-phases-v1"
    assert report["issue"] == 247
    assert report["status"] == "baseline-candidate"
    assert report["claim_eligible"] is True
    assert report["sanity"]["passed"] is True

    environment = report["environment"]
    assert environment["platform_system"] == "Linux"
    assert environment["platform_machine"] == "aarch64"
    assert environment["python_implementation"] == "CPython"
    assert environment["python_version"] == "3.14.6"
    assert environment["free_threading_build"] is True
    assert environment["gil_enabled"] is False
    assert environment["kida_version"] == "0.12.0"
    assert environment["git_revision"] == "79b5586982acdfa8c0d3a8af06a2cc53ac932579"

    methodology = report["methodology"]
    assert methodology["warmups_per_phase"] == 3
    assert methodology["samples_per_phase"] == 20
    assert methodology["memory_samples_per_phase"] == 5
    assert methodology["child_environment"]["PYTHON_GIL"] == "0"

    for phase in cold_start_module.PHASES:
        phase_report = report["phases"][phase]
        assert len(phase_report["samples"]) == 20
        assert len(phase_report["memory_samples"]) == (0 if phase == "process_startup" else 5)
        assert phase_report["summary"]["elapsed_ms"]["median"] > 0
        assert phase_report["summary"]["elapsed_ms"]["p95"] > 0
