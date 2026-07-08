"""Public contract tests for :mod:`kida.diagnostics`."""

from __future__ import annotations

import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints

import pytest

import kida
import kida.diagnostics as diagnostics
from kida import DictLoader, Environment, TemplateSyntaxError
from kida.cli import main
from kida.diagnostics import (
    DiagnosticConfidence,
    DiagnosticOptions,
    DiagnosticSeverity,
    diagnose_directory,
    diagnose_source,
    diagnostic_from_exception,
)

EXPECTED_EXPORTS = [
    "Diagnostic",
    "DiagnosticConfidence",
    "DiagnosticConverter",
    "DiagnosticOptions",
    "DiagnosticReport",
    "DiagnosticSeverity",
    "DiagnosticSnippet",
    "RelatedLocation",
    "SafeEdit",
    "SourcePosition",
    "SourceSpan",
    "diagnose_directory",
    "diagnose_source",
    "diagnostic_from_exception",
]


def test_public_module_exports_and_signatures_are_stable() -> None:
    assert diagnostics.__all__ == EXPECTED_EXPORTS
    assert diagnostics.Diagnostic.__module__ == "kida.diagnostics"
    assert "Diagnostic" not in kida.__all__
    assert get_type_hints(diagnose_source)["return"] is diagnostics.DiagnosticReport
    assert get_type_hints(diagnose_directory)["return"] is diagnostics.DiagnosticReport
    assert str(inspect.signature(diagnose_directory)) == (
        "(root: 'str | PathLike[str]', *, "
        "options: 'DiagnosticOptions' = DiagnosticOptions(strict=False, "
        "validate_calls=False, a11y=False, typed=False, "
        "lint_fragile_paths=False)) -> 'DiagnosticReport'"
    )
    assert str(inspect.signature(diagnose_source)) == (
        "(source: 'str', *, name: 'str' = '<string>', "
        "environment: 'Environment | None' = None, "
        "options: 'DiagnosticOptions' = DiagnosticOptions(strict=False, "
        "validate_calls=False, a11y=False, typed=False, "
        "lint_fragile_paths=False)) -> 'DiagnosticReport'"
    )


def test_public_diagnostic_record_shapes_are_stable() -> None:
    assert [field.name for field in fields(diagnostics.SourcePosition)] == ["line", "column"]
    assert [field.name for field in fields(diagnostics.SourceSpan)] == ["path", "start", "end"]
    assert [field.name for field in fields(diagnostics.RelatedLocation)] == ["label", "span"]
    assert [field.name for field in fields(diagnostics.SafeEdit)] == [
        "span",
        "replacement",
        "description",
    ]
    assert [field.name for field in fields(diagnostics.DiagnosticSnippet)] == [
        "lines",
        "error_line",
        "column",
    ]
    assert [field.name for field in fields(diagnostics.Diagnostic)] == [
        "code",
        "category",
        "severity",
        "message",
        "span",
        "title",
        "kind",
        "suggestion",
        "safe_edit",
        "related_locations",
        "confidence",
        "notes",
        "documentation_url",
        "source_snippet",
        "metadata",
    ]
    assert [field.name for field in fields(DiagnosticOptions)] == [
        "strict",
        "validate_calls",
        "a11y",
        "typed",
        "lint_fragile_paths",
    ]
    assert [field.name for field in fields(diagnostics.DiagnosticReport)] == [
        "diagnostics",
        "partial",
    ]
    assert [item.value for item in DiagnosticSeverity] == ["error", "warning", "info"]
    assert [item.value for item in DiagnosticConfidence] == [
        "proven",
        "conservative",
        "runtime-only",
        "unknown",
    ]


class _FailIfLoaded:
    def get_source(self, name: str) -> tuple[str, None]:
        raise AssertionError(f"unsaved source unexpectedly loaded {name}")

    def list_templates(self) -> list[str]:
        return []


def test_unsaved_source_uses_supplied_text_without_loader_or_cache() -> None:
    env = Environment(loader=_FailIfLoaded())
    report = diagnose_source(
        '{% template user: str %}{{ usre }}<img src="x">',
        name="page.html",
        environment=env,
        options=DiagnosticOptions(typed=True, a11y=True),
    )

    assert report.partial is False
    assert [item.code for item in report.diagnostics] == [
        "K-TYP-001",
        "K-TYP-002",
        "K-A11Y-001",
    ]
    assert all(item.span.path == "page.html" for item in report.diagnostics)
    assert report.diagnostics[0].confidence is DiagnosticConfidence.PROVEN
    assert report.diagnostics[-1].confidence is DiagnosticConfidence.CONSERVATIVE


def test_source_reports_malformed_input_as_partial_with_location() -> None:
    report = diagnose_source("{% if broken %}", name="broken.html")

    assert report.partial is True
    assert len(report.diagnostics) == 1
    diagnostic = report.diagnostics[0]
    assert diagnostic.code == "K-PAR-001"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.span.path == "broken.html"
    assert diagnostic.span.start is not None
    assert diagnostic.span.start.line == 1


def test_source_strict_option_controls_unified_end_finding() -> None:
    source = "{% if ok %}yes{% end %}"

    assert diagnose_source(source, name="page.html").diagnostics == ()
    strict = diagnose_source(
        source,
        name="page.html",
        options=DiagnosticOptions(strict=True),
    )

    assert [item.code for item in strict.diagnostics] == ["K-PAR-007"]
    assert strict.diagnostics[0].suggestion == "Prefer {% endif %}."


def test_unsaved_source_resolves_cross_template_component_metadata() -> None:
    env = Environment(
        loader=DictLoader(
            {"components.html": ("{% def card(title: str, count: int) %}{{ title }}{% end %}")}
        )
    )
    source = (
        '{% from "components.html" import card %}'
        '{{ card(titl="Hi") }}'
        '{{ card("Hi", count="many") }}'
    )

    report = diagnose_source(
        source,
        name="page.html",
        environment=env,
        options=DiagnosticOptions(validate_calls=True),
    )

    assert [(item.code, item.span.path) for item in report.diagnostics] == [
        ("K-CMP-001", "page.html"),
        ("K-CMP-002", "page.html"),
    ]
    assert all(item.confidence is DiagnosticConfidence.PROVEN for item in report.diagnostics)


def test_directory_report_matches_cli_json_facts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "page.html").write_text(
        '{% template user: str %}{{ usre }}<img src="x">',
        encoding="utf-8",
    )
    options = DiagnosticOptions(typed=True, a11y=True)

    report = diagnose_directory(tmp_path, options=options)
    exit_code = main(["check", str(tmp_path), "--typed", "--a11y", "--format", "json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert captured.err == ""
    assert report.partial == payload["partial"]
    assert [(item.code, item.span.path, item.message) for item in report.diagnostics] == [
        (item["code"], item["path"], item["message"]) for item in payload["diagnostics"]
    ]


def test_missing_directory_is_a_partial_report_not_an_exception(tmp_path: Path) -> None:
    report = diagnose_directory(tmp_path / "missing")

    assert report.partial is True
    assert [item.code for item in report.diagnostics] == ["K-TPL-001"]


def test_exception_conversion_preserves_kida_identity_and_rejects_foreign_errors() -> None:
    error = TemplateSyntaxError(
        "Unexpected token",
        lineno=2,
        name="original.html",
        source="first\n{% nope %}",
        col_offset=3,
    )

    diagnostic = diagnostic_from_exception(error, path="overlay.html")

    assert diagnostic.code == "K-TPL-002"
    assert diagnostic.span.path == "overlay.html"
    assert diagnostic.span.start == diagnostics.SourcePosition(2, 3)
    assert diagnostic.source_snippet is not None
    with pytest.raises(TypeError, match="unsupported diagnostic exception: ValueError"):
        diagnostic_from_exception(ValueError("application failure"))


def test_concurrent_source_diagnosis_has_no_cross_request_state() -> None:
    env = Environment(
        loader=DictLoader({"components.html": "{% def card(title: str) %}{{ title }}{% end %}"})
    )
    source = '{% from "components.html" import card %}{{ card(titl="Hi") }}'

    def run(index: int) -> tuple[str, str, int]:
        name = f"page-{index}.html"
        report = diagnose_source(
            source,
            name=name,
            environment=env,
            options=DiagnosticOptions(validate_calls=True),
        )
        item = report.diagnostics[0]
        return item.code, item.span.path or "", len(report.diagnostics)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(run, range(32)))

    assert results == [("K-CMP-001", f"page-{index}.html", 1) for index in range(32)]
