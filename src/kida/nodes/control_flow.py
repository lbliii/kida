"""Control flow nodes for Kida AST."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kida.nodes.base import Node
from kida.nodes.expressions import Expr


@dataclass(frozen=True, slots=True)
class If(Node):
    """Conditional: {% if cond %}...{% elif cond %}...{% else %}...{% end %}"""

    test: Expr
    body: Sequence[Node]
    elif_: Sequence[tuple[Expr, Sequence[Node]]] = ()
    else_: Sequence[Node] = ()


@dataclass(frozen=True, slots=True)
class For(Node):
    """For loop: {% for x in items %}...{% empty %}...{% end %}"""

    target: Expr
    iter: Expr
    body: Sequence[Node]
    empty: Sequence[Node] = ()
    recursive: bool = False
    test: Expr | None = None


@dataclass(frozen=True, slots=True)
class AsyncFor(Node):
    """Async for loop: {% async for x in async_items %}...{% end %}"""

    target: Expr
    iter: Expr
    body: Sequence[Node]
    empty: Sequence[Node] = ()
    test: Expr | None = None


@dataclass(frozen=True, slots=True)
class While(Node):
    """While loop: {% while cond %}...{% end %}"""

    test: Expr
    body: Sequence[Node]


@dataclass(frozen=True, slots=True)
class Match(Node):
    """Pattern matching: {% match expr %}{% case pattern [if guard] %}...{% end %}"""

    subject: Expr | None
    cases: Sequence[tuple[Expr, Expr | None, Sequence[Node]]]


@dataclass(frozen=True, slots=True)
class Break(Node):
    """Break out of loop: {% break %}"""


@dataclass(frozen=True, slots=True)
class Continue(Node):
    """Skip to next iteration: {% continue %}"""
