"""Parser error handling for Kida.

Provides ParseError class with rich source context and suggestions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida.exceptions import ErrorCode, TemplateSyntaxError
from kida.tstring import plain as _plain

if TYPE_CHECKING:
    from kida._types import Token


class ParseError(TemplateSyntaxError):
    """Parser error with rich source context.

    Inherits from TemplateSyntaxError to ensure consistent exception handling.
    Displays errors with source code snippets and visual pointers,
    matching the format used by the lexer for consistency.

    """

    def __init__(
        self,
        message: str,
        token: Token,
        source: str | None = None,
        filename: str | None = None,
        suggestion: str | None = None,
        code: ErrorCode | None = None,
    ):
        self.token = token
        self.suggestion = suggestion
        self._col_offset = token.col_offset
        self.code = code if code is not None else ErrorCode.UNEXPECTED_TOKEN
        # Initialize parent with TemplateSyntaxError signature
        # Note: we override _format_message so the formatted output comes from there
        super().__init__(message, token.lineno, filename, filename)
        # Set source AFTER super().__init__() — parent sets self.source = None
        # when source is not passed, which clobbers our value.
        self.source = source

    def _format_message(self) -> str:
        """Override parent's formatting with rich source context."""
        return self._format()

    @property
    def col_offset(self) -> int:
        """Column offset where the error occurred (0-based)."""
        return self._col_offset

    @col_offset.setter
    def col_offset(self, value: int | None) -> None:
        """Allow parent __init__ to set col_offset without clobbering token value."""
        if value is not None:
            self._col_offset = value

    def _format(self) -> str:
        """Format error with source context like Rust/modern compilers."""
        # Header with Kida branding and error code
        location = self.filename or "<template>"
        code_str = self.code.value if self.code else "K-PAR-001"
        message = self.message
        lineno = self.token.lineno
        col_offset = self.token.col_offset
        header = _plain(
            t"Kida Parse Error [{code_str}]: {message}\n  --> {location}:{lineno}:{col_offset}"
        )

        # Source context (if available)
        if self.source:
            lines = self.source.splitlines()
            if 0 < lineno <= len(lines):
                error_line = lines[lineno - 1]
                # Create pointer to error location
                pointer = " " * col_offset + "^"

                # Build the error display
                msg = _plain(t"\n{header}\n   |\n{lineno:>3} | {error_line}\n   | {pointer}")
            else:
                msg = _plain(t"\n{header}")
        else:
            # Fallback without source
            msg = _plain(t"\n{header}")

        # Add suggestion if available
        if self.suggestion:
            suggestion = self.suggestion
            msg += _plain(t"\n\nSuggestion: {suggestion}")

        # Add docs URL
        if self.code:
            docs_url = self.code.docs_url
            msg += _plain(t"\n\nDocs: {docs_url}")

        return msg
