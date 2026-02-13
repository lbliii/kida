"""Function definition and call nodes for Kida AST."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kida.nodes.base import Node
from kida.nodes.expressions import Expr


@dataclass(frozen=True, slots=True)
class DefParam(Node):
    """A single parameter in a {% def %} with optional type annotation."""

    name: str
    annotation: str | None = None


@dataclass(frozen=True, slots=True)
class Def(Node):
    """Function definition: {% def name(params) %}...{% end %}"""

    name: str
    params: Sequence[DefParam]
    body: Sequence[Node]
    defaults: Sequence[Expr] = ()
    vararg: str | None = None
    kwarg: str | None = None

    @property
    def args(self) -> tuple[str, ...]:
        """Backward-compat bridge: returns parameter names."""
        return tuple(p.name for p in self.params)


@dataclass(frozen=True, slots=True)
class Slot(Node):
    """Slot for component content: {% slot %}"""

    name: str = "default"


@dataclass(frozen=True, slots=True)
class CallBlock(Node):
    """Call function with body content: {% call name(args) %}body{% end %}"""

    call: Expr
    body: Sequence[Node]
    args: Sequence[Expr] = ()
