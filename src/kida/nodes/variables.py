"""Variable and scoping nodes for Kida AST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from kida.nodes.base import Node

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kida.nodes.expressions import Expr, Filter


@final
@dataclass(frozen=True, slots=True)
class Let(Node):
    """Template-scoped variable: {% let x = expr %} or {% let x ??= expr %}"""

    name: Expr
    value: Expr
    coalesce: bool = False  # ??= — assign only if undefined/None


@final
@dataclass(frozen=True, slots=True)
class Set(Node):
    """Block-scoped variable: {% set x = expr %} or {% set x ??= expr %}"""

    target: Expr
    value: Expr
    coalesce: bool = False  # ??= — assign only if undefined/None


@final
@dataclass(frozen=True, slots=True)
class Export(Node):
    """Export variable from inner scope: {% export x = expr %} or {% export x ??= expr %}"""

    name: Expr
    value: Expr
    coalesce: bool = False  # ??= — assign only if undefined/None


@final
@dataclass(frozen=True, slots=True)
class Capture(Node):
    """Capture block content: {% capture x %}...{% end %}"""

    name: str
    body: Sequence[Node]
    filter: Filter | None = None
