"""Type protocols for parser mixin pattern.

Provides ParserCoreProtocol — a minimal protocol containing only host attributes
and frequently-used cross-mixin methods. Individual mixins declare their own
requirements via TYPE_CHECKING blocks.

This hybrid approach:
1. Reduces protocol maintenance from ~75 signatures to ~16
2. Makes mixins self-documenting (inline declarations show dependencies)
3. Enables IDE autocomplete and compile-time safety
4. Has zero runtime cost (protocols erased at runtime)

See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from kida._types import Token, TokenType

if TYPE_CHECKING:
    from kida.parser.errors import ParseError


class ParserCoreProtocol(Protocol):
    """Minimal contract for cross-mixin dependencies.

    Contains ONLY:
    1. Host class attributes (defined in Parser.__init__)
    2. Token navigation methods (used by all parsing mixins)
    3. Error handling (used everywhere)

    Individual mixin methods are NOT included—mixins declare
    their own cross-mixin dependencies via inline TYPE_CHECKING declarations.

    This protocol is satisfied by the Parser class through structural typing.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host Attributes (from Parser.__init__)
    # ─────────────────────────────────────────────────────────────────────────
    _tokens: Sequence[Token]
    _pos: int
    _name: str | None
    _filename: str | None
    _source: str | None
    _autoescape: bool
    _block_stack: list[tuple[str, int, int]]

    # ─────────────────────────────────────────────────────────────────────────
    # Token Navigation (from TokenNavigationMixin)
    # These are called by ALL other mixins, so they're in the protocol
    # ─────────────────────────────────────────────────────────────────────────
    @property
    def _current(self) -> Token:
        """Get current token."""
        ...

    def _peek(self, offset: int = 0) -> Token:
        """Peek at token at offset from current position."""
        ...

    def _advance(self) -> Token:
        """Advance to next token and return current."""
        ...

    def _expect(self, token_type: TokenType) -> Token:
        """Expect current token to be of given type."""
        ...

    def _match(self, *types: TokenType) -> bool:
        """Check if current token matches any of the types."""
        ...

    def _error(
        self,
        message: str,
        token: Token | None = None,
        suggestion: str | None = None,
    ) -> ParseError:
        """Create a ParseError with source context and block stack info."""
        ...

    def _format_open_blocks(self) -> str:
        """Format the current block stack for error messages."""
        ...
