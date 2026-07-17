"""Contract tests for the report-only maintainability scorecard."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "maintainability_scorecard.py"


def _load_scorecard_module():
    spec = importlib.util.spec_from_file_location("maintainability_scorecard", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scorecard_module():
    return _load_scorecard_module()


def test_budget_status_reports_targets_ratchets_and_regressions(scorecard_module) -> None:
    budget = scorecard_module.Budget

    assert budget("metric", 2, 3, 1, "max", "items").status == "ratchet"
    assert budget("metric", 1, 3, 1, "max", "items").status == "target"
    assert budget("metric", 4, 3, 1, "max", "items").status == "regressed"
    assert budget("metric", 80.0, 75.0, 95.0, "min", "percent").status == "ratchet"
    assert budget("metric", 95.0, 75.0, 95.0, "min", "percent").status == "target"
    assert budget("metric", 70.0, 75.0, 95.0, "min", "percent").status == "regressed"
    assert budget("metric", None, 75.0, 95.0, "min", "percent").status == "unavailable"


def test_definition_metrics_include_span_and_decision_complexity(
    scorecard_module, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        """\
def choose(left, right):
    if left and right:
        return left
    return right
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(scorecard_module, "ROOT", tmp_path)
    [metric] = scorecard_module._definitions([source])

    assert metric.qualified_name == "choose"
    assert metric.kind == "function"
    assert metric.lines == 4
    assert metric.complexity == 3


def test_critical_coverage_aggregates_only_declared_paths(scorecard_module, tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(
        json.dumps(
            {
                "files": {
                    **{
                        path: {"summary": {"covered_lines": 7, "num_statements": 10}}
                        for path in scorecard_module.CRITICAL_COVERAGE_PATHS
                    },
                    "src/kida/unrelated.py": {
                        "summary": {"covered_lines": 0, "num_statements": 100}
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    percent, missing = scorecard_module._critical_coverage(report)

    assert percent == 70.0
    assert missing == []


def test_repository_scorecard_has_stable_contract(scorecard_module) -> None:
    scorecard = scorecard_module.build_scorecard()
    budgets = scorecard["budgets"]

    assert scorecard["schema_version"] == 1
    assert {budget["name"] for budget in budgets} == set(scorecard_module.RATCHETS)
    assert all(
        budget["status"] in {"target", "ratchet", "regressed", "unavailable"} for budget in budgets
    )
    assert scorecard["scope"]["source_files"] > 0
    assert scorecard["scope"]["test_files"] > 0
    assert len(scorecard["public_api"]["exports"]) == 74
    assert scorecard["public_api"]["undocumented"] == [
        "WorkerEnvironment",
        "strip_colors",
    ]
    undocumented_budget = next(
        budget for budget in budgets if budget["name"] == "undocumented_exports"
    )
    assert undocumented_budget["current"] == 2
    assert undocumented_budget["ratchet"] == 2
    assert scorecard["import_closure"]["error"] is None


def test_report_only_cli_returns_success_when_a_metric_regresses(
    scorecard_module, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    regressed = {
        "scope": {"source_files": 1, "source_lines": 1, "test_files": 1, "test_lines": 1},
        "budgets": [
            {
                "name": "example",
                "current": 2,
                "ratchet": 1,
                "target": 0,
                "direction": "max",
                "unit": "items",
                "status": "regressed",
            }
        ],
    }
    monkeypatch.setattr(scorecard_module, "build_scorecard", lambda **_kwargs: regressed)

    assert scorecard_module.main([]) == 0
    assert "regressed" in capsys.readouterr().out
