"""Template structure block parsing for Kida parser.

Provides mixin for parsing template structure statements (block, extends, include, from_import).

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from kida._types import Token, TokenType
from kida.nodes import Block, Extends, FromImport, Globals, Import, Include

if TYPE_CHECKING:
    from kida.nodes import Expr, Node
    from kida.parser.errors import ParseError

from kida.parser.blocks.core import BlockStackMixin


class TemplateStructureBlockParsingMixin(BlockStackMixin):
    """Mixin for parsing template structure blocks.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks. Inherits block stack management from BlockStackMixin.

    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes and cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # Host attributes (from Parser.__init__)
        _tokens: Sequence[Token]
        _pos: int
        _block_stack: list[tuple[str, int, int]]

        # From TokenNavigationMixin (ParserCoreProtocol members)
        @property
        def _current(self) -> Token: ...
        def _peek(self, offset: int = 0) -> Token: ...
        def _advance(self) -> Token: ...
        def _expect(self, token_type: TokenType) -> Token: ...
        def _match(self, *types: TokenType) -> bool: ...
        def _error(
            self,
            message: str,
            token: Token | None = None,
            suggestion: str | None = None,
        ) -> ParseError: ...

        # From StatementParsingMixin
        def _parse_body(self, stop_on_continuation: bool = False) -> list[Node]: ...

        # From ExpressionParsingMixin
        def _parse_expression(self) -> Expr: ...

    def _parse_block_tag(self) -> Block:
        """Parse {% block name [if expr] %}...{% end %} or {% endblock %}.

        The optional ``if expr`` guard causes the block to be skipped
        during full render when the expression is falsy.
        """
        start = self._advance()  # consume 'block'
        self._push_block("block", start)

        if self._current.type != TokenType.NAME:
            raise self._error("Expected block name")
        name = self._advance().value

        # Optional condition: {% block detail if show_detail %}
        condition: Expr | None = None
        if self._current.type == TokenType.NAME and self._current.value == "if":
            self._advance()  # consume 'if'
            condition = self._parse_expression()

        self._expect(TokenType.BLOCK_END)
        body = self._parse_body()

        # Consume end tag
        self._consume_end_tag("block")

        return Block(
            lineno=start.lineno,
            col_offset=start.col_offset,
            name=name,
            body=tuple(body),
            condition=condition,
        )

    def _parse_globals_tag(self) -> Globals:
        """Parse {% globals %}...{% end %} — setup block for render_block().

        The globals block defines macros and variables that are available during
        both full render() and render_block(). This solves the problem of macros
        defined in base templates being invisible during fragment rendering.

        Only one {% globals %} block is allowed per template.
        """
        start = self._advance()  # consume 'globals'
        self._push_block("globals", start)

        self._expect(TokenType.BLOCK_END)
        body = self._parse_body()

        # Consume end tag
        self._consume_end_tag("globals")

        return Globals(
            lineno=start.lineno,
            col_offset=start.col_offset,
            body=tuple(body),
        )

    def _parse_fragment_tag(self) -> Block:
        """Parse {% fragment name %}...{% end %} — fragment-only block.

        Fragment blocks are skipped during full template render() and only
        rendered when explicitly requested via render_block(). This avoids
        UndefinedError for blocks whose variables are only provided during
        fragment rendering (e.g., htmx OOB swaps, SSE partials).
        """
        start = self._advance()  # consume 'fragment'
        self._push_block("fragment", start)

        if self._current.type != TokenType.NAME:
            raise self._error("Expected fragment block name")
        name = self._advance().value

        self._expect(TokenType.BLOCK_END)
        body = self._parse_body()

        # Consume end tag
        self._consume_end_tag("fragment")

        return Block(
            lineno=start.lineno,
            col_offset=start.col_offset,
            name=name,
            body=tuple(body),
            fragment=True,
        )

    def _parse_extends(self) -> Extends:
        """Parse {% extends "base.html" %}."""
        start = self._advance()  # consume 'extends'
        template = self._parse_expression()
        self._expect(TokenType.BLOCK_END)

        return Extends(
            lineno=start.lineno,
            col_offset=start.col_offset,
            template=template,
        )

    def _parse_include(self) -> Include:
        """Parse {% include "partial.html" [with context] [ignore missing] %}."""
        start = self._advance()  # consume 'include'
        template = self._parse_expression()

        with_context = True
        ignore_missing = False

        # Parse optional modifiers
        while self._current.type == TokenType.NAME:
            keyword = self._current.value
            if keyword == "with":
                self._advance()  # consume 'with'
                if self._current.type == TokenType.NAME and self._current.value == "context":
                    self._advance()  # consume 'context'
                    with_context = True
                elif self._current.type == TokenType.NAME:
                    # Detected Jinja2 "with var=value" pattern
                    raise self._error(
                        'Jinja2\'s "include with var=value" syntax is not supported',
                        suggestion=(
                            "In Kida, set variables before the include:\n"
                            "  {% let var = value %}\n"
                            "  {% include 'template.html' %}"
                        ),
                    )
                else:
                    raise self._error(
                        "Expected 'context' after 'with'",
                        suggestion=(
                            "Use '{% include \"template.html\" with context %}' "
                            "or just '{% include \"template.html\" %}'"
                        ),
                    )
            elif keyword == "without":
                self._advance()  # consume 'without'
                if self._current.type == TokenType.NAME and self._current.value == "context":
                    self._advance()  # consume 'context'
                    with_context = False
                else:
                    raise self._error(
                        "Expected 'context' after 'without'",
                        suggestion="Use '{% include \"template.html\" without context %}'",
                    )
            elif keyword == "ignore":
                self._advance()  # consume 'ignore'
                if self._current.type == TokenType.NAME and self._current.value == "missing":
                    self._advance()  # consume 'missing'
                    ignore_missing = True
                else:
                    raise self._error(
                        "Expected 'missing' after 'ignore'",
                        suggestion="Use '{% include \"template.html\" ignore missing %}'",
                    )
            else:
                break

        self._expect(TokenType.BLOCK_END)

        return Include(
            lineno=start.lineno,
            col_offset=start.col_offset,
            template=template,
            with_context=with_context,
            ignore_missing=ignore_missing,
        )

    def _parse_import(self) -> Import:
        """Parse {% import "template.html" as f [with context] %}."""
        start = self._advance()  # consume 'import'

        template = self._parse_expression()

        # Expect 'as'
        if self._current.type != TokenType.NAME or self._current.value != "as":
            raise self._error("Expected 'as' after template name in import")
        self._advance()  # consume 'as'

        if self._current.type != TokenType.NAME:
            raise self._error("Expected alias name for import")
        target = self._advance().value

        with_context = False
        if self._current.type == TokenType.NAME and self._current.value == "with":
            self._advance()  # consume 'with'
            if self._current.type == TokenType.NAME and self._current.value == "context":
                self._advance()  # consume 'context'
                with_context = True
            else:
                raise self._error("Expected 'context' after 'with'")

        self._expect(TokenType.BLOCK_END)

        return Import(
            lineno=start.lineno,
            col_offset=start.col_offset,
            template=template,
            target=target,
            with_context=with_context,
        )

    def _parse_from_import(self) -> FromImport:
        """Parse {% from "template.html" import name1, name2 as alias %}."""
        start = self._advance()  # consume 'from'

        template = self._parse_expression()

        # Expect 'import'
        if self._current.type != TokenType.NAME or self._current.value != "import":
            raise self._error("Expected 'import' after template name")
        self._advance()  # consume 'import'

        # Parse imported names
        names: list[tuple[str, str | None]] = []
        with_context = False

        while True:
            if self._current.type != TokenType.NAME:
                raise self._error("Expected name to import")
            name = self._advance().value

            # Check for alias
            alias: str | None = None
            if self._current.type == TokenType.NAME and self._current.value == "as":
                self._advance()  # consume 'as'
                if self._current.type != TokenType.NAME:
                    raise self._error("Expected alias name")
                alias = self._advance().value

            names.append((name, alias))

            # Check for comma or end
            if self._match(TokenType.COMMA):
                self._advance()
            elif self._current.type == TokenType.NAME and self._current.value == "with":
                self._advance()  # consume 'with'
                if self._current.type == TokenType.NAME and self._current.value == "context":
                    self._advance()  # consume 'context'
                    with_context = True
                break
            elif self._match(TokenType.BLOCK_END):
                break
            else:
                break

        self._expect(TokenType.BLOCK_END)

        return FromImport(
            lineno=start.lineno,
            col_offset=start.col_offset,
            template=template,
            names=tuple(names),
            with_context=with_context,
        )
