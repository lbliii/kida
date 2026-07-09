"""Private text, JSON, and SARIF renderers for ``kida check`` results."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from kida import __version__
from kida.diagnostics import Diagnostic, DiagnosticSeverity, SourcePosition, SourceSpan

if TYPE_CHECKING:
    from kida._check import CheckResult


def render_check_text(result: CheckResult) -> str:
    """Render compatibility text in the collector's deterministic event order."""
    if not result.events:
        return ""
    return "".join(f"{event.text}\n" for event in result.events)


def _position(position: SourcePosition) -> dict[str, int | None]:
    return {"line": position.line, "column": position.column}


def _range(span: SourceSpan) -> dict[str, object] | None:
    if span.start is None:
        return None
    return {
        "start": _position(span.start),
        "end": _position(span.end) if span.end is not None else None,
    }


def _span(span: SourceSpan) -> dict[str, object]:
    return {"path": span.path, "range": _range(span)}


def diagnostic_to_dict(diagnostic: Diagnostic) -> dict[str, object]:
    """Return the versioned JSON fact shape for one diagnostic."""
    safe_edit = None
    if diagnostic.safe_edit is not None:
        safe_edit = {
            **_span(diagnostic.safe_edit.span),
            "replacement": diagnostic.safe_edit.replacement,
            "description": diagnostic.safe_edit.description,
        }

    snippet = None
    if diagnostic.source_snippet is not None:
        snippet = {
            "lines": [
                {"line": line, "text": text} for line, text in diagnostic.source_snippet.lines
            ],
            "error_line": diagnostic.source_snippet.error_line,
            "column": diagnostic.source_snippet.column,
        }

    return {
        "code": diagnostic.code,
        "category": diagnostic.category,
        "severity": diagnostic.severity.value,
        "message": diagnostic.message,
        "path": diagnostic.span.path,
        "range": _range(diagnostic.span),
        "title": diagnostic.title,
        "kind": diagnostic.kind,
        "suggestion": diagnostic.suggestion,
        "safe_edit": safe_edit,
        "related_locations": [
            {"label": related.label, **_span(related.span)}
            for related in diagnostic.related_locations
        ],
        "confidence": diagnostic.confidence.value,
        "notes": list(diagnostic.notes),
        "documentation_url": diagnostic.documentation_url,
        "source_snippet": snippet,
        "metadata": dict(diagnostic.metadata),
    }


def _severity_counts(diagnostics: tuple[Diagnostic, ...]) -> dict[str, int]:
    errors = sum(item.severity is DiagnosticSeverity.ERROR for item in diagnostics)
    warnings = sum(item.severity is DiagnosticSeverity.WARNING for item in diagnostics)
    info = sum(item.severity is DiagnosticSeverity.INFO for item in diagnostics)
    return {
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "total": len(diagnostics),
    }


def check_json_payload(result: CheckResult) -> dict[str, object]:
    """Return the diagnostics JSON v1 envelope."""
    diagnostics = result.diagnostics
    return {
        "schema_version": 1,
        "root": result.root,
        "diagnostics": [diagnostic_to_dict(item) for item in diagnostics],
        "summary": _severity_counts(diagnostics),
        "partial": result.partial,
        "exit_code": result.exit_code,
    }


def render_check_json(result: CheckResult) -> str:
    """Render the diagnostics JSON v1 envelope."""
    return json.dumps(check_json_payload(result), indent=2, sort_keys=True) + "\n"


def _sarif_level(severity: DiagnosticSeverity) -> str:
    return {
        DiagnosticSeverity.ERROR: "error",
        DiagnosticSeverity.WARNING: "warning",
        DiagnosticSeverity.INFO: "note",
    }[severity]


def _sarif_region(
    span: SourceSpan, diagnostic: Diagnostic | None = None
) -> dict[str, object] | None:
    if span.start is None:
        return None
    region: dict[str, object] = {"startLine": span.start.line}
    if span.start.column is not None:
        region["startColumn"] = span.start.column + 1
    if span.end is not None:
        region["endLine"] = span.end.line
        if span.end.column is not None:
            region["endColumn"] = span.end.column + 1
    if diagnostic is not None and diagnostic.source_snippet is not None:
        for line, text in diagnostic.source_snippet.lines:
            if line == diagnostic.source_snippet.error_line:
                region["snippet"] = {"text": text}
                break
    return region


def _sarif_physical_location(
    span: SourceSpan,
    diagnostic: Diagnostic | None = None,
) -> dict[str, object] | None:
    if span.path is None:
        return None
    physical: dict[str, object] = {"artifactLocation": {"uri": span.path}}
    region = _sarif_region(span, diagnostic)
    if region is not None:
        physical["region"] = region
    return {"physicalLocation": physical}


def _sarif_result(diagnostic: Diagnostic) -> dict[str, object]:
    result: dict[str, object] = {
        "ruleId": diagnostic.code,
        "level": _sarif_level(diagnostic.severity),
        "message": {"text": diagnostic.message},
        "properties": {
            "category": diagnostic.category,
            "confidence": diagnostic.confidence.value,
            "kind": diagnostic.kind,
            "suggestion": diagnostic.suggestion,
            "notes": list(diagnostic.notes),
            "metadata": dict(diagnostic.metadata),
        },
    }
    primary = _sarif_physical_location(diagnostic.span, diagnostic)
    if primary is not None:
        result["locations"] = [primary]
    if diagnostic.related_locations:
        result["relatedLocations"] = [
            {"id": index, "message": {"text": related.label}, **location}
            for index, related in enumerate(diagnostic.related_locations, start=1)
            if (location := _sarif_physical_location(related.span)) is not None
        ]
    if diagnostic.safe_edit is not None and diagnostic.safe_edit.span.path is not None:
        region = _sarif_region(diagnostic.safe_edit.span)
        if region is not None:
            result["fixes"] = [
                {
                    "description": {
                        "text": diagnostic.safe_edit.description or "Apply suggested edit"
                    },
                    "artifactChanges": [
                        {
                            "artifactLocation": {"uri": diagnostic.safe_edit.span.path},
                            "replacements": [
                                {
                                    "deletedRegion": region,
                                    "insertedContent": {
                                        "text": diagnostic.safe_edit.replacement,
                                    },
                                }
                            ],
                        }
                    ],
                }
            ]
    return result


def check_sarif_payload(result: CheckResult) -> dict[str, object]:
    """Return a SARIF 2.1.0 log for the canonical diagnostic collection."""
    diagnostics = result.diagnostics
    first_by_code: dict[str, Diagnostic] = {}
    for diagnostic in diagnostics:
        first_by_code.setdefault(diagnostic.code, diagnostic)
    rules: list[dict[str, Any]] = []
    for code in sorted(first_by_code):
        diagnostic = first_by_code[code]
        rule: dict[str, Any] = {
            "id": code,
            "name": diagnostic.kind or code,
            "shortDescription": {"text": diagnostic.title or code},
            "defaultConfiguration": {"level": _sarif_level(diagnostic.severity)},
            "properties": {
                "category": diagnostic.category,
                "confidence": diagnostic.confidence.value,
            },
        }
        if diagnostic.documentation_url is not None:
            rule["helpUri"] = diagnostic.documentation_url
        rules.append(rule)

    run = {
        "tool": {
            "driver": {
                "name": "kida",
                "semanticVersion": __version__,
                "informationUri": "https://lbliii.github.io/kida/",
                "rules": rules,
            }
        },
        "results": [_sarif_result(item) for item in diagnostics],
        "invocations": [
            {
                "executionSuccessful": result.exit_code != 2,
                "exitCode": result.exit_code,
                "workingDirectory": {"uri": result.root},
                "properties": {"partial": result.partial},
            }
        ],
    }
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [run],
    }


def render_check_sarif(result: CheckResult) -> str:
    """Render the canonical collection as SARIF 2.1.0 JSON."""
    return json.dumps(check_sarif_payload(result), indent=2, sort_keys=True) + "\n"
