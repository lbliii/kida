"""Lint rule — suggest relative paths for same-folder includes.

Flags cross-template references whose target lives in the same folder
as the caller. Those references will break on a folder rename even
though nothing about the caller↔target relationship changed. Rewriting
them as ``./<basename>`` makes the folder move zero-edit.

Only a same-folder match is reported. Parent-folder suggestions
(``../x``) are ambiguous and would produce false positives for
legitimate cross-cutting library references, so they are intentionally
out of scope for this rule.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from kida.analysis.node_visitor import NodeVisitor

if TYPE_CHECKING:
    from kida.nodes import Embed, Extends, FromImport, Import, Include, Template
    from kida.nodes.base import Node


@final
@dataclass(frozen=True, slots=True)
class FragilePathIssue:
    """A single fragile-path finding."""

    lineno: int
    col_offset: int
    statement: str  # "include" | "extends" | "embed" | "import" | "from"
    target: str
    suggestion: str
    severity: str = "warning"


class _FragilePathVisitor(NodeVisitor):
    """Collect cross-template references whose target is a sibling of the caller."""

    def __init__(self, caller_name: str) -> None:
        self.issues: list[FragilePathIssue] = []
        self._caller_dir = posixpath.dirname(caller_name.replace("\\", "/"))

    def visit_Include(self, node: Include) -> None:  # noqa: N802
        self._check(node, "include")
        self.generic_visit(node)

    def visit_Extends(self, node: Extends) -> None:  # noqa: N802
        self._check(node, "extends")
        self.generic_visit(node)

    def visit_Embed(self, node: Embed) -> None:  # noqa: N802
        self._check(node, "embed")
        self.generic_visit(node)

    def visit_Import(self, node: Import) -> None:  # noqa: N802
        self._check(node, "import")
        self.generic_visit(node)

    def visit_FromImport(self, node: FromImport) -> None:  # noqa: N802
        self._check(node, "from")
        self.generic_visit(node)

    def _check(self, node: Node, statement: str) -> None:
        from kida.nodes import Const

        template_expr = getattr(node, "template", None)
        if not isinstance(template_expr, Const):
            return
        target = template_expr.value
        if not isinstance(target, str):
            return
        if target.startswith(("./", "../", "@")):
            return  # already refactor-safe

        target_norm = target.replace("\\", "/")
        target_dir = posixpath.dirname(target_norm)
        if target_dir != self._caller_dir or not target_dir:
            return  # different folder, or both at root (no anchor win)

        basename = posixpath.basename(target_norm)
        self.issues.append(
            FragilePathIssue(
                lineno=template_expr.lineno,
                col_offset=template_expr.col_offset,
                statement=statement,
                target=target,
                suggestion=f"./{basename}",
            )
        )


def check_fragile_paths(ast: Template, caller_name: str) -> list[FragilePathIssue]:
    """Return all fragile-path issues in *ast* for a caller named *caller_name*."""
    visitor = _FragilePathVisitor(caller_name)
    visitor.visit(ast)
    return visitor.issues
