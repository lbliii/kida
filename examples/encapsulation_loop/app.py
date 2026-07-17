"""Reproducible before/after calibration for Kida encapsulation advice."""

import argparse
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, final

from kida import Environment, FileSystemLoader, PrefixLoader
from kida.analysis import AdviceContext, profile_source
from kida.diagnostics import Diagnostic, DiagnosticOptions
from kida.inspection import (
    TemplateRoot,
    advise_encapsulation_roots,
    diagnose_roots,
    inspect_components,
)

ROOT = Path(__file__).parent
CASES_ROOT = ROOT / "cases"
CALIBRATION_PATH = ROOT / "calibration.json"

_MESSAGES = [
    {
        "author": {"avatar": "/ada.png", "id": "u1", "name": "Ada"},
        "body": "Evidence should stay inspectable.",
        "created_at": "2026-07-17T19:00:00Z",
        "id": "m1",
        "permalink": "/messages/m1",
        "relative_time": "now",
    }
]


@final
@dataclass(frozen=True, slots=True)
class _Case:
    name: str
    decision: str
    expected_before_candidates: tuple[str, ...]
    expected_after_candidates: tuple[str, ...]
    render_context: dict[str, Any]
    context_kind: str | None = None
    response_block: str | None = None


_CASES = (
    _Case(
        "growing-route",
        "extract-message-row",
        ("K-MOD-102@app/page.kida:5:7-27:16",),
        (),
        {"current_user": {"id": "u1"}, "messages": _MESSAGES},
    ),
    _Case(
        "healthy-layout",
        "keep-layout-intact",
        (),
        (),
        {
            "body_html": "<article>Account</article>",
            "footer_links": [{"label": "Privacy", "url": "/privacy"}],
            "navigation": [{"current": True, "label": "Home", "url": "/"}],
            "site": {
                "description": "A healthy large layout",
                "name": "Kida",
                "notice": "",
                "title": "Account",
            },
        },
    ),
    _Case(
        "pass-through-component",
        "inline-pass-through-wrapper",
        ("K-MOD-103@app/components.kida:5:3-7:9",),
        (),
        {},
    ),
    _Case(
        "response-boundary",
        "preserve-response-and-extract-message-row",
        ("K-MOD-102@app/page.kida:6:7-28:16",),
        (),
        {"current_user": {"id": "u1"}, "messages": _MESSAGES},
        context_kind="response",
        response_block="messages_oob",
    ),
    _Case(
        "multiple-roots",
        "preserve-public-app-boundary",
        (),
        (),
        {},
        context_kind="public",
    ),
)

_EVIDENCE_KEYS = frozenset(
    {
        "advice_context",
        "candidate_kind",
        "component_name",
        "downstream_component",
        "forwarded_props",
        "forwarded_slots",
        "possible_slots",
        "signals",
        "tentative_props",
    }
)


def _stage_path(case: _Case, stage: str) -> Path:
    return CASES_ROOT / case.name / stage


def _roots(case: _Case, stage: str) -> tuple[TemplateRoot, ...]:
    stage_path = _stage_path(case, stage)
    return tuple(
        TemplateRoot(path.name, path) for path in sorted(stage_path.iterdir()) if path.is_dir()
    )


def _environment(case: _Case, stage: str) -> Environment:
    roots = _roots(case, stage)
    return Environment(
        loader=PrefixLoader({root.namespace: FileSystemLoader(root.path) for root in roots}),
        bytecode_cache=False,
    )


def _context(case: _Case, stage: str) -> tuple[AdviceContext, ...]:
    if case.context_kind is None:
        return ()
    name = "app/page.kida" if case.context_kind == "response" else "app/components.kida"
    source = (_stage_path(case, stage) / name).read_text(encoding="utf-8")
    profiles = profile_source(source, name=name)
    if case.context_kind == "response":
        profile = next(
            item
            for item in profiles.profiles
            if item.kind == "block" and item.name == case.response_block
        )
        return (
            AdviceContext(
                profile.span,
                (
                    ("consumer_context", "repeated"),
                    ("preserve_boundary", True),
                    ("response_boundary", True),
                    ("role", "adapter-response"),
                ),
            ),
        )
    profile = next(
        item
        for item in profiles.profiles
        if item.kind == "definition" and item.name == "public_card"
    )
    return (
        AdviceContext(profile.span, (("role", "application-component"), ("visibility", "public"))),
    )


def _advice(case: _Case, stage: str, *, include_context: bool) -> tuple[Diagnostic, ...]:
    report = advise_encapsulation_roots(
        _roots(case, stage),
        context=_context(case, stage) if include_context else (),
    )
    assert report.partial is False
    return report.diagnostics


def _normalize_html(value: str) -> str:
    return re.sub(r">\s+<", "><", " ".join(value.split())).strip()


def _render(case: _Case, stage: str) -> dict[str, str]:
    template = _environment(case, stage).get_template("app/page.kida")
    rendered = {"page": _normalize_html(template.render(**case.render_context))}
    if case.response_block is not None:
        rendered["response_block"] = _normalize_html(
            template.render_block(case.response_block, case.render_context)
        )
    return rendered


def _diagnostic_payload(diagnostic: Diagnostic) -> dict[str, object]:
    assert diagnostic.span.start is not None
    assert diagnostic.span.end is not None
    metadata = {name: value for name, value in diagnostic.metadata if name in _EVIDENCE_KEYS}
    return {
        "code": diagnostic.code,
        "confidence": diagnostic.confidence.value,
        "evidence": metadata,
        "kind": diagnostic.kind,
        "span": {
            "end": [diagnostic.span.end.line, diagnostic.span.end.column],
            "path": diagnostic.span.path,
            "start": [diagnostic.span.start.line, diagnostic.span.start.column],
        },
    }


def _candidate_marker(diagnostic: Diagnostic) -> str:
    assert diagnostic.span.start is not None
    assert diagnostic.span.end is not None
    return (
        f"{diagnostic.code}@{diagnostic.span.path}:"
        f"{diagnostic.span.start.line}:{diagnostic.span.start.column}-"
        f"{diagnostic.span.end.line}:{diagnostic.span.end.column}"
    )


def _difference(actual: tuple[str, ...], expected: tuple[str, ...]) -> tuple[list[str], list[str]]:
    actual_counts = Counter(actual)
    expected_counts = Counter(expected)
    false_positives = sorted((actual_counts - expected_counts).elements())
    false_negatives = sorted((expected_counts - actual_counts).elements())
    return false_positives, false_negatives


def _component_names(case: _Case, stage: str) -> list[str]:
    inspection = inspect_components(_roots(case, stage))
    assert inspection.partial is False
    assert inspection.diagnostics == ()
    return [record.metadata.name for record in inspection.components]


def _validation_codes(case: _Case, stage: str) -> list[str]:
    report = diagnose_roots(
        _roots(case, stage),
        options=DiagnosticOptions(validate_calls=True),
    )
    assert report.partial is False
    return [item.code for item in report.diagnostics]


def calibrate() -> dict[str, object]:
    """Return the deterministic replay report consumed by tests and agents."""
    cases: list[dict[str, object]] = []
    false_positive_count = 0
    false_negative_count = 0
    for case in _CASES:
        raw_before = _advice(case, "before", include_context=False)
        before = _advice(case, "before", include_context=True)
        after = _advice(case, "after", include_context=True)
        before_codes = tuple(item.code for item in before)
        after_codes = tuple(item.code for item in after)
        before_candidates = tuple(_candidate_marker(item) for item in before)
        after_candidates = tuple(_candidate_marker(item) for item in after)
        before_fp, before_fn = _difference(
            before_candidates,
            case.expected_before_candidates,
        )
        after_fp, after_fn = _difference(after_candidates, case.expected_after_candidates)
        false_positives = [*before_fp, *after_fp]
        false_negatives = [*before_fn, *after_fn]
        false_positive_count += len(false_positives)
        false_negative_count += len(false_negatives)
        before_render = _render(case, "before")
        after_render = _render(case, "after")
        cases.append(
            {
                "after_codes": list(after_codes),
                "before_codes": list(before_codes),
                "before_without_context_codes": [item.code for item in raw_before],
                "behavior_equal": before_render == after_render,
                "component_names_after": _component_names(case, "after"),
                "component_names_before": _component_names(case, "before"),
                "decision": case.decision,
                "evidence": [_diagnostic_payload(item) for item in before],
                "expected_after_candidates": list(case.expected_after_candidates),
                "expected_before_candidates": list(case.expected_before_candidates),
                "false_negatives": false_negatives,
                "false_positives": false_positives,
                "id": case.name,
                "validation_codes_after": _validation_codes(case, "after"),
                "validation_codes_before": _validation_codes(case, "before"),
            }
        )
    return {
        "cases": cases,
        "contract": "kida.encapsulation-loop-calibration",
        "contract_version": 1,
        "summary": {
            "behavior_parity_failures": sum(not item["behavior_equal"] for item in cases),
            "case_count": len(cases),
            "false_negatives": false_negative_count,
            "false_positives": false_positive_count,
            "validation_failures": sum(
                bool(item["validation_codes_before"] or item["validation_codes_after"])
                for item in cases
            ),
        },
    }


def measure_analysis(*, rounds: int = 5) -> dict[str, object]:
    """Measure end-to-end advisory calls without putting timing in the snapshot."""
    if rounds < 1:
        raise ValueError("rounds must be at least 1")
    calls = 0
    started = time.perf_counter()
    for _round in range(rounds):
        for case in _CASES:
            for stage in ("before", "after"):
                _advice(case, stage, include_context=True)
                calls += 1
    elapsed_ms = (time.perf_counter() - started) * 1_000
    return {
        "advice_calls": calls,
        "mean_ms_per_call": round(elapsed_ms / calls, 3),
        "rounds": rounds,
        "total_ms": round(elapsed_ms, 3),
    }


def main(*, measure: bool = False, rounds: int = 5) -> None:
    """Print deterministic calibration JSON and optional local timing evidence."""
    payload: dict[str, object] = {"calibration": calibrate()}
    if measure:
        payload["measurement"] = measure_analysis(rounds=rounds)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", action="store_true", help="include local timing evidence")
    parser.add_argument("--rounds", type=int, default=5, help="timing rounds (default: 5)")
    arguments = parser.parse_args()
    main(measure=arguments.measure, rounds=arguments.rounds)
