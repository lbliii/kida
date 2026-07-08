"""Fact-preservation tests for private diagnostic producer adapters."""

from __future__ import annotations

import pytest

from kida._diagnostic_adapters import (
    convert_call_validation,
    convert_context_contract_issue,
    convert_escape_audit_finding,
    convert_privacy_finding,
    convert_template_error,
    convert_template_warning,
    convert_type_mismatch,
)
from kida._diagnostics import (
    DiagnosticConfidence,
    DiagnosticSeverity,
    SourcePosition,
    SourceSpan,
)
from kida._types import Token, TokenType
from kida.analysis.context_contracts import ContextContractIssue
from kida.analysis.escape_audit import EscapeAuditFinding
from kida.analysis.metadata import CallValidation, TypeMismatch
from kida.analysis.privacy import PrivacyFinding
from kida.exceptions import (
    ErrorCode,
    SourceSnippet,
    TemplateError,
    TemplateRuntimeError,
    TemplateWarning,
)
from kida.parser.errors import ParseError
from kida.sandbox import SecurityError


def test_parse_error_conversion_preserves_code_location_source_and_suggestion() -> None:
    source = ParseError(
        "Expected an expression",
        Token(TokenType.NAME, "broken", lineno=2, col_offset=4),
        source="<main>\n{{ broken }}",
        filename="page.html",
        suggestion="Add a value after the operator.",
        code=ErrorCode.INVALID_EXPRESSION,
    )

    diagnostic = convert_template_error(source)

    assert diagnostic.code == "K-PAR-003"
    assert diagnostic.category == "parser"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.confidence is DiagnosticConfidence.PROVEN
    assert diagnostic.message == "Expected an expression"
    assert diagnostic.span == SourceSpan(
        path="page.html",
        start=SourcePosition(2, 4),
    )
    assert diagnostic.suggestion == "Add a value after the operator."
    assert diagnostic.documentation_url == ErrorCode.INVALID_EXPRESSION.docs_url
    assert diagnostic.source_snippet is not None
    assert diagnostic.source_snippet.lines == ((1, "<main>"), (2, "{{ broken }}"))
    assert diagnostic.source_snippet.error_line == 2
    assert diagnostic.source_snippet.column == 4


def test_runtime_error_conversion_preserves_safe_context_without_raw_values() -> None:
    source = TemplateRuntimeError(
        "Cannot render user",
        expression="user.name",
        values={"user": {"name": "Ada"}},
        template_name="page.html",
        lineno=5,
        suggestion="Pass a user with a name.",
        source_snippet=SourceSnippet(
            lines=((5, "{{ user.name }}"),),
            error_line=5,
            column=3,
        ),
        component_stack=[("page.html", 4, "card")],
        template_stack=[("layout.html", 2)],
        code=ErrorCode.TYPE_ERROR,
    )

    diagnostic = convert_template_error(source)

    assert diagnostic.code == "K-RUN-012"
    assert diagnostic.category == "runtime"
    assert diagnostic.confidence is DiagnosticConfidence.RUNTIME_ONLY
    assert diagnostic.span == SourceSpan(path="page.html", start=SourcePosition(5, 3))
    assert diagnostic.suggestion == "Pass a user with a name."
    assert diagnostic.metadata == (
        ("expression", "user.name"),
        ("value_types", "user:dict"),
    )
    assert "Ada" not in repr(diagnostic)
    assert diagnostic.source_snippet is not None
    assert diagnostic.source_snippet.column == 3
    assert [item.label for item in diagnostic.related_locations] == [
        "component card",
        "template",
    ]


def test_security_error_conversion_retains_code_and_action_without_location() -> None:
    source = SecurityError(
        "Attribute access is blocked",
        code=ErrorCode.BLOCKED_ATTRIBUTE,
        suggestion="Remove the blocked attribute access.",
    )

    diagnostic = convert_template_error(source)

    assert diagnostic.code == "K-SEC-001"
    assert diagnostic.category == "security"
    assert diagnostic.span == SourceSpan()
    assert diagnostic.suggestion == "Remove the blocked attribute access."
    assert diagnostic.confidence is DiagnosticConfidence.RUNTIME_ONLY


def test_template_error_conversion_rejects_missing_stable_code() -> None:
    with pytest.raises(ValueError, match="requires a stable code"):
        convert_template_error(TemplateError("Unclassified failure"))


def test_template_warning_conversion_is_proven_and_non_disruptive() -> None:
    source = TemplateWarning(
        code=ErrorCode.JINJA2_SET_SCOPING,
        message="set creates a block-scoped shadow",
        template_name="page.html",
        lineno=7,
        suggestion="Use export for an outer-scope write.",
    )

    diagnostic = convert_template_warning(source)

    assert diagnostic.code == "K-WARN-002"
    assert diagnostic.category == "warning"
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.confidence is DiagnosticConfidence.PROVEN
    assert diagnostic.span == SourceSpan(path="page.html", start=SourcePosition(7))
    assert diagnostic.suggestion == "Use export for an outer-scope write."
    assert source.format_message().startswith("[K-WARN-002]")


def test_component_call_conversion_preserves_signature_facts_and_location() -> None:
    source = CallValidation(
        def_name="card",
        lineno=9,
        col_offset=6,
        unknown_params=("titl",),
        missing_required=("title", "count"),
    )

    diagnostic = convert_call_validation(source, template_name="page.html")

    assert diagnostic.code == "K-CMP-001"
    assert diagnostic.category == "component"
    assert diagnostic.confidence is DiagnosticConfidence.PROVEN
    assert diagnostic.span == SourceSpan(
        path="page.html",
        start=SourcePosition(9, 6),
    )
    assert diagnostic.message == (
        "Call to 'card' — unknown params: titl; missing required: title, count"
    )
    assert diagnostic.metadata == (
        ("def_name", "card"),
        ("unknown_params", "titl"),
        ("missing_required", "title, count"),
    )


def test_valid_component_call_does_not_become_a_diagnostic() -> None:
    source = CallValidation(def_name="card", lineno=1, col_offset=0)

    with pytest.raises(ValueError, match="does not represent a diagnostic"):
        convert_call_validation(source)


def test_component_type_conversion_preserves_expected_and_actual_types() -> None:
    source = TypeMismatch(
        def_name="card",
        param_name="count",
        expected="int",
        actual_type="str",
        actual_value="many",
        lineno=11,
        col_offset=8,
    )

    diagnostic = convert_type_mismatch(source, template_name="page.html")

    assert diagnostic.code == "K-CMP-002"
    assert diagnostic.message == "card() param 'count' expects int, got str ('many')"
    assert diagnostic.span == SourceSpan(
        path="page.html",
        start=SourcePosition(11, 8),
    )
    assert diagnostic.metadata == (
        ("def_name", "card"),
        ("param_name", "count"),
        ("expected", "int"),
        ("actual_type", "str"),
    )


def test_privacy_conversion_marks_heuristic_conservative_and_avoids_fabricated_location() -> None:
    source = PrivacyFinding(
        code="K-PRI-001",
        severity="warning",
        kind="sensitive-context-path",
        message="Template reads a sensitive-looking context path.",
        path="request.session.token",
        suggestion="Confirm this value is intended for output.",
    )

    diagnostic = convert_privacy_finding(source)

    assert diagnostic.category == "privacy"
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.confidence is DiagnosticConfidence.CONSERVATIVE
    assert diagnostic.span == SourceSpan()
    assert diagnostic.metadata == (("context_path", "request.session.token"),)


def test_context_conversion_marks_contract_comparison_proven() -> None:
    source = ContextContractIssue(
        code="K-CTX-001",
        severity="error",
        path="page.title",
        message="The contract does not provide page.title.",
        template_name="page.html",
        suggestion="Add page.title to the route contract.",
    )

    diagnostic = convert_context_contract_issue(source)

    assert diagnostic.category == "context"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.confidence is DiagnosticConfidence.PROVEN
    assert diagnostic.span == SourceSpan(path="page.html")
    assert diagnostic.metadata == (("context_path", "page.title"),)


def test_escape_conversion_preserves_expression_and_source_position() -> None:
    source = EscapeAuditFinding(
        code="K-ESC-003",
        severity="warning",
        kind="unescaped-output",
        message="Output expression is rendered without autoescape.",
        template_name="page.html",
        lineno=4,
        col_offset=2,
        expression="user.bio",
        suggestion="Escape this value or mark the trust boundary explicitly.",
    )

    diagnostic = convert_escape_audit_finding(source)

    assert diagnostic.category == "escape"
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.confidence is DiagnosticConfidence.PROVEN
    assert diagnostic.span == SourceSpan(
        path="page.html",
        start=SourcePosition(4, 2),
    )
    assert diagnostic.metadata == (("expression", "user.bio"),)
