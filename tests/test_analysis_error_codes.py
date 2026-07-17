"""Public code-registry contracts for static analysis findings."""

from __future__ import annotations

from kida import ErrorCode
from kida.analysis.a11y import A11yIssue
from kida.analysis.context_contracts import ContextContractIssue
from kida.analysis.escape_audit import EscapeAuditFinding
from kida.analysis.fragile_paths import FragilePathIssue
from kida.analysis.privacy import PrivacyFinding
from kida.analysis.type_checker import TypeIssue


def test_previously_code_less_findings_expose_stable_codes_without_new_fields() -> None:
    a11y = {
        rule: A11yIssue(1, 0, rule, "finding").code
        for rule in ("img-alt", "heading-order", "html-lang", "input-label")
    }
    typed = {
        rule: TypeIssue(1, 0, rule, "finding").code
        for rule in ("undeclared-var", "unused-declared", "typo-suggestion")
    }
    fragile = FragilePathIssue(1, 0, "include", "pages/card.html", "./card.html")

    assert a11y == {
        "img-alt": "K-A11Y-001",
        "heading-order": "K-A11Y-002",
        "html-lang": "K-A11Y-003",
        "input-label": "K-A11Y-004",
    }
    assert typed == {
        "undeclared-var": "K-TYP-001",
        "unused-declared": "K-TYP-002",
        "typo-suggestion": "K-TYP-003",
    }
    assert fragile.code == "K-PATH-001"
    assert list(A11yIssue.__dataclass_fields__) == [
        "lineno",
        "col_offset",
        "rule",
        "message",
        "severity",
    ]
    assert list(TypeIssue.__dataclass_fields__) == [
        "lineno",
        "col_offset",
        "rule",
        "message",
        "severity",
    ]
    assert list(FragilePathIssue.__dataclass_fields__) == [
        "lineno",
        "col_offset",
        "statement",
        "target",
        "suggestion",
        "severity",
    ]


def test_existing_analysis_code_strings_are_registered_without_renumbering() -> None:
    privacy = PrivacyFinding(
        code="K-PRI-001",
        severity="warning",
        kind="sensitive-context-path",
        message="finding",
    )
    context = ContextContractIssue(
        code="K-CTX-001",
        severity="error",
        path="page.title",
        message="finding",
    )
    escape = EscapeAuditFinding(
        code="K-ESC-001",
        severity="info",
        kind="escaped-output",
        message="finding",
    )

    assert ErrorCode(privacy.code) is ErrorCode.PRIVACY_SENSITIVE_CONTEXT
    assert ErrorCode(context.code) is ErrorCode.CONTEXT_MISSING
    assert ErrorCode(escape.code) is ErrorCode.ESCAPE_ESCAPED_OUTPUT
    assert privacy.code == "K-PRI-001"
    assert context.code == "K-CTX-001"
    assert escape.code == "K-ESC-001"


def test_analysis_code_categories_are_stable() -> None:
    assert ErrorCode.A11Y_IMG_ALT.category == "accessibility"
    assert ErrorCode.TYPE_UNDECLARED_VARIABLE.category == "type"
    assert ErrorCode.FRAGILE_TEMPLATE_PATH.category == "path"
    assert ErrorCode.PRIVACY_SECRET_LITERAL.category == "privacy"
    assert ErrorCode.CONTEXT_UNUSED.category == "context"
    assert ErrorCode.ESCAPE_TRUSTED_MARKUP.category == "escape"
    assert ErrorCode.MODULARITY_EXTRACTION_CANDIDATE.category == "modularity"
    assert ErrorCode.MODULARITY_PASS_THROUGH_COMPONENT.category == "modularity"
