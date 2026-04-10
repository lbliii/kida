"""Control flow nodes for Kida AST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from kida.nodes.base import Node

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kida.nodes.expressions import Expr


@final
@dataclass(frozen=True, slots=True)
class If(Node):
    """Conditional: {% if cond %}...{% elif cond %}...{% else %}...{% end %}"""

    test: Expr
    body: Sequence[Node]
    elif_: Sequence[tuple[Expr, Sequence[Node]]] = ()
    else_: Sequence[Node] = ()


@final
@dataclass(frozen=True, slots=True)
class For(Node):
    """For loop: {% for x in items %}...{% empty %}...{% end %}"""

    target: Expr
    iter: Expr
    body: Sequence[Node]
    empty: Sequence[Node] = ()
    recursive: bool = False
    test: Expr | None = None


@final
@dataclass(frozen=True, slots=True)
class AsyncFor(Node):
    """Async for loop: {% async for x in async_items %}...{% end %}"""

    target: Expr
    iter: Expr
    body: Sequence[Node]
    empty: Sequence[Node] = ()
    test: Expr | None = None


@final
@dataclass(frozen=True, slots=True)
class While(Node):
    """While loop: {% while cond %}...{% end %}"""

    test: Expr
    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class Match(Node):
    """Pattern matching: {% match expr %}{% case pattern [if guard] %}...{% end %}"""

    subject: Expr | None
    cases: Sequence[tuple[Expr, Expr | None, Sequence[Node]]]


@final
@dataclass(frozen=True, slots=True)
class Break(Node):
    """Break out of loop: {% break %}"""


@final
@dataclass(frozen=True, slots=True)
class Continue(Node):
    """Skip to next iteration: {% continue %}"""


@final
@dataclass(frozen=True, slots=True)
class Try(Node):
    """Error boundary: {% try %}...{% fallback [error] %}...{% end %}

    Catches rendering errors in body and renders fallback content instead.
    If error_name is set, the caught exception is bound as a dict in the
    fallback scope with keys: message, type, template, line.
    """

    body: Sequence[Node]
    fallback: Sequence[Node]
    error_name: str | None = None
