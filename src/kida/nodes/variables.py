"""Variable and scoping nodes for Kida AST."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kida.nodes.base import Node
from kida.nodes.expressions import Expr, Filter


@dataclass(frozen=True, slots=True)
class Let(Node):
    """Template-scoped variable: {% let x = expr %}"""

    name: Expr
    value: Expr


@dataclass(frozen=True, slots=True)
class Set(Node):
    """Block-scoped variable: {% set x = expr %}"""

    target: Expr
    value: Expr


@dataclass(frozen=True, slots=True)
class Export(Node):
    """Export variable from inner scope: {% export x = expr %}"""

    name: Expr
    value: Expr


@dataclass(frozen=True, slots=True)
class Capture(Node):
    """Capture block content: {% capture x %}...{% end %}"""

    name: str
    body: Sequence[Node]
    filter: Filter | None = None
