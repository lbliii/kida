"""Executable contracts for the human/agent encapsulation replay."""

from __future__ import annotations

import json
from pathlib import Path


def test_calibration_matches_committed_machine_readable_report(example_app) -> None:
    expected = json.loads(example_app.CALIBRATION_PATH.read_text(encoding="utf-8"))
    report = example_app.calibrate()

    assert report == expected
    assert report["summary"] == {
        "behavior_parity_failures": 0,
        "case_count": 5,
        "false_negatives": 0,
        "false_positives": 0,
        "validation_failures": 0,
    }


def test_context_changes_are_explicit_and_boundary_specific(example_app) -> None:
    cases = {item["id"]: item for item in example_app.calibrate()["cases"]}

    assert cases["response-boundary"]["before_without_context_codes"] == []
    assert cases["response-boundary"]["before_codes"] == ["K-MOD-102"]
    assert cases["response-boundary"]["component_names_after"] == ["message_row"]
    assert cases["multiple-roots"]["before_without_context_codes"] == ["K-MOD-103"]
    assert cases["multiple-roots"]["before_codes"] == []
    assert cases["multiple-roots"]["component_names_before"] == [
        "card",
        "public_card",
        "frame",
    ]


def test_analysis_cost_probe_is_bounded_and_kept_out_of_snapshot(example_app) -> None:
    measurement = example_app.measure_analysis(rounds=1)
    snapshot = example_app.calibrate()

    assert measurement["advice_calls"] == 10
    assert measurement["rounds"] == 1
    assert measurement["mean_ms_per_call"] < 500
    assert "measurement" not in snapshot


def test_human_and_agent_guidance_share_the_same_supported_loop(example_app) -> None:
    readme = (Path(example_app.ROOT) / "README.md").read_text(encoding="utf-8")
    public_docs = (
        Path(example_app.ROOT).parents[1] / "site" / "content" / "docs" / "advanced" / "analysis.md"
    ).read_text(encoding="utf-8")

    for phrase in (
        "advise_encapsulation_roots()",
        "diagnose_roots(..., validate_calls=True)",
        "Render before and after",
        "false positives",
        "analysis cost",
    ):
        assert phrase in readme
    assert "Evidence-Driven Encapsulation Loop" in public_docs
    assert "examples/encapsulation_loop" in public_docs
