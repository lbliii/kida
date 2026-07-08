"""Cross-surface contracts for ``kida check`` diagnostics."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from kida._check import _Collector
from kida.cli import main
from kida.diagnostics import Diagnostic, DiagnosticSeverity, SourcePosition, SourceSpan

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "diagnostics" / "v1" / "check.schema.json"


def _write_contract_fixture(root: Path) -> None:
    (root / "pages").mkdir()
    (root / "components.html").write_text(
        "{% def card(title: str, count: int) %}{{ title }}{% end %}",
        encoding="utf-8",
    )
    (root / "call.html").write_text(
        '{% from "components.html" import card %}'
        '{{ card(titl="Hi") }}'
        '{{ card("Hi", count="many") }}',
        encoding="utf-8",
    )
    (root / "typed.html").write_text(
        "{% template user: str %}{{ usre }}",
        encoding="utf-8",
    )
    (root / "a11y.html").write_text('<img src="avatar.png">', encoding="utf-8")
    (root / "pages" / "about.html").write_text(
        '{% include "pages/card.html" %}',
        encoding="utf-8",
    )
    (root / "pages" / "card.html").write_text("CARD", encoding="utf-8")


def _run_format(root: Path, output_format: str, capsys: pytest.CaptureFixture[str]):
    exit_code = main(
        [
            "check",
            str(root),
            "--validate-calls",
            "--typed",
            "--a11y",
            "--lint-fragile-paths",
            "--format",
            output_format,
        ]
    )
    return exit_code, capsys.readouterr()


def _type_matches(value: object, expected: str) -> bool:
    return {
        "array": isinstance(value, list),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
        "object": isinstance(value, dict),
        "string": isinstance(value, str),
    }[expected]


def _validate_schema(
    value: Any,
    node: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    path: str = "$",
) -> list[str]:
    if "$ref" in node:
        name = node["$ref"].removeprefix("#/$defs/")
        return _validate_schema(value, root_schema["$defs"][name], root_schema, path)
    if "oneOf" in node:
        matches = [
            errors
            for branch in node["oneOf"]
            if not (errors := _validate_schema(value, branch, root_schema, path))
        ]
        return [] if len(matches) == 1 else [f"{path}: expected exactly one matching branch"]

    errors: list[str] = []
    if "const" in node and value != node["const"]:
        errors.append(f"{path}: expected {node['const']!r}")
    if "enum" in node and value not in node["enum"]:
        errors.append(f"{path}: expected one of {node['enum']!r}")
    expected_type = node.get("type")
    if isinstance(expected_type, str) and not _type_matches(value, expected_type):
        return [f"{path}: expected {expected_type}, got {type(value).__name__}"]
    if isinstance(value, str):
        if "minLength" in node and len(value) < node["minLength"]:
            errors.append(f"{path}: string is too short")
        if "pattern" in node and re.search(node["pattern"], value) is None:
            errors.append(f"{path}: string does not match {node['pattern']}")
    if isinstance(value, int) and "minimum" in node and value < node["minimum"]:
        errors.append(f"{path}: value is below minimum")
    if isinstance(value, dict):
        required = set(node.get("required", []))
        errors.extend(f"{path}: missing {key}" for key in sorted(required - value.keys()))
        properties = node.get("properties", {})
        if node.get("additionalProperties") is False:
            errors.extend(f"{path}: unexpected {key}" for key in sorted(value.keys() - properties))
        for key, child in properties.items():
            if key in value:
                errors.extend(_validate_schema(value[key], child, root_schema, f"{path}.{key}"))
        additional = node.get("additionalProperties")
        if isinstance(additional, Mapping):
            for key in value.keys() - properties:
                errors.extend(
                    _validate_schema(value[key], additional, root_schema, f"{path}.{key}")
                )
    if isinstance(value, list) and isinstance(node.get("items"), Mapping):
        for index, item in enumerate(value):
            errors.extend(_validate_schema(item, node["items"], root_schema, f"{path}[{index}]"))
    return errors


def test_one_fixture_has_equivalent_text_json_and_sarif_facts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_contract_fixture(tmp_path)

    text_exit, text = _run_format(tmp_path, "text", capsys)
    json_exit, json_capture = _run_format(tmp_path, "json", capsys)
    sarif_exit, sarif_capture = _run_format(tmp_path, "sarif", capsys)

    assert text_exit == json_exit == sarif_exit == 1
    assert text.out == ""
    assert json_capture.err == sarif_capture.err == ""
    payload = json.loads(json_capture.out)
    sarif = json.loads(sarif_capture.out)
    diagnostics = payload["diagnostics"]
    results = sarif["runs"][0]["results"]
    assert payload["schema_version"] == 1
    assert payload["root"] == str(tmp_path)
    assert payload["summary"]["total"] == len(diagnostics) == len(results)
    assert payload["partial"] is False
    assert payload["exit_code"] == 1
    assert [(item["code"], item["path"], item["message"]) for item in diagnostics] == [
        (
            item["ruleId"],
            item["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
            item["message"]["text"],
        )
        for item in results
    ]
    assert {item["code"] for item in diagnostics} >= {
        "K-CMP-001",
        "K-CMP-002",
        "K-TYP-002",
        "K-PATH-001",
        "K-A11Y-001",
    }
    assert [item["code"] for item in diagnostics] == [
        "K-CMP-001",
        "K-CMP-002",
        "K-TYP-001",
        "K-TYP-002",
        "K-PATH-001",
        "K-A11Y-001",
    ]
    for item in diagnostics:
        assert item["message"] in text.err
    assert "kida check: 6 problem(s)" in text.err

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert _validate_schema(payload, schema, schema) == []


def test_json_reports_partial_collection_and_continues_other_templates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "bad.html").write_text("{% if broken %}", encoding="utf-8")
    (tmp_path / "good.html").write_text('<img src="x">', encoding="utf-8")

    exit_code = main(["check", str(tmp_path), "--a11y", "--format", "json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert captured.err == ""
    assert payload["partial"] is True
    assert payload["exit_code"] == 1
    assert {item["code"] for item in payload["diagnostics"]} >= {
        "K-PAR-001",
        "K-A11Y-001",
    }


@pytest.mark.parametrize("output_format", ["json", "sarif"])
def test_machine_formats_report_invalid_root_on_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    output_format: str,
) -> None:
    missing = tmp_path / "missing"

    exit_code = main(["check", str(missing), "--format", output_format])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert captured.err == ""
    if output_format == "json":
        assert payload["partial"] is True
        assert payload["diagnostics"][0]["code"] == "K-TPL-001"
    else:
        invocation = payload["runs"][0]["invocations"][0]
        assert invocation["executionSuccessful"] is False
        assert invocation["exitCode"] == 2


def test_sarif_coordinates_are_one_based(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "page.html").write_text('\n<img src="x">', encoding="utf-8")

    assert main(["check", str(tmp_path), "--a11y", "--format", "sarif"]) == 1
    payload = json.loads(capsys.readouterr().out)
    region = payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]

    assert region["startLine"] == 2
    assert region["startColumn"] == 1


def test_strict_safe_edit_has_json_sarif_and_text_parity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "page.html").write_text(
        "{% if ok %}\n{% end %}",
        encoding="utf-8",
    )

    text_exit = main(["check", str(tmp_path), "--strict"])
    text = capsys.readouterr()
    json_exit = main(["check", str(tmp_path), "--strict", "--format", "json"])
    json_capture = capsys.readouterr()
    sarif_exit = main(["check", str(tmp_path), "--strict", "--format", "sarif"])
    sarif_capture = capsys.readouterr()

    assert text_exit == json_exit == sarif_exit == 1
    assert text.out == ""
    assert "page.html:2: strict: unified {% end %} closes 'if' — prefer {% endif %}" in text.err
    payload = json.loads(json_capture.out)
    sarif = json.loads(sarif_capture.out)
    diagnostic = payload["diagnostics"][0]
    result = sarif["runs"][0]["results"][0]

    assert diagnostic["code"] == result["ruleId"] == "K-PAR-007"
    assert diagnostic["safe_edit"] == {
        "path": "page.html",
        "range": {
            "start": {"line": 2, "column": 3},
            "end": {"line": 2, "column": 6},
        },
        "replacement": "endif",
        "description": "Replace the unified closer with 'endif'.",
    }
    assert diagnostic["source_snippet"] is not None
    replacement = result["fixes"][0]["artifactChanges"][0]["replacements"][0]
    assert replacement == {
        "deletedRegion": {
            "startLine": 2,
            "startColumn": 4,
            "endLine": 2,
            "endColumn": 7,
        },
        "insertedContent": {"text": "endif"},
    }
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert _validate_schema(payload, schema, schema) == []


def test_deduplication_keeps_first_exact_diagnostic_event(tmp_path: Path) -> None:
    collector = _Collector(tmp_path)
    diagnostic = Diagnostic(
        code="K-TEST-001",
        category="test",
        severity=DiagnosticSeverity.WARNING,
        message="Duplicate",
        span=SourceSpan(path="page.html", start=SourcePosition(1, 0)),
    )

    assert collector.add(diagnostic, phase="load", text="first") is True
    assert collector.add(diagnostic, phase="type", text="second") is False
    result = collector.build(exit_code=1)

    assert result.diagnostics == (diagnostic,)
    assert [event.text for event in result.events] == ["first"]


def test_machine_diagnostics_sort_by_phase_before_source_order(tmp_path: Path) -> None:
    collector = _Collector(tmp_path)
    later_phase = Diagnostic(
        code="K-A11Y-001",
        category="accessibility",
        severity=DiagnosticSeverity.ERROR,
        message="Later phase",
        span=SourceSpan(path="a.html", start=SourcePosition(1, 0)),
    )
    earlier_phase = Diagnostic(
        code="K-PAR-001",
        category="parser",
        severity=DiagnosticSeverity.ERROR,
        message="Earlier phase",
        span=SourceSpan(path="z.html", start=SourcePosition(2, 0)),
    )

    collector.add(later_phase, phase="accessibility", text="later")
    collector.add(earlier_phase, phase="load", text="earlier")
    result = collector.build(exit_code=1)

    assert [event.text for event in result.events] == ["later", "earlier"]
    assert result.diagnostics == (earlier_phase, later_phase)
