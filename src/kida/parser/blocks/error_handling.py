"""Error boundary block parsing for Kida parser.

Provides mixin for parsing {% try %}...{% fallback %}...{% end %} blocks.

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida._types import TokenType
from kida.nodes.control_flow import Try

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kida._types import Token
    from kida.exceptions import ErrorCode
    from kida.nodes import Node
    from kida.parser.errors import ParseError

from kida.parser.blocks.core import BlockStackMixin


class ErrorHandlingBlockParsingMixin(BlockStackMixin):
    """Mixin for parsing error boundary blocks.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.
    """

    if TYPE_CHECKING:
        _tokens: Sequence[Token]
        _pos: int
        _block_stack: list[tuple[str, int, int]]

        @property
        def _current(self) -> Token: ...
        def _advance(self) -> Token: ...
        def _expect(self, token_type: TokenType) -> Token: ...
        def _match(self, *types: TokenType) -> bool: ...
        def _peek(self, offset: int = 0) -> Token: ...
        def _error(
            self,
            message: str,
            token: Token | None = None,
            suggestion: str | None = None,
            code: ErrorCode | None = None,
        ) -> ParseError: ...
        def _parse_body(self, stop_on_continuation: bool = False) -> list[Node]: ...

    def _parse_try(self) -> Try:
        """Parse {% try %}...{% fallback [name] %}...{% end %}.

        Error boundary that catches rendering errors in the body and renders
        fallback content instead. An optional name after {% fallback %} binds
        the caught error as a dict to the fallback scope.

        Example:
            {% try %}
                {{ user.profile.avatar_url }}
            {% fallback error %}
                <div>Error: {{ error.message }}</div>
            {% end %}
        """
        start = self._advance()  # consume 'try'
        self._push_block("try", start)
        self._expect(TokenType.BLOCK_END)

        # Parse try body until {% fallback %}
        body = self._parse_body(stop_on_continuation=True)

        # After _parse_body stops, current token is BLOCK_BEGIN ({%)
        # and peek(1) is the continuation keyword NAME
        if (
            self._current.type != TokenType.BLOCK_BEGIN
            or self._peek(1).type != TokenType.NAME
            or self._peek(1).value != "fallback"
        ):
            raise self._error(
                "Expected {% fallback %} inside {% try %} block",
                suggestion="Add a {% fallback %} section: {% try %}...{% fallback %}...{% end %}",
            )
        self._advance()  # consume BLOCK_BEGIN ({%)
        self._advance()  # consume 'fallback'

        # Optional error name binding
        error_name: str | None = None
        if self._current.type == TokenType.NAME:
            error_name = self._advance().value

        self._expect(TokenType.BLOCK_END)

        # Parse fallback body until {% end %}
        fallback = self._parse_body()

        # Consume end tag
        self._consume_end_tag("try")

        return Try(
            lineno=start.lineno,
            col_offset=start.col_offset,
            body=tuple(body),
            fallback=tuple(fallback),
            error_name=error_name,
        )
