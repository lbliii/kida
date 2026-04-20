"""Parser error handling for Kida.

Provides ParseError class with rich source context and suggestions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida.exceptions import ErrorCode, TemplateSyntaxError

if TYPE_CHECKING:
    from kida._types import Token


JINJA2_TRAPS: dict[str, str] = {
    "macro": "Kida uses {% def %} for macros — {% def name(...) %}...{% end %} (supports caller() and named slots).",
    "endmacro": "Kida uses unified {% end %} for all blocks — {% def ... %}...{% end %}.",
    "namespace": "Kida has no namespace() — use {% let %} at template scope, or {% export x = ... %} to write to outer scope from inside a block.",
    "endset": "Kida uses unified {% end %} for block-capture. Prefer {% capture x %}...{% end %} or {% let x %}...{% end %}.",
    "fill": "Kida has no {% fill %} tag — use {% slot name %}...{% end %} inside a {% call %} block.",
    "endfill": "Kida has no {% fill %}/{% endfill %} — use {% slot name %}...{% end %} inside a {% call %} block.",
}


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
        # Restore source after parent initialization, then rebuild the stored
        # exception message so str(ParseError) includes source context.
        self.source = source
        self.args = (self._format_message(),)

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
        header = (
            f"Kida Parse Error [{code_str}]: {self.message}\n"
            f"  --> {location}:{self.token.lineno}:{self.token.col_offset}"
        )

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

        # Add docs URL
        if self.code:
            msg += f"\n\nDocs: {self.code.docs_url}"

        return msg
