"""Drift checks for the reviewed adapter advice-context contract."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import kida
import kida.analysis as analysis
from kida.analysis import AdviceContext, AdviceFactValue

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "audit" / "adapter-advice-context-contract.md"


def test_contract_freezes_generic_semantics_and_compatibility_boundaries() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    for heading in (
        "## Public Record And Entry Point",
        "## Generic Fact Vocabulary",
        "## Span Matching And Boundary Semantics",
        "## Determinism And Degraded Operation",
        "## Compatibility Boundaries",
        "## Required Proof And Collateral",
    ):
        assert heading in contract
    for decision in (
        "consumer_context",
        "preserve_boundary",
        "response_boundary",
        "role",
        "visibility",
        "Unknown fact names and unrecognized values are ignored",
        "Only a nested candidate may be reported",
        "adds no CLI flag",
        "Kida does not import or name Chirp, HTMX, OOB",
    ):
        assert decision in contract


def test_public_record_is_additive_and_has_exact_frozen_shape() -> None:
    assert {"AdviceContext", "AdviceFactValue"} <= set(analysis.__all__)
    assert "AdviceContext" not in kida.__all__
    assert "AdviceFactValue" not in kida.__all__
    assert [field.name for field in fields(AdviceContext)] == ["span", "facts"]
    assert AdviceFactValue is not None
