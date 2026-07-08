"""Private adapters from existing producer records to canonical diagnostics."""

from __future__ import annotations

from kida._diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticSeverity,
    DiagnosticSnippet,
    RelatedLocation,
    SourcePosition,
    SourceSpan,
)
from kida.exceptions import ErrorCode, TemplateDiagnostic


def _category_for_code(code: str) -> str:
    """Return the public ErrorCode category or an explicit unknown marker."""
    try:
        return ErrorCode(code).category
    except ValueError:
        return "unknown"


def _frame_location(label: str, template: str, line: int) -> RelatedLocation:
    return RelatedLocation(
        label=label,
        span=SourceSpan(path=template, start=SourcePosition(line=line)),
    )


def convert_template_diagnostic(source: TemplateDiagnostic) -> Diagnostic:
    """Losslessly adapt the existing exception payload to the private model.

    ``TemplateDiagnostic`` predates the canonical model and is documented via
    ``UndefinedError.to_diagnostic()``.  This adapter leaves that payload and
    all of its renderers unchanged.
    """
    if source.code is None:
        raise ValueError("TemplateDiagnostic requires a stable code for conversion")

    start = None
    if source.location.line is not None:
        start = SourcePosition(
            line=source.location.line,
            column=source.location.column,
        )
    elif source.location.column is not None:
        raise ValueError("TemplateDiagnostic column requires a line")

    snippet = None
    if source.source_snippet is not None:
        snippet = DiagnosticSnippet(
            lines=source.source_snippet.lines,
            error_line=source.source_snippet.error_line,
            column=source.source_snippet.column,
        )

    related_locations = tuple(
        _frame_location(
            f"component {frame.name}" if frame.name else "component",
            frame.template,
            frame.line,
        )
        for frame in source.component_stack
    ) + tuple(
        _frame_location("template", frame.template, frame.line) for frame in source.template_stack
    )

    metadata = source.metadata
    if source.location.filename is not None and "filename" not in dict(metadata):
        metadata += (("filename", source.location.filename),)

    return Diagnostic(
        code=source.code,
        category=_category_for_code(source.code),
        severity=DiagnosticSeverity.ERROR,
        message=source.message,
        span=SourceSpan(path=source.location.template, start=start),
        title=source.title,
        kind=source.kind,
        suggestion=source.suggestion,
        related_locations=related_locations,
        confidence=DiagnosticConfidence.RUNTIME_ONLY,
        notes=source.hints,
        documentation_url=source.docs_url,
        source_snippet=snippet,
        metadata=metadata,
    )
