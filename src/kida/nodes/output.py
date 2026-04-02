"""Output and formatting nodes for Kida AST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from kida.nodes.base import Node

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kida.nodes.expressions import Expr, Filter


@final
@dataclass(frozen=True, slots=True)
class Output(Node):
    """Output expression: {{ expr }}"""

    expr: Expr
    escape: bool = True


@final
@dataclass(frozen=True, slots=True)
class Data(Node):
    """Raw text data between template constructs."""

    value: str


@final
@dataclass(frozen=True, slots=True)
class FilterBlock(Node):
    """Apply filter to block: {% filter upper %}...{% end %}"""

    filter: Filter
    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class Autoescape(Node):
    """Control autoescaping: {% autoescape true %}...{% end %}"""

    enabled: bool
    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class Raw(Node):
    """Raw block (no template processing): {% raw %}...{% end %}"""

    value: str


@final
@dataclass(frozen=True, slots=True)
class Trim(Node):
    """Whitespace control block: {% trim %}...{% end %}"""

    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class Spaceless(Node):
    """Remove whitespace between HTML tags: {% spaceless %}...{% end %}"""

    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class Flush(Node):
    """Streaming flush boundary: {% flush %}"""
