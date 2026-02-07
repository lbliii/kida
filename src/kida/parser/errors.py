"""Parser error handling for Kida.

Provides ParseError class with rich source context and suggestions.
"""

from __future__ import annotations

from kida._types import Token
from kida.environment.exceptions import TemplateSyntaxError


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
    ):
        self.token = token
        self.source = source
        self.suggestion = suggestion
        self._col_offset = token.col_offset
        # Initialize parent with TemplateSyntaxError signature
        # Note: we override _format_message so the formatted output comes from there
        super().__init__(message, token.lineno, filename, filename)

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
        # Header with location
        location = self.filename or "<template>"
        header = f"Parse Error: {self.message}\n  --> {location}:{self.token.lineno}:{self.token.col_offset}"

        # Source context (if available)
        if self.source:
            lines = self.source.splitlines()
            if 0 < self.token.lineno <= len(lines):
                error_line = lines[self.token.lineno - 1]
                # Create pointer to error location
                pointer = " " * self.token.col_offset + "^"

                # Build the error display
                line_num = self.token.lineno
                msg = f"""
{header}
   |
{line_num:>3} | {error_line}
   | {pointer}"""
            else:
                msg = f"\n{header}"
        else:
            # Fallback without source
            msg = f"\n{header}"

        # Add suggestion if available
        if self.suggestion:
            msg += f"\n\nSuggestion: {self.suggestion}"

        return msg
