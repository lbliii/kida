"""Function definition and call nodes for Kida AST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from kida.nodes.base import Node

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kida.nodes.expressions import Expr


@final
@dataclass(frozen=True, slots=True)
class DefParam(Node):
    """A single parameter in a {% def %} with optional type annotation."""

    name: str
    annotation: str | None = None


@final
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


@final
@dataclass(frozen=True, slots=True)
class Region(Node):
    """Parameterized renderable unit: {% region name(params) %}...{% end %}.

    Compiles to BOTH a block function (for render_block) AND a callable
    (for {{ name(args) }}). Parameters make it self-contained.
    """

    name: str
    params: Sequence[DefParam]
    body: Sequence[Node]
    defaults: Sequence[Expr] = ()
    vararg: str | None = None
    kwarg: str | None = None
    condition: Expr | None = None

    @property
    def args(self) -> tuple[str, ...]:
        """Backward-compat bridge: returns parameter names."""
        return tuple(p.name for p in self.params)


@final
@dataclass(frozen=True, slots=True)
class Slot(Node):
    """Slot placeholder inside {% def %}: {% slot %} or {% slot name %}"""

    name: str = "default"


@final
@dataclass(frozen=True, slots=True)
class SlotBlock(Node):
    """Named slot content inside {% call %}: {% slot name %}...{% end %}"""

    name: str
    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class CallBlock(Node):
    """Call function with slot content: {% call name(args) %}...{% end %}"""

    call: Expr
    slots: dict[str, Sequence[Node]]
    args: Sequence[Expr] = ()

    @property
    def body(self) -> Sequence[Node]:
        """Backward-compat: default slot content."""
        return self.slots.get("default", ())
