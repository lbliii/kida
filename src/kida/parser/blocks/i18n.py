"""i18n block parsing for Kida parser.

Provides mixin for parsing {% trans %} blocks with variable bindings,
pluralization via {% plural %}, and message ID extraction.

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida._types import TokenType
from kida.nodes.structure import Trans, TransVar

if TYPE_CHECKING:
    from kida._types import Token
    from kida.exceptions import ErrorCode
    from kida.nodes.expressions import Expr
    from kida.parser.errors import ParseError

from kida.parser.blocks.core import BlockStackMixin


class I18nParsingMixin(BlockStackMixin):
    """Mixin for parsing {% trans %}...{% endtrans %} blocks.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.
    """

    if TYPE_CHECKING:
        _tokens: list[Token]
        _pos: int
        _block_stack: list[tuple[str, int, int]]

        @property
        def _current(self) -> Token: ...
        def _advance(self) -> Token: ...
        def _expect(self, token_type: TokenType) -> Token: ...
        def _match(self, *types: TokenType) -> bool: ...
        def _peek(self, offset: int = 0) -> Token: ...
        def _parse_expression(self) -> Expr: ...
        def _error(
            self,
            message: str,
            token: Token | None = None,
            suggestion: str | None = None,
            code: ErrorCode | None = None,
        ) -> ParseError: ...

    def _parse_trans(self) -> Trans:
        """Parse {% trans [var=expr, ...] %}...{% endtrans %}.

        Syntax:
            {% trans %}literal body{% endtrans %}
            {% trans name=expr %}Hello, {{ name }}!{% endtrans %}
            {% trans count=expr %}One item.{% plural %}{{ count }} items.{% endtrans %}

        Body restrictions:
            - Only {{ name }} references allowed (simple names)
            - No filters, attribute access, or method calls
            - All referenced names must be declared in the {% trans %} tag
        """
        start = self._advance()  # consume 'trans'

        # Parse variable bindings: name=expr, name=expr
        variables: list[TransVar] = []
        count_expr: Expr | None = None

        while self._current.type == TokenType.NAME and self._peek(1).type == TokenType.ASSIGN:
            var_start = self._current
            var_name = self._advance().value
            self._advance()  # consume '='
            var_expr = self._parse_expression()
            var_node = TransVar(
                lineno=var_start.lineno,
                col_offset=var_start.col_offset,
                name=var_name,
                expr=var_expr,
            )
            variables.append(var_node)
            if var_name == "count":
                count_expr = var_expr
            # Consume optional comma between bindings
            if self._match(TokenType.COMMA):
                self._advance()

        self._expect(TokenType.BLOCK_END)

        # Collect declared variable names for validation
        declared_names = {v.name for v in variables}

        # Parse body: collect text and {{ name }} references
        singular_parts, plural_parts, has_plural = self._parse_trans_body(declared_names)

        singular = self._normalize_message("".join(singular_parts))
        plural_str: str | None = None
        if has_plural:
            plural_str = self._normalize_message("".join(plural_parts))
            if count_expr is None:
                raise self._error(
                    "{% plural %} requires a 'count' variable in {% trans %}",
                    suggestion="Add count=expr to the {% trans %} tag: "
                    "{% trans count=items|length %}",
                )

        return Trans(
            lineno=start.lineno,
            col_offset=start.col_offset,
            singular=singular,
            plural=plural_str,
            variables=tuple(variables),
            count_expr=count_expr,
        )

    def _parse_trans_body(self, declared_names: set[str]) -> tuple[list[str], list[str], bool]:
        """Parse trans block body, returning singular parts, plural parts, and has_plural flag."""
        singular_parts: list[str] = []
        plural_parts: list[str] = []
        current_parts = singular_parts
        has_plural = False

        while True:
            if self._current.type == TokenType.DATA:
                current_parts.append(self._advance().value)

            elif self._current.type == TokenType.VARIABLE_BEGIN:
                self._advance()  # consume {{
                if self._current.type != TokenType.NAME:
                    raise self._error(
                        "Only simple variable names allowed inside {% trans %} body",
                        suggestion="Use variable bindings: "
                        "{% trans name=user.name %}{{ name }}{% endtrans %}",
                    )
                ref_name = self._advance().value
                if ref_name not in declared_names:
                    raise self._error(
                        f"Undeclared variable '{ref_name}' in {{% trans %}} body",
                        suggestion=f"Add {ref_name}=expr to the {{% trans %}} tag",
                    )
                # Check for filters or attribute access (forbidden)
                if self._current.type != TokenType.VARIABLE_END:
                    raise self._error(
                        f"Complex expressions not allowed inside {{% trans %}} body "
                        f"(found {self._current.type} after '{ref_name}')",
                        suggestion=f"Bind the expression in the tag: "
                        f"{{% trans {ref_name}=your_expr %}}{{{{ {ref_name} }}}}"
                        f"{{% endtrans %}}",
                    )
                self._expect(TokenType.VARIABLE_END)
                current_parts.append(f"%({ref_name})s")

            elif self._current.type == TokenType.BLOCK_BEGIN:
                self._advance()  # consume {%
                if self._current.type != TokenType.NAME:
                    raise self._error("Expected block keyword inside {% trans %} body")
                keyword = self._current.value
                if keyword in ("endtrans", "end"):
                    self._advance()  # consume keyword
                    self._expect(TokenType.BLOCK_END)
                    break
                elif keyword == "plural":
                    if has_plural:
                        raise self._error("Duplicate {% plural %} in {% trans %} block")
                    self._advance()  # consume 'plural'
                    self._expect(TokenType.BLOCK_END)
                    has_plural = True
                    current_parts = plural_parts
                else:
                    raise self._error(
                        f"Unexpected block tag '{keyword}' inside {{% trans %}}",
                        suggestion="Only {% plural %} and {% endtrans %} "
                        "are allowed inside {% trans %}",
                    )

            elif self._current.type == TokenType.EOF:
                raise self._error(
                    "Unexpected end of template inside {% trans %} block",
                    suggestion="Add {% endtrans %} to close the block",
                )
            else:
                raise self._error(
                    f"Unexpected token {self._current.type} inside {{% trans %}} body"
                )

        return singular_parts, plural_parts, has_plural

    @staticmethod
    def _normalize_message(msg: str) -> str:
        """Normalize whitespace in a message ID.

        Strips leading/trailing whitespace and collapses internal
        whitespace to single spaces. This ensures consistent message
        IDs regardless of template formatting.
        """
        return " ".join(msg.split())
