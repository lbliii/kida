"""Static escape and trusted-markup audit findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, final

from kida.analysis.dependencies import DependencyWalker
from kida.nodes import Autoescape, Const, Expr, Filter, MarkSafe, Node, Output


@final
@dataclass(frozen=True, slots=True)
class EscapeAuditFinding:
    """Machine-readable escaping and trusted-markup audit finding."""

    code: Literal["K-ESC-001", "K-ESC-002", "K-ESC-003", "K-ESC-004", "K-ESC-005"]
    severity: Literal["info", "warning"]
    kind: str
    message: str
    template_name: str | None = None
    lineno: int | None = None
    col_offset: int | None = None
    expression: str | None = None
    suggestion: str | None = None


def _walk(node: Node) -> list[Node]:
    nodes = [node]
    for child in node.iter_child_nodes():
        nodes.extend(_walk(child))
    return nodes


def _expr_nodes(expr: Expr) -> list[Node]:
    return _walk(expr)


def _expr_label(expr: Expr) -> str:
    deps = sorted(DependencyWalker().analyze(expr))
    return deps[0] if deps else type(expr).__name__


def _safe_reason(node: Filter) -> str | None:
    reason = node.kwargs.get("reason")
    if isinstance(reason, Const) and isinstance(reason.value, str):
        return reason.value
    return None


def audit_escaping(
    template_or_ast: Any,
    *,
    include_output_sites: bool = True,
) -> list[EscapeAuditFinding]:
    """Return static escaping and trusted-markup findings for a template.

    This does not change render behavior. It reports observable template facts:
    escaped output sites, unescaped output sites, ``| safe`` uses and review
    reasons, plus filters that intentionally return trusted markup.
    """
    ast = getattr(template_or_ast, "_optimized_ast", template_or_ast)
    if ast is None:
        return []
    template_name = getattr(template_or_ast, "name", None)

    findings: list[EscapeAuditFinding] = []
    for node in _walk(ast):
        if isinstance(node, Autoescape) and not node.enabled:
            findings.append(
                EscapeAuditFinding(
                    code="K-ESC-003",
                    severity="warning",
                    kind="autoescape-disabled",
                    template_name=template_name,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    message="Autoescape is disabled for this template block.",
                    suggestion="Keep autoescape enabled unless every output in the block is trusted.",
                )
            )
            continue

        if not isinstance(node, Output):
            continue

        expression = _expr_label(node.expr)
        if include_output_sites:
            findings.append(
                EscapeAuditFinding(
                    code="K-ESC-001" if node.escape else "K-ESC-003",
                    severity="info" if node.escape else "warning",
                    kind="escaped-output" if node.escape else "unescaped-output",
                    template_name=template_name,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    expression=expression,
                    message=(
                        "Output expression is escaped by the active render surface."
                        if node.escape
                        else "Output expression is rendered without autoescape."
                    ),
                    suggestion=None
                    if node.escape
                    else "Escape this value or mark the trust boundary explicitly.",
                )
            )

        for expr_node in _expr_nodes(node.expr):
            if isinstance(expr_node, MarkSafe):
                findings.append(
                    EscapeAuditFinding(
                        code="K-ESC-002",
                        severity="warning",
                        kind="trusted-markup",
                        template_name=template_name,
                        lineno=expr_node.lineno,
                        col_offset=expr_node.col_offset,
                        expression=_expr_label(expr_node.value),
                        message="Expression is marked safe and bypasses escaping.",
                        suggestion="Document why this value is trusted and sanitized.",
                    )
                )
            elif isinstance(expr_node, Filter):
                if expr_node.name == "safe":
                    reason = _safe_reason(expr_node)
                    findings.append(
                        EscapeAuditFinding(
                            code="K-ESC-002",
                            severity="warning",
                            kind="safe-filter",
                            template_name=template_name,
                            lineno=expr_node.lineno,
                            col_offset=expr_node.col_offset,
                            expression=_expr_label(expr_node.value),
                            message=(
                                "|safe marks output as trusted markup."
                                if reason is None
                                else f"|safe marks output as trusted markup: {reason}"
                            ),
                            suggestion=None
                            if reason
                            else 'Add safe(reason="...") explaining the trust boundary.',
                        )
                    )
                elif expr_node.name == "tojson":
                    findings.append(
                        EscapeAuditFinding(
                            code="K-ESC-004",
                            severity="info",
                            kind="tojson",
                            template_name=template_name,
                            lineno=expr_node.lineno,
                            col_offset=expr_node.col_offset,
                            expression=_expr_label(expr_node.value),
                            message="tojson returns trusted JSON markup for safe embedding.",
                            suggestion="Use tojson(attr=true) inside HTML attributes.",
                        )
                    )
                elif expr_node.name == "xmlattr":
                    findings.append(
                        EscapeAuditFinding(
                            code="K-ESC-005",
                            severity="info",
                            kind="xmlattr",
                            template_name=template_name,
                            lineno=expr_node.lineno,
                            col_offset=expr_node.col_offset,
                            expression=_expr_label(expr_node.value),
                            message="xmlattr returns trusted HTML attribute markup.",
                        )
                    )

    return findings
