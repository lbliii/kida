"""Focused proof for the public canonical diagnostic model."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from kida._diagnostic_adapters import convert_template_diagnostic
from kida.diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticConverter,
    DiagnosticSeverity,
    RelatedLocation,
    SafeEdit,
    SourcePosition,
    SourceSpan,
)
from kida.exceptions import (
    DiagnosticLocation,
    SourceSnippet,
    TemplateDiagnostic,
    UndefinedError,
)


def _convert[SourceT](source: SourceT, converter: DiagnosticConverter[SourceT]) -> Diagnostic:
    return converter(source)


def test_diagnostic_facts_are_deeply_immutable() -> None:
    diagnostic = Diagnostic(
        code="K-TEST-001",
        category="test",
        severity=DiagnosticSeverity.WARNING,
        message="Example finding",
        span=SourceSpan(path="page.html", start=SourcePosition(2, 4)),
        related_locations=(
            RelatedLocation(
                label="definition",
                span=SourceSpan(path="components.html", start=SourcePosition(8)),
            ),
        ),
        notes=("Check the declaration.",),
        metadata=(("rule", "example"),),
    )

    with pytest.raises(FrozenInstanceError):
        del diagnostic.message
    with pytest.raises(FrozenInstanceError):
        del diagnostic.span.path

    assert isinstance(diagnostic.related_locations, tuple)
    assert isinstance(diagnostic.metadata, tuple)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: SourcePosition(0), "line must be 1-based"),
        (lambda: SourcePosition(1, -1), "column must be 0-based"),
        (
            lambda: SourceSpan(end=SourcePosition(1, 1)),
            "end position requires a start position",
        ),
        (
            lambda: SourceSpan(start=SourcePosition(3), end=SourcePosition(2)),
            "end position must not precede start position",
        ),
        (
            lambda: SourceSpan(start=SourcePosition(2, 5), end=SourcePosition(2, 4)),
            "end position must not precede start position",
        ),
    ],
)
def test_source_coordinates_reject_ambiguous_or_invalid_ranges(factory, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_safe_edit_requires_an_exact_half_open_range() -> None:
    exact = SourceSpan(
        path="page.html",
        start=SourcePosition(2, 3),
        end=SourcePosition(2, 7),
    )

    edit = SafeEdit(span=exact, replacement="user", description="Correct the variable name")

    assert edit.span.is_exact
    assert edit.replacement == "user"
    with pytest.raises(ValueError, match="safe edit requires"):
        SafeEdit(
            span=SourceSpan(path="page.html", start=SourcePosition(2, 3)),
            replacement="user",
        )


def test_diagnostic_rejects_missing_identity_and_duplicate_metadata() -> None:
    with pytest.raises(ValueError, match="diagnostic code"):
        Diagnostic(
            code=" ",
            category="type",
            severity=DiagnosticSeverity.ERROR,
            message="Missing code",
        )
    with pytest.raises(ValueError, match="duplicate diagnostic metadata key"):
        Diagnostic(
            code="K-TEST-001",
            category="test",
            severity=DiagnosticSeverity.INFO,
            message="Duplicate metadata",
            metadata=(("rule", "one"), ("rule", "two")),
        )


def test_existing_undefined_payload_converts_without_losing_facts() -> None:
    snippet = SourceSnippet(
        lines=((4, "{% call card() %}"), (5, "{{ usernme }}")),
        error_line=5,
        column=3,
    )
    source = UndefinedError(
        "usernme",
        template="page.html",
        lineno=5,
        available_names=frozenset({"username"}),
        source_snippet=snippet,
        component_stack=[("page.html", 4, "card")],
        template_stack=[("layout.html", 2)],
    ).to_diagnostic()

    diagnostic = _convert(source, convert_template_diagnostic)

    assert diagnostic.code == "K-RUN-001"
    assert diagnostic.category == "runtime"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.confidence is DiagnosticConfidence.RUNTIME_ONLY
    assert diagnostic.message == source.message
    assert diagnostic.span == SourceSpan(
        path="page.html",
        start=SourcePosition(5, 3),
    )
    assert diagnostic.title == "Undefined variable"
    assert diagnostic.kind == "variable"
    assert diagnostic.suggestion == "username"
    assert diagnostic.notes == source.hints
    assert diagnostic.documentation_url == source.docs_url
    assert diagnostic.metadata == source.metadata
    assert diagnostic.source_snippet is not None
    assert diagnostic.source_snippet.lines == snippet.lines
    assert diagnostic.source_snippet.error_line == 5
    assert diagnostic.source_snippet.column == 3
    assert [
        (item.label, item.span.path, item.span.start) for item in diagnostic.related_locations
    ] == [
        ("component card", "page.html", SourcePosition(4)),
        ("template", "layout.html", SourcePosition(2)),
    ]

    # The documented payload remains the same object shape and renderer input.
    assert source.format_markdown().startswith("### K-RUN-001: Undefined variable")


def test_template_diagnostic_conversion_requires_code_and_consistent_location() -> None:
    missing_code = TemplateDiagnostic(
        code=None,
        title="Example",
        message="Example failure",
        kind="example",
        location=DiagnosticLocation(template="page.html", line=1),
    )
    bad_location = TemplateDiagnostic(
        code="K-RUN-001",
        title="Example",
        message="Example failure",
        kind="example",
        location=DiagnosticLocation(template="page.html", column=2),
    )

    with pytest.raises(ValueError, match="stable code"):
        convert_template_diagnostic(missing_code)
    with pytest.raises(ValueError, match="column requires a line"):
        convert_template_diagnostic(bad_location)


def test_unknown_code_conversion_keeps_code_and_marks_category_unknown() -> None:
    source = TemplateDiagnostic(
        code="K-EXT-900",
        title="Extension finding",
        message="Extension reported a finding",
        kind="extension",
        location=DiagnosticLocation(
            template="page.html",
            line=3,
            filename="/templates/page.html",
        ),
        metadata=(("owner", "extension"),),
    )

    diagnostic = convert_template_diagnostic(source)

    assert diagnostic.code == "K-EXT-900"
    assert diagnostic.category == "unknown"
    assert diagnostic.metadata == (
        ("owner", "extension"),
        ("filename", "/templates/page.html"),
    )
