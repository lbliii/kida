"""Function block parsing for Kida parser.

Provides mixin for parsing function related statements (def, call, slot).

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida._types import Token, TokenType
from kida.nodes import CallBlock, Def, DefParam, Region, Slot, SlotBlock

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kida.exceptions import ErrorCode
    from kida.nodes import Data, Expr, Node, Output
    from kida.parser.errors import ParseError

from kida.parser.blocks.core import BlockStackMixin


class FunctionBlockParsingMixin(BlockStackMixin):
    """Mixin for parsing function blocks.

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
        def _advance(self) -> Token: ...
        def _expect(self, token_type: TokenType) -> Token: ...
        def _match(self, *types: TokenType) -> bool: ...
        def _error(
            self,
            message: str,
            token: Token | None = None,
            suggestion: str | None = None,
            code: ErrorCode | None = None,
        ) -> ParseError: ...

        # From StatementParsingMixin
        def _parse_body(self, stop_on_continuation: bool = False) -> list[Node]: ...
        def _peek(self, offset: int = 0) -> Token: ...
        def _parse_block(self) -> Node | list[Node] | None: ...
        def _parse_data(self) -> Data: ...
        def _parse_output(self) -> Output: ...
        def _skip_comment(self) -> None: ...

        # From ExpressionParsingMixin
        def _parse_expression(self) -> Expr: ...

    def _parse_type_annotation(self) -> str | None:
        """Parse an optional type annotation after a parameter name.

        Called when the current token is COLON (indicating a type follows).
        Consumes the colon and type expression tokens, returning the raw
        annotation string.

        Grammar::

            type_expr := NAME [ '|' NAME ]* [ '[' type_expr (',' type_expr)* ']' ]

        Handles: ``str``, ``int``, ``list``, ``str | None``,
        ``dict[str, int]``, ``MyModel``.

        Returns:
            Raw annotation string, or None if no colon follows.
        """
        if not self._match(TokenType.COLON):
            return None

        self._advance()  # consume ':'

        # Must start with a NAME
        if self._current.type != TokenType.NAME:
            raise self._error(
                "Expected type name after ':'",
                suggestion="Annotation syntax: name: str, name: str | None",
            )

        parts: list[str] = [self._advance().value]

        # Handle generic parameters: name[T, U]
        if self._match(TokenType.LBRACKET):
            parts.append("[")
            self._advance()  # consume '['
            parts.append(self._parse_type_annotation_inner())
            while self._match(TokenType.COMMA):
                self._advance()  # consume ','
                parts.append(", ")
                parts.append(self._parse_type_annotation_inner())
            self._expect(TokenType.RBRACKET)
            parts.append("]")

        # Handle union: T | U | V
        while self._match(TokenType.PIPE):
            self._advance()  # consume '|'
            if self._current.type != TokenType.NAME:
                raise self._error(
                    "Expected type name after '|'",
                    suggestion="Union syntax: str | None",
                )
            parts.append(" | ")
            parts.append(self._advance().value)

            # Handle generic after union member: T | list[U]
            if self._match(TokenType.LBRACKET):
                parts.append("[")
                self._advance()  # consume '['
                parts.append(self._parse_type_annotation_inner())
                while self._match(TokenType.COMMA):
                    self._advance()
                    parts.append(", ")
                    parts.append(self._parse_type_annotation_inner())
                self._expect(TokenType.RBRACKET)
                parts.append("]")

        return "".join(parts)

    def _parse_type_annotation_inner(self) -> str:
        """Parse a single type inside brackets (for generic parameters).

        Returns:
            Type string (e.g. "str", "str | None").
        """
        if self._current.type != TokenType.NAME:
            raise self._error("Expected type name in generic parameter")

        parts: list[str] = [self._advance().value]

        # Nested generics: dict[str, list[int]]
        if self._match(TokenType.LBRACKET):
            parts.append("[")
            self._advance()
            parts.append(self._parse_type_annotation_inner())
            while self._match(TokenType.COMMA):
                self._advance()
                parts.append(", ")
                parts.append(self._parse_type_annotation_inner())
            self._expect(TokenType.RBRACKET)
            parts.append("]")

        # Union inside generics: list[str | None]
        while self._match(TokenType.PIPE):
            self._advance()
            if self._current.type != TokenType.NAME:
                raise self._error("Expected type name after '|'")
            parts.append(" | ")
            parts.append(self._advance().value)

        return "".join(parts)

    def _parse_def(self) -> Def:
        """Parse {% def name(args) %}...{% end %} or {% enddef %.

        Kida functions with true lexical scoping (can access outer scope).
        Uses stack-based parsing for proper nested block handling.

        Supports optional type annotations on parameters::

            {% def card(title: str, items: list, footer: str | None = None) %}
                ...
            {% end %}

        Example:
            {% def card(item, show_date=true) %}
                <div>{{ item.title }}</div>
                {% if show_date %}{{ item.date }}{% end %}
                <span>From: {{ site.title }}</span>  {# outer scope access #}
            {% end %}

            {{ card(page) }}
        """
        start = self._advance()  # consume 'def'
        self._push_block("def", start)

        # Get function name
        if self._current.type != TokenType.NAME:
            raise self._error(
                "Expected function name",
                suggestion="Function syntax: {% def name(args) %}...{% end %}",
            )
        name = self._advance().value

        # Parse arguments (supports type annotations, *args and **kwargs)
        params: list[DefParam] = []
        defaults: list[Expr] = []
        vararg: str | None = None
        kwarg: str | None = None
        has_args = False  # track if we've seen any args for comma handling

        self._expect(TokenType.LPAREN)
        while not self._match(TokenType.RPAREN):
            if has_args:
                self._expect(TokenType.COMMA)

            # Check for **kwargs
            if self._match(TokenType.POW):
                self._advance()  # consume **
                if self._current.type != TokenType.NAME:
                    raise self._error("Expected argument name after **")
                kwarg = self._advance().value
                has_args = True
                # **kwargs must be last
                if not self._match(TokenType.RPAREN):
                    raise self._error(
                        "**kwargs must be the last parameter",
                        suggestion="Move **kwargs to the end of the parameter list",
                    )
                break

            # Check for *args
            if self._match(TokenType.MUL):
                self._advance()  # consume *
                if self._current.type != TokenType.NAME:
                    raise self._error("Expected argument name after *")
                vararg = self._advance().value
                has_args = True
                continue

            # Regular argument
            if self._current.type != TokenType.NAME:
                raise self._error("Expected argument name")
            param_token = self._current
            arg_name = self._advance().value

            # Optional type annotation: name: type
            annotation = self._parse_type_annotation()

            params.append(
                DefParam(
                    lineno=param_token.lineno,
                    col_offset=param_token.col_offset,
                    name=arg_name,
                    annotation=annotation,
                )
            )
            has_args = True

            # Check for default value
            if self._match(TokenType.ASSIGN):
                self._advance()
                defaults.append(self._parse_expression())

        self._expect(TokenType.RPAREN)
        self._expect(TokenType.BLOCK_END)

        # Parse body using universal end detection
        body = self._parse_body()

        # Consume end tag
        self._consume_end_tag("def")

        return Def(
            lineno=start.lineno,
            col_offset=start.col_offset,
            name=name,
            params=tuple(params),
            body=tuple(body),
            defaults=tuple(defaults),
            vararg=vararg,
            kwarg=kwarg,
        )

    def _parse_region(self) -> Region:
        """Parse {% region name(params) %}...{% end %} or {% endregion %}."""
        start = self._advance()  # consume 'region'
        self._push_block("region", start)

        if self._current.type != TokenType.NAME:
            raise self._error(
                "Expected region name",
                suggestion="Region syntax: {% region name(params) %}...{% end %}",
            )
        name = self._advance().value

        params: list[DefParam] = []
        defaults: list[Expr] = []
        vararg: str | None = None
        kwarg: str | None = None
        has_args = False

        self._expect(TokenType.LPAREN)
        while not self._match(TokenType.RPAREN):
            if has_args:
                self._expect(TokenType.COMMA)

            if self._match(TokenType.POW):
                self._advance()
                if self._current.type != TokenType.NAME:
                    raise self._error("Expected argument name after **")
                kwarg = self._advance().value
                has_args = True
                if not self._match(TokenType.RPAREN):
                    raise self._error(
                        "**kwargs must be the last parameter",
                        suggestion="Move **kwargs to the end of the parameter list",
                    )
                break

            if self._match(TokenType.MUL):
                self._advance()
                if self._current.type != TokenType.NAME:
                    raise self._error("Expected argument name after *")
                vararg = self._advance().value
                has_args = True
                continue

            if self._current.type != TokenType.NAME:
                raise self._error("Expected argument name")
            param_token = self._current
            arg_name = self._advance().value
            annotation = self._parse_type_annotation()
            params.append(
                DefParam(
                    lineno=param_token.lineno,
                    col_offset=param_token.col_offset,
                    name=arg_name,
                    annotation=annotation,
                )
            )
            has_args = True

            if self._match(TokenType.ASSIGN):
                self._advance()
                defaults.append(self._parse_expression())

        self._expect(TokenType.RPAREN)
        self._expect(TokenType.BLOCK_END)

        body = self._parse_body()
        self._consume_end_tag("region")

        return Region(
            lineno=start.lineno,
            col_offset=start.col_offset,
            name=name,
            params=tuple(params),
            body=tuple(body),
            defaults=tuple(defaults),
            vararg=vararg,
            kwarg=kwarg,
        )

    def _parse_call(self) -> CallBlock:
        """Parse {% call name(args) %}body{% end %} or {% endcall %.

        Call a function/def with body content that fills {% slot %}.
        Supports named slots: {% slot name %}...{% end %} assigns to slot name;
        content outside slot blocks goes to default.

        Example:
            {% call card("My Title") %}
                {% slot header_actions %}<button>⋯</button>{% end %}
                <p>Body content.</p>
            {% end %}
        """
        start = self._advance()  # consume 'call'
        self._push_block("call", start)

        # Parse the call expression
        call_expr = self._parse_expression()
        self._expect(TokenType.BLOCK_END)

        # Parse body into slots (named or default)
        slots = self._parse_call_body()

        # Consume end tag
        self._consume_end_tag("call")

        return CallBlock(
            lineno=start.lineno,
            col_offset=start.col_offset,
            call=call_expr,
            slots=slots,
        )

    def _parse_call_body(self) -> dict[str, Sequence[Node]]:
        """Parse call block body into slots dict.

        When {% slot name %}...{% end %} appears, content goes to slots[name].
        Other content goes to slots["default"].
        """
        slots: dict[str, list[Node]] = {"default": []}

        while self._current.type != TokenType.EOF:
            if self._current.type == TokenType.BLOCK_BEGIN:
                next_tok = self._peek(1)
                if next_tok.type == TokenType.NAME and next_tok.value in self._end_keywords:
                    break
                if (
                    next_tok.type == TokenType.NAME
                    and next_tok.value in self._CONTINUATION_KEYWORDS
                ):
                    break

                result = self._parse_block()
                if result is not None:
                    if isinstance(result, SlotBlock):
                        name = result.name
                        if name not in slots:
                            slots[name] = []
                        slots[name].extend(result.body)
                    elif isinstance(result, list):
                        slots["default"].extend(result)
                    else:
                        slots["default"].append(result)
            elif self._current.type == TokenType.DATA:
                slots["default"].append(self._parse_data())
            elif self._current.type == TokenType.VARIABLE_BEGIN:
                slots["default"].append(self._parse_output())
            elif self._current.type == TokenType.COMMENT_BEGIN:
                self._skip_comment()
            else:
                self._advance()

        return {k: tuple(v) for k, v in slots.items()}

    def _parse_let_bindings(self) -> list[tuple[str, Expr]]:
        """Parse let:name=expr pairs for scoped slot bindings (def-side).

        Grammar::
            let_binding := 'let' ':' NAME '=' expression
            let_bindings := let_binding (',' let_binding)*

        Returns:
            List of (name, expr) tuples.
        """
        bindings: list[tuple[str, Expr]] = []
        while (
            self._current.type == TokenType.NAME
            and self._current.value == "let"
            and self._peek(1).type == TokenType.COLON
        ):
            self._advance()  # consume 'let'
            self._advance()  # consume ':'
            if self._current.type != TokenType.NAME:
                raise self._error(
                    "Expected binding name after 'let:'",
                    suggestion="Scoped slot syntax: {% slot name let:item=expr %}",
                )
            binding_name = self._advance().value
            self._expect(TokenType.ASSIGN)
            expr = self._parse_expression()
            bindings.append((binding_name, expr))
            # Optional comma between bindings
            if self._match(TokenType.COMMA):
                self._advance()
        return bindings

    def _parse_let_params(self) -> list[str]:
        """Parse let:name declarations for scoped slot params (call-site).

        Grammar::
            let_param := 'let' ':' NAME
            let_params := let_param (',' let_param)*

        Returns:
            List of parameter names.
        """
        params: list[str] = []
        while (
            self._current.type == TokenType.NAME
            and self._current.value == "let"
            and self._peek(1).type == TokenType.COLON
        ):
            self._advance()  # consume 'let'
            self._advance()  # consume ':'
            if self._current.type != TokenType.NAME:
                raise self._error(
                    "Expected parameter name after 'let:'",
                    suggestion="Scoped slot syntax: {% slot name let:item, let:index %}",
                )
            params.append(self._advance().value)
            # Optional comma between params
            if self._match(TokenType.COMMA):
                self._advance()
        return params

    def _parse_slot(self) -> Slot | SlotBlock:
        """Parse {% slot %} or {% slot name %} — context-dependent.

        Inside {% call %}: parse {% slot name %}...{% end %} as SlotBlock.
          With scoped params: {% slot name let:item, let:index %}...{% end %}
        Inside {% def %}: parse self-closing {% slot %} or {% slot name %} as Slot.
          With scoped bindings: {% slot name let:item=expr, let:index=loop.index %}
        """
        start = self._advance()  # consume 'slot'

        # Optional slot name (default is "default")
        name = "default"
        if self._current.type == TokenType.NAME and self._current.value != "let":
            name = self._advance().value

        # Inside call block: parse as block with body (+ optional let: params)
        if self._block_stack and self._block_stack[-1][0] == "call":
            params = tuple(self._parse_let_params())
            self._expect(TokenType.BLOCK_END)
            self._push_block("slot", start)
            body = self._parse_body()
            self._consume_end_tag("slot")
            return SlotBlock(
                lineno=start.lineno,
                col_offset=start.col_offset,
                name=name,
                body=tuple(body),
                params=params,
            )

        # Inside def: placeholder with optional let: bindings and optional body.
        # When bindings are present, the slot may have a body for default content:
        #   {% slot row let:item=item %}default {{ item }}{% end %}
        # Without bindings, the slot is self-closing: {% slot %} or {% slot name %}
        bindings = tuple(self._parse_let_bindings())
        self._expect(TokenType.BLOCK_END)

        # Parse optional body (default content) — only when the slot has bindings
        # or when the next token sequence indicates a body before {% end %}
        body: tuple[Node, ...] = ()
        if bindings:
            self._push_block("slot", start)
            body = tuple(self._parse_body())
            self._consume_end_tag("slot")

        return Slot(
            lineno=start.lineno,
            col_offset=start.col_offset,
            name=name,
            bindings=bindings,
            body=body,
        )

    def _parse_yield(self) -> Slot:
        """Parse {% yield %} or {% yield name %} — always a render reference.

        Unlike {% slot %}, which becomes a SlotBlock inside {% call %} blocks,
        {% yield %} always produces a Slot node. This makes it safe to use
        inside nested {% call %} blocks when forwarding the enclosing def's
        caller slots.
        """
        start = self._advance()  # consume 'yield'
        name = "default"
        if self._current.type == TokenType.NAME:
            name = self._advance().value
        self._expect(TokenType.BLOCK_END)
        return Slot(lineno=start.lineno, col_offset=start.col_offset, name=name)
