"""Template structure nodes for Kida AST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from kida.nodes.base import Node

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kida.nodes.expressions import Expr


@final
@dataclass(frozen=True, slots=True)
class TemplateContext(Node):
    """Type declaration: {% template page: Page, site: Site %}"""

    declarations: Sequence[tuple[str, str]]


@final
@dataclass(frozen=True, slots=True)
class Extends(Node):
    """Template inheritance: {% extends "base.html" %}"""

    template: Expr


@final
@dataclass(frozen=True, slots=True)
class Block(Node):
    """Named block for inheritance: {% block name %}...{% end %}"""

    name: str
    body: Sequence[Node]
    scoped: bool = False
    required: bool = False
    fragment: bool = False
    condition: Expr | None = None


@final
@dataclass(frozen=True, slots=True)
class Globals(Node):
    """Setup block for macros/variables available during render_block()."""

    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class Imports(Node):
    """Imports block — {% imports %}...{% end %}.

    Same semantics as {% globals %} but signals intent: these imports
    are for fragment/block scope. Compiles to _globals_setup.
    """

    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class Include(Node):
    """Include another template: {% include "partial.html" %}"""

    template: Expr
    with_context: bool = True
    ignore_missing: bool = False


@final
@dataclass(frozen=True, slots=True)
class Import(Node):
    """Import functions from template: {% import "funcs.html" as f %}"""

    template: Expr
    target: str
    with_context: bool = False


@final
@dataclass(frozen=True, slots=True)
class FromImport(Node):
    """Import specific functions: {% from "funcs.html" import button, card %}"""

    template: Expr
    names: Sequence[tuple[str, str | None]]
    with_context: bool = False


@final
@dataclass(frozen=True, slots=True)
class Template(Node):
    """Root node representing a complete template."""

    body: Sequence[Node]
    extends: Extends | None = None
    context_type: TemplateContext | None = None


@final
@dataclass(frozen=True, slots=True)
class Cache(Node):
    """Fragment caching: {% cache key %}...{% end %}"""

    key: Expr
    body: Sequence[Node]
    ttl: Expr | None = None
    depends: Sequence[Expr] = ()


@final
@dataclass(frozen=True, slots=True)
class With(Node):
    """Jinja2-style context manager: {% with x = expr %}...{% end %}"""

    targets: Sequence[tuple[str, Expr]]
    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class WithConditional(Node):
    """Conditional with block: {% with expr as name %}...{% end %}"""

    expr: Expr
    target: Expr
    body: Sequence[Node]
    empty: Sequence[Node] = ()


@final
@dataclass(frozen=True, slots=True)
class Embed(Node):
    """Embed template with block overrides: {% embed 'card.html' %}...{% end %}"""

    template: Expr
    blocks: dict[str, Block]
    with_context: bool = True


@final
@dataclass(frozen=True, slots=True)
class Push(Node):
    """Push content to a named stack: {% push "scripts" %}...{% end %}

    Content is collected during rendering and emitted where the
    corresponding ``{% stack "scripts" %}`` appears.
    """

    stack_name: str
    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class Stack(Node):
    """Emit collected stack content: {% stack "scripts" %}

    Outputs all content pushed to the named stack via ``{% push %}``.
    """

    stack_name: str


@final
@dataclass(frozen=True, slots=True)
class Provide(Node):
    """Provide a value to descendant consumers.

    ``{% provide key = expr %}...{% endprovide %}`` pushes *value* onto
    a per-key stack in ``RenderContext``. Any descendant macro can read it
    via ``consume("key")``. Stack-based for nesting: inner provides shadow
    outer ones for the same key.
    """

    name: str
    value: Expr
    body: Sequence[Node]


@final
@dataclass(frozen=True, slots=True)
class TransVar(Node):
    """Variable binding in {% trans name=expr %}.

    Binds a template expression to a simple name for use inside
    the trans body as {{ name }}.
    """

    name: str
    expr: Expr


@final
@dataclass(frozen=True, slots=True)
class Trans(Node):
    """{% trans %}...{% endtrans %} block.

    Represents a translatable string region. The singular field holds
    the message ID with %(name)s placeholders. When {% plural %} is
    present, the plural field holds the plural form and count_expr
    provides the ngettext dispatch value.
    """

    singular: str
    plural: str | None = None
    variables: tuple[TransVar, ...] = ()
    count_expr: Expr | None = None
