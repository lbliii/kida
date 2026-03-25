"""Extension/plugin architecture for Kida template engine.

Allows third-party packages to register custom tags, filters, tests,
and globals without modifying core code.

Usage::

    import ast
    from dataclasses import dataclass
    from kida import Environment
    from kida.extensions import Extension
    from kida.nodes.base import Node

    @dataclass(frozen=True, slots=True)
    class DebugNode(Node):
        expr: object  # Expr node

    class DebugExtension(Extension):
        tags = {"debug"}

        def parse(self, parser, tag_name):
            token = parser._advance()  # consume "debug"
            expr = parser._parse_expression()
            parser._expect(parser.TokenType.BLOCK_END)
            return DebugNode(lineno=token.lineno, col_offset=token.col_offset, expr=expr)

        def compile(self, compiler, node):
            expr = compiler._compile_expr(node.expr)
            return [ast.Expr(value=ast.Call(
                func=ast.Name(id="print", ctx=ast.Load()),
                args=[expr], keywords=[],
            ))]

    env = Environment(extensions=[DebugExtension])

"""

from __future__ import annotations

import ast
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from kida.nodes.base import Node


class Extension:
    """Base class for Kida template extensions.

    Subclass this to add custom tags, filters, tests, or globals.

    Attributes:
        tags: Set of block keyword strings this extension handles.
            When the parser encounters ``{% tagname ... %}``, it calls
            this extension's ``parse()`` method.
        end_keywords: Set of end keywords for tags with bodies.
            E.g., ``{"enddebug"}`` for a ``{% debug %}...{% enddebug %}`` tag.
    """

    tags: ClassVar[set[str]] = set()
    end_keywords: ClassVar[set[str]] = set()
    node_types: ClassVar[set[str]] = set()  # Node class names this extension compiles

    def __init__(self, environment: Any) -> None:
        self.environment = environment

    def get_filters(self) -> dict[str, Callable[..., Any]]:
        """Return filters provided by this extension."""
        return {}

    def get_tests(self) -> dict[str, Callable[..., Any]]:
        """Return tests provided by this extension."""
        return {}

    def get_globals(self) -> dict[str, Any]:
        """Return global variables provided by this extension."""
        return {}

    def parse(self, parser: Any, tag_name: str) -> Node:
        """Parse a tag handled by this extension.

        Called when the parser encounters a block keyword in ``self.tags``.
        The parser's current token is the tag name token.

        Args:
            parser: The Parser instance (provides _advance, _expect,
                _parse_expression, _parse_body, etc.)
            tag_name: The keyword that triggered this call.

        Returns:
            An AST Node (typically a custom frozen dataclass).
        """
        raise NotImplementedError(f"Extension {type(self).__name__} does not implement parse()")

    def compile(self, compiler: Any, node: Node) -> list[ast.stmt]:
        """Compile a node produced by this extension's parse().

        Called when the compiler encounters a node whose type name
        matches a registration from this extension.

        Args:
            compiler: The Compiler instance (provides _compile_expr,
                _compile_node, _emit_output, etc.)
            node: The AST node to compile.

        Returns:
            List of Python AST statements.
        """
        raise NotImplementedError(f"Extension {type(self).__name__} does not implement compile()")
