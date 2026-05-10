"""Static privacy lint findings for templates and report fixtures."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, final

from kida.analysis.dependencies import DependencyWalker
from kida.nodes import (
    Const,
    Embed,
    Expr,
    Extends,
    Filter,
    FromImport,
    Import,
    Include,
    Node,
    Output,
)

_SENSITIVE_TERMS = frozenset(
    {
        "api_key",
        "cookie",
        "email",
        "password",
        "private",
        "secret",
        "session",
        "staff",
        "token",
    }
)
_BROAD_DEBUG_NAMES = frozenset({"context", "ctx", "debug", "request", "session"})
_SECRET_LITERAL_RE = re.compile(
    r"(?i)(api[_-]?key|password|secret|session|token)\s*[:=]\s*['\"]?([^\s'\"<>]{6,})"
)


@final
@dataclass(frozen=True, slots=True)
class PrivacyFinding:
    """Machine-readable privacy lint finding."""

    code: Literal["K-PRI-001", "K-PRI-002", "K-PRI-003", "K-PRI-004", "K-PRI-005"]
    severity: Literal["error", "warning"]
    kind: str
    message: str
    template_name: str | None = None
    lineno: int | None = None
    col_offset: int | None = None
    path: str | None = None
    suggestion: str | None = None


def _walk(node: Node) -> list[Node]:
    nodes = [node]
    for child in node.iter_child_nodes():
        nodes.extend(_walk(child))
    return nodes


def _expr_label(expr: Expr) -> str:
    deps = sorted(DependencyWalker().analyze(expr))
    return deps[0] if deps else type(expr).__name__


def _is_sensitive_path(path: str) -> bool:
    lower = path.lower()
    parts = re.split(r"[._:-]+", lower)
    return any(term in parts or term in lower for term in _SENSITIVE_TERMS)


def _literal_contains_secret(value: str) -> bool:
    return bool(_SECRET_LITERAL_RE.search(value))


def lint_privacy(template_or_ast: Any) -> list[PrivacyFinding]:
    """Return static privacy findings without echoing secret literal values."""
    ast = getattr(template_or_ast, "_optimized_ast", template_or_ast)
    if ast is None:
        return []
    template_name = getattr(template_or_ast, "name", None)

    findings: list[PrivacyFinding] = []
    dependencies = (
        set(template_or_ast.depends_on()) if hasattr(template_or_ast, "depends_on") else set()
    )
    if not dependencies and isinstance(ast, Node):
        dependencies = set(DependencyWalker().analyze(ast))

    findings.extend(
        PrivacyFinding(
            code="K-PRI-001",
            severity="warning",
            kind="sensitive-context-path",
            template_name=template_name,
            path=path,
            message=f"Template reads sensitive-looking context path '{path}'.",
            suggestion="Confirm this value is intended for rendered output.",
        )
        for path in sorted(dependencies)
        if _is_sensitive_path(path)
    )

    for node in _walk(ast):
        if (
            isinstance(node, Const)
            and isinstance(node.value, str)
            and _literal_contains_secret(node.value)
        ):
            findings.append(
                PrivacyFinding(
                    code="K-PRI-002",
                    severity="error",
                    kind="secret-like-literal",
                    template_name=template_name,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    message="Template contains a secret-like literal value.",
                    suggestion="Move secrets out of templates and redact report fixtures.",
                )
            )

        if isinstance(node, Output):
            label = _expr_label(node.expr)
            if label in _BROAD_DEBUG_NAMES:
                findings.append(
                    PrivacyFinding(
                        code="K-PRI-004",
                        severity="warning",
                        kind="broad-context-output",
                        template_name=template_name,
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        path=label,
                        message=f"Template appears to render broad context object '{label}'.",
                        suggestion="Render specific fields instead of broad context/debug objects.",
                    )
                )

        if isinstance(node, Filter) and node.name == "safe":
            label = _expr_label(node.value)
            if _is_sensitive_path(label):
                findings.append(
                    PrivacyFinding(
                        code="K-PRI-003",
                        severity="warning",
                        kind="safe-sensitive-value",
                        template_name=template_name,
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        path=label,
                        message=f"Sensitive-looking value '{label}' is marked safe.",
                        suggestion="Avoid |safe on sensitive values unless a sanitizer and trust reason are documented.",
                    )
                )

        if isinstance(node, (Extends, Include, Import, FromImport, Embed)):
            template_expr = node.template
            if not (isinstance(template_expr, Const) and isinstance(template_expr.value, str)):
                findings.append(
                    PrivacyFinding(
                        code="K-PRI-005",
                        severity="warning",
                        kind="dynamic-template-name",
                        template_name=template_name,
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        message="Template name is dynamic and cannot be checked against a static allowlist.",
                        suggestion="Use literal template names when a privacy policy requires static includes.",
                    )
                )

    return findings
