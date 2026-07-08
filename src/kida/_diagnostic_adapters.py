"""Private adapters from existing producer records to canonical diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida._diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticSeverity,
    DiagnosticSnippet,
    RelatedLocation,
    SourcePosition,
    SourceSpan,
)
from kida.exceptions import (
    ErrorCode,
    SourceSnippet,
    TemplateDiagnostic,
    TemplateError,
    TemplateRuntimeError,
    TemplateSyntaxError,
    TemplateWarning,
    UndefinedError,
    build_source_snippet,
)

if TYPE_CHECKING:
    from kida.analysis.a11y import A11yIssue
    from kida.analysis.context_contracts import ContextContractIssue
    from kida.analysis.escape_audit import EscapeAuditFinding
    from kida.analysis.fragile_paths import FragilePathIssue
    from kida.analysis.metadata import CallValidation, TypeMismatch
    from kida.analysis.privacy import PrivacyFinding
    from kida.analysis.type_checker import TypeIssue


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


def _source_span(
    path: str | None,
    line: int | None,
    column: int | None,
) -> SourceSpan:
    if line is None:
        if column is not None:
            raise ValueError("diagnostic column requires a line")
        return SourceSpan(path=path)
    return SourceSpan(path=path, start=SourcePosition(line=line, column=column))


def _convert_snippet(source: SourceSnippet | None) -> DiagnosticSnippet | None:
    if source is None:
        return None
    return DiagnosticSnippet(
        lines=source.lines,
        error_line=source.error_line,
        column=source.column,
    )


def _related_locations(
    component_stack: tuple[tuple[str, int, str], ...] | list[tuple[str, int, str]],
    template_stack: tuple[tuple[str, int], ...] | list[tuple[str, int]],
) -> tuple[RelatedLocation, ...]:
    return tuple(
        _frame_location(f"component {name}" if name else "component", template, line)
        for template, line, name in component_stack
    ) + tuple(_frame_location("template", template, line) for template, line in template_stack)


def convert_template_diagnostic(source: TemplateDiagnostic) -> Diagnostic:
    """Losslessly adapt the existing exception payload to the private model.

    ``TemplateDiagnostic`` predates the canonical model and is documented via
    ``UndefinedError.to_diagnostic()``.  This adapter leaves that payload and
    all of its renderers unchanged.
    """
    if source.code is None:
        raise ValueError("TemplateDiagnostic requires a stable code for conversion")

    related_locations = _related_locations(
        [(frame.template, frame.line, frame.name or "") for frame in source.component_stack],
        [(frame.template, frame.line) for frame in source.template_stack],
    )

    metadata = source.metadata
    if source.location.filename is not None and "filename" not in dict(metadata):
        metadata += (("filename", source.location.filename),)

    return Diagnostic(
        code=source.code,
        category=_category_for_code(source.code),
        severity=DiagnosticSeverity.ERROR,
        message=source.message,
        span=_source_span(
            source.location.template,
            source.location.line,
            source.location.column,
        ),
        title=source.title,
        kind=source.kind,
        suggestion=source.suggestion,
        related_locations=related_locations,
        confidence=DiagnosticConfidence.RUNTIME_ONLY,
        notes=source.hints,
        documentation_url=source.docs_url,
        source_snippet=_convert_snippet(source.source_snippet),
        metadata=metadata,
    )


def convert_template_error(source: TemplateError) -> Diagnostic:
    """Adapt a code-bearing Kida exception without changing its public class."""
    if isinstance(source, UndefinedError):
        return convert_template_diagnostic(source.to_diagnostic())
    if source.code is None:
        raise ValueError(f"{type(source).__name__} requires a stable code for conversion")

    code = source.code
    message = getattr(source, "message", None) or str(source)
    suggestion = getattr(source, "suggestion", None)
    path = None
    line = None
    column = None
    snippet = None
    related_locations: tuple[RelatedLocation, ...] = ()
    metadata: list[tuple[str, str]] = []
    confidence = DiagnosticConfidence.RUNTIME_ONLY

    if isinstance(source, TemplateSyntaxError):
        path = source.filename or source.name
        line = source.lineno
        column = source.col_offset
        confidence = DiagnosticConfidence.PROVEN
        if source.source is not None and line is not None:
            snippet = _convert_snippet(
                build_source_snippet(source.source, line, column=column),
            )
        if source.name is not None and source.name != path:
            metadata.append(("template_name", source.name))
    elif isinstance(source, TemplateRuntimeError):
        path = source.template_name
        line = source.lineno
        column = source.source_snippet.column if source.source_snippet is not None else None
        snippet = _convert_snippet(source.source_snippet)
        related_locations = _related_locations(source.component_stack, source.template_stack)
        if source.expression is not None:
            metadata.append(("expression", source.expression))
        if source.values:
            value_types = ", ".join(
                f"{name}:{type(value).__name__}" for name, value in source.values.items()
            )
            metadata.append(("value_types", value_types))
        field_name = getattr(source, "field_name", None)
        if field_name is not None:
            metadata.append(("field_name", field_name))

    return Diagnostic(
        code=code.value,
        category=code.category,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        span=_source_span(path, line, column),
        title=type(source).__name__,
        kind=code.category,
        suggestion=suggestion,
        related_locations=related_locations,
        confidence=confidence,
        documentation_url=code.docs_url,
        source_snippet=snippet,
        metadata=tuple(metadata),
    )


def convert_template_warning(source: TemplateWarning) -> Diagnostic:
    """Adapt a compiler warning while retaining its existing warning API."""
    return Diagnostic(
        code=source.code.value,
        category=source.code.category,
        severity=DiagnosticSeverity.WARNING,
        message=source.message,
        span=_source_span(source.template_name, source.lineno, None),
        title="Template warning",
        kind="compiler-warning",
        suggestion=source.suggestion,
        confidence=DiagnosticConfidence.PROVEN,
        documentation_url=source.code.docs_url,
    )


def convert_call_validation(
    source: CallValidation,
    *,
    template_name: str | None = None,
) -> Diagnostic:
    """Adapt one invalid component call result."""
    if source.is_valid:
        raise ValueError("valid CallValidation does not represent a diagnostic")

    parts: list[str] = []
    metadata: list[tuple[str, str]] = [("def_name", source.def_name)]
    for label, values in (
        ("unknown_params", source.unknown_params),
        ("missing_required", source.missing_required),
        ("duplicate_params", source.duplicate_params),
    ):
        if values:
            joined = ", ".join(values)
            parts.append(f"{label.replace('_', ' ')}: {joined}")
            metadata.append((label, joined))

    code = ErrorCode.COMPONENT_CALL_SIGNATURE
    return Diagnostic(
        code=code.value,
        category=code.category,
        severity=DiagnosticSeverity.ERROR,
        message=f"Call to '{source.def_name}' — {'; '.join(parts)}",
        span=_source_span(template_name, source.lineno, source.col_offset),
        title="Component call signature mismatch",
        kind="component-call",
        suggestion="Check the component definition and rename, add, or remove arguments.",
        confidence=DiagnosticConfidence.PROVEN,
        documentation_url=code.docs_url,
        metadata=tuple(metadata),
    )


def convert_type_mismatch(
    source: TypeMismatch,
    *,
    template_name: str | None = None,
) -> Diagnostic:
    """Adapt one statically proven component literal type mismatch."""
    code = ErrorCode.COMPONENT_TYPE_MISMATCH
    return Diagnostic(
        code=code.value,
        category=code.category,
        severity=DiagnosticSeverity.ERROR,
        message=(
            f"{source.def_name}() param '{source.param_name}' expects {source.expected}, "
            f"got {source.actual_type} ({source.actual_value!r})"
        ),
        span=_source_span(template_name, source.lineno, source.col_offset),
        title="Component literal type mismatch",
        kind="component-type",
        suggestion=f"Pass a {source.expected} literal for '{source.param_name}'.",
        confidence=DiagnosticConfidence.PROVEN,
        documentation_url=code.docs_url,
        metadata=(
            ("def_name", source.def_name),
            ("param_name", source.param_name),
            ("expected", source.expected),
            ("actual_type", source.actual_type),
        ),
    )


def convert_privacy_finding(source: PrivacyFinding) -> Diagnostic:
    """Adapt a conservative privacy-lint heuristic."""
    metadata = (("context_path", source.path),) if source.path is not None else ()
    return Diagnostic(
        code=source.code,
        category="privacy",
        severity=DiagnosticSeverity(source.severity),
        message=source.message,
        span=_source_span(source.template_name, source.lineno, source.col_offset),
        title="Privacy finding",
        kind=source.kind,
        suggestion=source.suggestion,
        confidence=DiagnosticConfidence.CONSERVATIVE,
        metadata=metadata,
    )


def convert_context_contract_issue(source: ContextContractIssue) -> Diagnostic:
    """Adapt a deterministic context-contract mismatch."""
    return Diagnostic(
        code=source.code,
        category="context",
        severity=DiagnosticSeverity(source.severity),
        message=source.message,
        span=_source_span(source.template_name, source.lineno, source.col_offset),
        title="Context contract finding",
        kind="context-contract",
        suggestion=source.suggestion,
        confidence=DiagnosticConfidence.PROVEN,
        metadata=(("context_path", source.path),),
    )


def convert_escape_audit_finding(source: EscapeAuditFinding) -> Diagnostic:
    """Adapt a deterministic escaping/trusted-markup observation."""
    metadata = (("expression", source.expression),) if source.expression is not None else ()
    return Diagnostic(
        code=source.code,
        category="escape",
        severity=DiagnosticSeverity(source.severity),
        message=source.message,
        span=_source_span(source.template_name, source.lineno, source.col_offset),
        title="Escape audit finding",
        kind=source.kind,
        suggestion=source.suggestion,
        confidence=DiagnosticConfidence.PROVEN,
        metadata=metadata,
    )


def convert_a11y_issue(
    source: A11yIssue,
    *,
    template_name: str | None = None,
) -> Diagnostic:
    """Adapt a static accessibility heuristic with its registered code."""
    return Diagnostic(
        code=source.code,
        category=ErrorCode(source.code).category,
        severity=DiagnosticSeverity(source.severity),
        message=source.message,
        span=_source_span(template_name, source.lineno, source.col_offset),
        title="Accessibility finding",
        kind=source.rule,
        confidence=DiagnosticConfidence.CONSERVATIVE,
    )


def convert_type_issue(
    source: TypeIssue,
    *,
    template_name: str | None = None,
) -> Diagnostic:
    """Adapt a template-declaration type finding with its registered code."""
    confidence = (
        DiagnosticConfidence.CONSERVATIVE
        if source.rule == "typo-suggestion"
        else DiagnosticConfidence.PROVEN
    )
    return Diagnostic(
        code=source.code,
        category=ErrorCode(source.code).category,
        severity=DiagnosticSeverity(source.severity),
        message=source.message,
        span=_source_span(template_name, source.lineno, source.col_offset),
        title="Template declaration type finding",
        kind=source.rule,
        confidence=confidence,
    )


def convert_fragile_path_issue(
    source: FragilePathIssue,
    *,
    template_name: str | None = None,
) -> Diagnostic:
    """Adapt a same-folder path suggestion with its registered code."""
    return Diagnostic(
        code=source.code,
        category=ErrorCode(source.code).category,
        severity=DiagnosticSeverity(source.severity),
        message=(
            f'{{% {source.statement} "{source.target}" %}} is in the same folder as the caller'
        ),
        span=_source_span(template_name, source.lineno, source.col_offset),
        title="Fragile template path",
        kind="fragile-template-path",
        suggestion=f'Use "{source.suggestion}" so folder moves stay zero-edit.',
        confidence=DiagnosticConfidence.CONSERVATIVE,
        metadata=(
            ("statement", source.statement),
            ("target", source.target),
            ("replacement", source.suggestion),
        ),
    )
