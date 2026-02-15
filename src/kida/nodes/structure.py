"""Template structure nodes for Kida AST."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kida.nodes.base import Node
from kida.nodes.expressions import Expr


@dataclass(frozen=True, slots=True)
class TemplateContext(Node):
    """Type declaration: {% template page: Page, site: Site %}"""

    declarations: Sequence[tuple[str, str]]


@dataclass(frozen=True, slots=True)
class Extends(Node):
    """Template inheritance: {% extends "base.html" %}"""

    template: Expr


@dataclass(frozen=True, slots=True)
class Block(Node):
    """Named block for inheritance: {% block name %}...{% end %}"""

    name: str
    body: Sequence[Node]
    scoped: bool = False
    required: bool = False
    fragment: bool = False
    condition: Expr | None = None


@dataclass(frozen=True, slots=True)
class Globals(Node):
    """Setup block for macros/variables available during render_block()."""

    body: Sequence[Node]


@dataclass(frozen=True, slots=True)
class Imports(Node):
    """Imports block — {% imports %}...{% end %}.

    Same semantics as {% globals %} but signals intent: these imports
    are for fragment/block scope. Compiles to _globals_setup.
    """

    body: Sequence[Node]


@dataclass(frozen=True, slots=True)
class Include(Node):
    """Include another template: {% include "partial.html" %}"""

    template: Expr
    with_context: bool = True
    ignore_missing: bool = False


@dataclass(frozen=True, slots=True)
class Import(Node):
    """Import functions from template: {% import "funcs.html" as f %}"""

    template: Expr
    target: str
    with_context: bool = False


@dataclass(frozen=True, slots=True)
class FromImport(Node):
    """Import specific functions: {% from "funcs.html" import button, card %}"""

    template: Expr
    names: Sequence[tuple[str, str | None]]
    with_context: bool = False


@dataclass(frozen=True, slots=True)
class Template(Node):
    """Root node representing a complete template."""

    body: Sequence[Node]
    extends: Extends | None = None
    context_type: TemplateContext | None = None


@dataclass(frozen=True, slots=True)
class Cache(Node):
    """Fragment caching: {% cache key %}...{% end %}"""

    key: Expr
    body: Sequence[Node]
    ttl: Expr | None = None
    depends: Sequence[Expr] = ()


@dataclass(frozen=True, slots=True)
class With(Node):
    """Jinja2-style context manager: {% with x = expr %}...{% end %}"""

    targets: Sequence[tuple[str, Expr]]
    body: Sequence[Node]


@dataclass(frozen=True, slots=True)
class WithConditional(Node):
    """Conditional with block: {% with expr as name %}...{% end %}"""

    expr: Expr
    target: Expr
    body: Sequence[Node]
    empty: Sequence[Node] = ()


@dataclass(frozen=True, slots=True)
class Embed(Node):
    """Embed template with block overrides: {% embed 'card.html' %}...{% end %}"""

    template: Expr
    blocks: dict[str, Block]
    with_context: bool = True
