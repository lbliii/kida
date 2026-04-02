"""Template type checker for Kida.

Validates that template variables match ``{% template %}`` declarations.
Catches typos, missing variables, and undeclared context access at
compile time.

Usage::

    from kida.analysis.type_checker import check_types
    issues = check_types(template_ast)
    for issue in issues:
        print(f"Line {issue.lineno}: {issue.message}")

CLI::

    kida check --typed templates/

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from kida.analysis.node_visitor import NodeVisitor

if TYPE_CHECKING:
    from kida.nodes import (
        Capture,
        Def,
        Export,
        For,
        FromImport,
        Import,
        Let,
        Name,
        Node,
        Set,
        Template,
        With,
    )


@final
@dataclass(frozen=True, slots=True)
class TypeIssue:
    """A single type-checking finding."""

    lineno: int
    col_offset: int
    rule: str  # "undeclared-var", "unused-declared", "typo-suggestion"
    message: str
    severity: str = "warning"  # "warning" | "error"


# Built-in names that don't need declaration
_BUILTIN_NAMES = frozenset(
    {
        "range",
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "min",
        "max",
        "sum",
        "abs",
        "round",
        "sorted",
        "reversed",
        "enumerate",
        "zip",
        "map",
        "filter",
        "any",
        "all",
        "hasattr",
        "getattr",
        "isinstance",
        "type",
        "true",
        "false",
        "none",
        "True",
        "False",
        "None",
        "loop",
        "caller",
        "super",
        # HTMX helpers
        "hx_request",
        "hx_target",
        "hx_trigger",
        "hx_boosted",
        "csrf_token",
        "csp_nonce",
    }
)


class _TypeCheckVisitor(NodeVisitor):
    """Collects variable references and local bindings for type checking."""

    def __init__(self, declared_names: frozenset[str]) -> None:
        self._declared = declared_names
        self._locals: set[str] = set()
        self._scope_stack: list[set[str]] = []
        self._used_names: list[tuple[str, int, int]] = []  # (name, line, col)
        self._used_declared: set[str] = set()

    def visit_Name(self, node: Name) -> None:  # noqa: N802
        if node.ctx == "load":
            name = node.name
            if name not in self._locals and name not in _BUILTIN_NAMES:
                self._used_names.append((name, node.lineno, node.col_offset))
                if name in self._declared:
                    self._used_declared.add(name)

    def visit_Set(self, node: Set) -> None:  # noqa: N802
        if hasattr(node, "target"):
            target = node.target
            if hasattr(target, "name"):
                self._locals.add(target.name)  # type: ignore[arg-type]
        self.generic_visit(node)

    def visit_Let(self, node: Let) -> None:  # noqa: N802
        name_node = node.name
        if hasattr(name_node, "name"):
            self._locals.add(name_node.name)  # type: ignore[arg-type]
        self.generic_visit(node)

    def visit_Export(self, node: Export) -> None:  # noqa: N802
        name_node = node.name
        if hasattr(name_node, "name"):
            self._locals.add(name_node.name)  # type: ignore[arg-type]
        self.generic_visit(node)

    def visit_Capture(self, node: Capture) -> None:  # noqa: N802
        self._locals.add(node.name)
        self.generic_visit(node)

    def visit_For(self, node: For) -> None:  # noqa: N802
        self._push_scope()
        self._add_target_names(node.target)
        self.generic_visit(node)
        self._pop_scope()

    def visit_With(self, node: With) -> None:  # noqa: N802
        self._push_scope()
        for name, _expr in node.targets:
            self._locals.add(name)
        self.generic_visit(node)
        self._pop_scope()

    def visit_Def(self, node: Def) -> None:  # noqa: N802
        self._locals.add(node.name)
        self._push_scope()
        for param in node.params:
            self._locals.add(param.name)
        self.generic_visit(node)
        self._pop_scope()

    def visit_Import(self, node: Import) -> None:  # noqa: N802
        self._locals.add(node.target)
        self.generic_visit(node)

    def visit_FromImport(self, node: FromImport) -> None:  # noqa: N802
        for name, alias in node.names:
            self._locals.add(alias or name)
        self.generic_visit(node)

    def _push_scope(self) -> None:
        self._scope_stack.append(self._locals.copy())

    def _pop_scope(self) -> None:
        if self._scope_stack:
            self._locals = self._scope_stack.pop()

    def _add_target_names(self, target: Node) -> None:
        """Extract names from for-loop target (single name or tuple)."""
        from kida.nodes import Name as NameNode
        from kida.nodes import Tuple as TupleNode

        if isinstance(target, NameNode):
            self._locals.add(target.name)
        elif isinstance(target, TupleNode):
            for item in target.items:
                self._add_target_names(item)


def _suggest_typo(name: str, candidates: list[str]) -> str | None:
    """Suggest a declared name if the given name looks like a typo."""
    if not candidates:
        return None
    # Simple edit distance check (1 char difference)
    for candidate in candidates:
        if abs(len(name) - len(candidate)) <= 2:
            # Check prefix match (common typo: extra/missing char)
            if name.startswith(candidate[:3]) or candidate.startswith(name[:3]):
                return candidate
            # Check Levenshtein distance = 1
            if _edit_distance_one(name, candidate):
                return candidate
    return None


def _edit_distance_one(a: str, b: str) -> bool:
    """Check if two strings have edit distance <= 1."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = sum(1 for x, y in zip(a, b, strict=False) if x != y)
        return diffs == 1
    # Insertion/deletion
    short, long = (a, b) if len(a) < len(b) else (b, a)
    j = 0
    diffs = 0
    for i in range(len(long)):
        if j < len(short) and long[i] == short[j]:
            j += 1
        else:
            diffs += 1
    return diffs <= 1


def check_types(template: Template) -> list[TypeIssue]:
    """Type-check a template against its ``{% template %}`` declarations.

    If the template has no ``{% template %}`` declaration, returns an
    empty list (no declarations = no constraints).

    Args:
        template: Parsed Template AST node.

    Returns:
        List of TypeIssue findings, sorted by line number.
    """
    if template.context_type is None:
        return []

    declared = frozenset(name for name, _type in template.context_type.declarations)
    declared_sorted = sorted(declared)

    visitor = _TypeCheckVisitor(declared)
    visitor.visit(template)

    issues: list[TypeIssue] = []

    # Check for undeclared variable access
    for name, lineno, col in visitor._used_names:
        if name not in declared:
            suggestion = _suggest_typo(name, declared_sorted)
            msg = f"Variable '{name}' used but not declared in {{% template %}}"
            if suggestion:
                msg += f" (did you mean '{suggestion}'?)"
                issues.append(
                    TypeIssue(
                        lineno=lineno,
                        col_offset=col,
                        rule="typo-suggestion",
                        message=msg,
                    )
                )
            else:
                issues.append(
                    TypeIssue(
                        lineno=lineno,
                        col_offset=col,
                        rule="undeclared-var",
                        message=msg,
                    )
                )

    # Check for declared but unused variables
    for name, _type in template.context_type.declarations:
        if name not in visitor._used_declared:
            issues.append(
                TypeIssue(
                    lineno=template.context_type.lineno,
                    col_offset=template.context_type.col_offset,
                    rule="unused-declared",
                    message=f"Declared variable '{name}' is never used",
                )
            )

    return sorted(issues, key=lambda i: (i.lineno, i.col_offset))
