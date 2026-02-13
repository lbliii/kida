"""Exceptions for Kida template system.

Exception Hierarchy:
TemplateError (base)
├── TemplateNotFoundError     # Template not found by loader
├── TemplateSyntaxError       # Parse-time syntax error
├── TemplateRuntimeError      # Render-time error with context
│   ├── RequiredValueError    # Required value was None/missing
│   └── NoneComparisonError   # Attempted None comparison (sorting)
└── UndefinedError            # Undefined variable access

Error Messages:
All exceptions provide rich error messages with:
- Source location (template name, line number)
- Expression context where error occurred
- Actual values and their types
- Source snippets showing the offending template line
- Actionable suggestions for fixing

Example:
    ```
    UndefinedError: Undefined variable 'titl' in article.html:5
       |
     5 | <h1>{{ titl }}</h1>
       |
    Hint: Did you mean 'title'? Or use {{ titl | default('') }}
    ```

"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from kida.environment import terminal

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

_KIDA_DOCS_BASE = "https://lbliii.github.io/kida/docs/errors"


class ErrorCode(Enum):
    """Searchable error codes for Kida template errors.

    Format: K-{CATEGORY}-{NUMBER}
    Categories: LEX (lexer), PAR (parser), RUN (runtime), TPL (template loading)

    Each code maps to a documentation URL for quick lookup:
        https://lbliii.github.io/kida/docs/errors/#k-run-001

    Example:
        >>> raise UndefinedError("x", code=ErrorCode.UNDEFINED_VARIABLE)
        # Error message includes: Docs: https://lbliii.github.io/kida/docs/errors/#k-run-001
    """

    # Lexer errors (K-LEX-xxx)
    UNCLOSED_TAG = "K-LEX-001"
    UNCLOSED_COMMENT = "K-LEX-002"
    UNCLOSED_VARIABLE = "K-LEX-003"
    TOKEN_LIMIT = "K-LEX-004"

    # Parser errors (K-PAR-xxx)
    UNEXPECTED_TOKEN = "K-PAR-001"
    UNCLOSED_BLOCK = "K-PAR-002"
    INVALID_EXPRESSION = "K-PAR-003"
    INVALID_FILTER = "K-PAR-004"
    INVALID_TEST = "K-PAR-005"

    # Runtime errors (K-RUN-xxx)
    UNDEFINED_VARIABLE = "K-RUN-001"
    FILTER_ERROR = "K-RUN-002"
    TEST_ERROR = "K-RUN-003"
    REQUIRED_VALUE = "K-RUN-004"
    NONE_COMPARISON = "K-RUN-005"
    INCLUDE_DEPTH = "K-RUN-006"
    RUNTIME_ERROR = "K-RUN-007"

    # Template loading errors (K-TPL-xxx)
    TEMPLATE_NOT_FOUND = "K-TPL-001"
    SYNTAX_ERROR = "K-TPL-002"

    @property
    def docs_url(self) -> str:
        """Documentation URL for this error code."""
        anchor = self.value.lower()
        return f"{_KIDA_DOCS_BASE}/#{anchor}"

    @property
    def category(self) -> str:
        """Error category (e.g., 'runtime', 'lexer', 'parser', 'template')."""
        prefix = self.value.split("-")[1]
        return {
            "LEX": "lexer",
            "PAR": "parser",
            "RUN": "runtime",
            "TPL": "template",
        }.get(prefix, "unknown")


# ---------------------------------------------------------------------------
# Source snippets
# ---------------------------------------------------------------------------


def format_template_stack(stack: list[tuple[str, int]] | None) -> str:
    """Format template call stack for error messages with colors.

    Args:
        stack: List of (template_name, line_number) tuples showing include chain

    Returns:
        Formatted stack trace string with colors

    Example:
        >>> stack = [("base.html", 42), ("includes/nav.html", 12)]
        >>> print(format_template_stack(stack))
        Template stack:
          • base.html:42
          • includes/nav.html:12
    """
    if not stack:
        return ""

    lines = [terminal.dim_text("Template stack:")]
    for template_name, line_num in stack:
        location_str = f"{template_name}:{line_num}"
        lines.append(f"  • {terminal.location(location_str)}")
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class SourceSnippet:
    """Template source context around an error line.

    Provides surrounding lines of template source for display in error
    messages. Used by TemplateRuntimeError and UndefinedError to show
    the template line where the error occurred.

    Attributes:
        lines: Tuple of (line_number, line_content) pairs around the error.
        error_line: The 1-based line number where the error occurred.
        column: Optional column offset for caret pointer.
    """

    lines: tuple[tuple[int, str], ...]
    error_line: int
    column: int | None = None

    def format(self) -> str:
        """Format snippet in Rust-inspired diagnostic style with colors.

        Returns a multi-line string with line numbers and the error line
        highlighted. Uses terminal colors when supported.
        """
        parts: list[str] = [terminal.dim_text("   |")]
        for lineno, content in self.lines:
            is_error = lineno == self.error_line
            parts.append(terminal.format_source_line(lineno, content, is_error=is_error))
        if self.column is not None:
            # Caret pointer in bright red
            caret = " " * self.column + "^"
            parts.append(f"{terminal.dim_text('   |')} {terminal.error_line(caret)}")
        parts.append(terminal.dim_text("   |"))
        return "\n".join(parts)


def build_source_snippet(
    source: str,
    error_line: int,
    *,
    context_lines: int = 2,
    column: int | None = None,
) -> SourceSnippet:
    """Build a SourceSnippet from template source.

    Args:
        source: Full template source text.
        error_line: 1-based line number of the error.
        context_lines: Number of lines to show before/after the error line.
        column: Optional column offset for caret pointer.

    Returns:
        SourceSnippet with surrounding context lines.
    """
    all_lines = source.splitlines()
    start = max(0, error_line - 1 - context_lines)
    end = min(len(all_lines), error_line + context_lines)
    lines = tuple((i + 1, all_lines[i]) for i in range(start, end))
    return SourceSnippet(lines=lines, error_line=error_line, column=column)


class TemplateError(Exception):
    """Base exception for all Kida template errors.

    All template-related exceptions inherit from this class, enabling
    broad exception handling:

        >>> try:
        ...     template.render()
        ... except TemplateError as e:
        ...     log.error(f"Template error: {e}")

    Attributes:
        code: Optional ErrorCode for searchable, documentable error identification.
    """

    code: ErrorCode | None = None

    def format_compact(self) -> str:
        """Format error as a structured, human-readable summary.

        Produces a clean diagnostic string suitable for terminal display,
        without Python traceback noise. Consumers (Chirp, Bengal) can call
        this instead of parsing ``str(exc)``.

        Format::

            K-RUN-001: Undefined variable 'usernme' in base.html:42
               |
            >42 | <h1>{{ usernme }}</h1>
               |
            Hint: Use {{ usernme | default('') }} for optional variables
            Docs: https://lbliii.github.io/kida/docs/errors/#k-run-001

        Returns:
            Multi-line string with error code, message, source snippet,
            and documentation URL.
        """
        parts: list[str] = []

        # Header: code + message
        header = str(self)
        if self.code:
            # Prefix with error code if not already in the message
            code_str = self.code.value
            if code_str not in header:
                header = f"{code_str}: {header}"
        parts.append(header)

        # Docs URL
        if self.code:
            parts.append(f"  Docs: {self.code.docs_url}")

        return "\n".join(parts)


class TemplateNotFoundError(TemplateError):
    """Template not found by any configured loader.

    Raised when `Environment.get_template(name)` cannot locate the template
    in any of the loader's search paths.

    Example:
            >>> env.get_template("nonexistent.html")
        TemplateNotFoundError: Template 'nonexistent.html' not found in: templates/

    """

    code: ErrorCode | None = ErrorCode.TEMPLATE_NOT_FOUND



class TemplateSyntaxError(TemplateError):
    """Parse-time syntax error in template source.

    Raised by the Parser when template syntax is invalid. Includes source
    location for error reporting.

    When ``source`` and ``lineno`` are provided, the error message includes
    a source snippet with the offending line.  If ``col_offset`` is also
    given, a caret (``^``) points at the exact column.
    """

    code: ErrorCode | None = ErrorCode.SYNTAX_ERROR

    def __init__(
        self,
        message: str,
        lineno: int | None = None,
        name: str | None = None,
        filename: str | None = None,
        source: str | None = None,
        col_offset: int | None = None,
    ):
        self.message = message
        self.lineno = lineno
        self.name = name
        self.filename = filename
        self.source = source
        self.col_offset = col_offset
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        location = self.filename or self.name or "<template>"
        if self.lineno:
            location += f":{self.lineno}"
            if self.col_offset is not None:
                location += f":{self.col_offset}"

        header = f"Syntax Error: {self.message}\n  --> {location}"

        # Show source snippet when available
        if self.source and self.lineno:
            lines = self.source.splitlines()
            if 0 < self.lineno <= len(lines):
                error_line = lines[self.lineno - 1]
                snippet = f"\n   |\n{self.lineno:>3} | {error_line}"
                if self.col_offset is not None:
                    snippet += f"\n   | {' ' * self.col_offset}^"
                return header + snippet

        return header

    def format_compact(self) -> str:
        """Format syntax error as structured terminal diagnostic."""
        parts: list[str] = []

        # Header: code + message
        code_prefix = f"{self.code.value}: " if self.code else ""
        location = self.filename or self.name or "<template>"
        if self.lineno:
            location += f":{self.lineno}"
        parts.append(f"{code_prefix}{self.message}")
        parts.append(f"  --> {location}")

        # Source snippet
        if self.source and self.lineno:
            lines = self.source.splitlines()
            if 0 < self.lineno <= len(lines):
                error_line = lines[self.lineno - 1]
                parts.append("   |")
                parts.append(f"{self.lineno:>3} | {error_line}")
                if self.col_offset is not None:
                    parts.append(f"   | {' ' * self.col_offset}^")
                parts.append("   |")

        # Docs URL
        if self.code:
            parts.append(f"  Docs: {self.code.docs_url}")

        return "\n".join(parts)


class TemplateRuntimeError(TemplateError):
    """Render-time error with rich debugging context.

    Raised during template rendering when an operation fails. Provides
    detailed information to help diagnose the issue:

    - Template name and line number
    - The expression that caused the error
    - Actual values and their types
    - Actionable suggestion for fixing

    Output Format:
            ```
            Runtime Error: 'NoneType' object has no attribute 'title'
              Location: article.html:15
              Expression: {{ post.title }}
              Values:
                post = None (NoneType)
              Suggestion: Check if 'post' is defined, or use {{ post.title | default('') }}
            ```

    Attributes:
        message: Error description
        expression: Template expression that failed
        values: Dict of variable names → values for context
        template_name: Name of the template
        lineno: Line number in template source
        suggestion: Actionable fix suggestion

    """

    code: ErrorCode | None = ErrorCode.RUNTIME_ERROR

    def __init__(
        self,
        message: str,
        *,
        expression: str | None = None,
        values: dict[str, Any] | None = None,
        template_name: str | None = None,
        lineno: int | None = None,
        suggestion: str | None = None,
        source_snippet: SourceSnippet | None = None,
        template_stack: list[tuple[str, int]] | None = None,
    ):
        self.message = message
        self.expression = expression
        self.values = values or {}
        self.template_name = template_name
        self.lineno = lineno
        self.suggestion = suggestion
        self.source_snippet = source_snippet
        self.template_stack = template_stack or []
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [f"Runtime Error: {self.message}"]

        # Location info
        if self.template_name or self.lineno:
            loc = self.template_name or "<template>"
            if self.lineno:
                loc += f":{self.lineno}"
            parts.append(f"  Location: {terminal.location(loc)}")

        # Source snippet (shows the template line where error occurred)
        if self.source_snippet:
            parts.append(self.source_snippet.format())

        # Template stack trace (Feature 2.1)
        if self.template_stack:
            parts.append("")
            parts.append(format_template_stack(self.template_stack))

        # Expression info
        if self.expression:
            parts.append(f"  Expression: {self.expression}")

        # Values with types
        if self.values:
            parts.append("  Values:")
            for name, value in self.values.items():
                type_name = type(value).__name__
                # Truncate long values
                value_repr = repr(value)
                if len(value_repr) > 80:
                    value_repr = value_repr[:77] + "..."
                parts.append(f"    {name} = {value_repr} ({type_name})")

        # Suggestion
        if self.suggestion:
            parts.append(f"\n  {terminal.hint('Suggestion:')} {self.suggestion}")

        return "\n".join(parts)

    def format_compact(self) -> str:
        """Format runtime error as structured terminal diagnostic."""
        parts: list[str] = []

        # Header: code + message + location
        loc = self.template_name or "<template>"
        if self.lineno:
            loc += f":{self.lineno}"
        parts.append(terminal.format_error_header(
            self.code.value if self.code else None,
            self.message
        ))
        parts.append(f"  Location: {terminal.location(loc)}")

        # Source snippet
        if self.source_snippet:
            parts.append(self.source_snippet.format())

        # Template stack trace (Feature 2.1)
        if self.template_stack:
            parts.append("")
            parts.append(format_template_stack(self.template_stack))

        # Expression
        if self.expression:
            parts.append(f"  Expression: {self.expression}")

        # Suggestion
        if self.suggestion:
            parts.append(f"  {terminal.hint('Hint:')} {self.suggestion}")

        # Docs URL
        if self.code:
            parts.append(f"  {terminal.dim_text('Docs:')} {terminal.docs_url(self.code.docs_url)}")

        return "\n".join(parts)


class RequiredValueError(TemplateRuntimeError):
    """A required value was None or missing.

    Raised by the `| require` filter when a value that must be present is
    None or missing. Useful for validating required context variables.

    Example:
            >>> {{ user.email | require('Email is required for notifications') }}
        RequiredValueError: Email is required for notifications
          Suggestion: Ensure 'email' is set before this point, or use | default(fallback)

    """

    code: ErrorCode | None = ErrorCode.REQUIRED_VALUE

    def __init__(
        self,
        field_name: str,
        message: str | None = None,
        **kwargs: Any,
    ):
        self.field_name = field_name
        msg = message or f"Required value '{field_name}' is None or missing"
        super().__init__(
            msg,
            suggestion=f"Ensure '{field_name}' is set before this point, or use | default(fallback)",
            **kwargs,
        )


class NoneComparisonError(TemplateRuntimeError):
    """Attempted to compare None values, typically during sorting.

    Raised when `| sort` or similar operations encounter None values that
    cannot be compared. Provides information about which items have None
    values for the sort attribute.

    Example:
            >>> {{ posts | sort(attribute='weight') }}
        NoneComparisonError: Cannot compare NoneType with int when sorting by 'weight'

        Items with None/empty values:
          - "Draft Post": weight = None/empty
          - "Untitled": weight = None/empty

        Suggestion: Ensure all items have 'weight' set, or filter out None values first

    """

    code: ErrorCode | None = ErrorCode.NONE_COMPARISON

    def __init__(
        self,
        left_value: Any,
        right_value: Any,
        attribute: str | None = None,
        **kwargs: Any,
    ):
        left_type = type(left_value).__name__
        right_type = type(right_value).__name__

        msg = f"Cannot compare {left_type} with {right_type}"
        if attribute:
            msg += f" when sorting by '{attribute}'"

        values = {
            "left": left_value,
            "right": right_value,
        }

        suggestion = "Use | default(fallback) to provide a fallback for None values before sorting"
        if attribute:
            suggestion = (
                f"Ensure all items have '{attribute}' set, or filter out items with None values"
            )

        super().__init__(
            msg,
            values=values,
            suggestion=suggestion,
            **kwargs,
        )


class UndefinedError(TemplateError):
    """Raised when accessing an undefined variable.

    Strict mode is enabled by default in Kida. When a template references
    a variable that doesn't exist in the context, this error is raised
    instead of silently returning None.

    If ``available_names`` is provided, a "Did you mean?" suggestion is
    included when a close match is found (using ``difflib.get_close_matches``).

    Example:
            >>> env = Environment()
            >>> env.from_string("{{ undefined_var }}").render()
        UndefinedError: Undefined variable 'undefined_var' in <template>:1

    To fix:
        - Pass the variable in render(): template.render(undefined_var="value")
        - Use the default filter: {{ undefined_var | default("fallback") }}

    """

    code: ErrorCode | None = ErrorCode.UNDEFINED_VARIABLE

    def __init__(
        self,
        name: str,
        template: str | None = None,
        lineno: int | None = None,
        available_names: frozenset[str] | None = None,
        source_snippet: SourceSnippet | None = None,
        template_stack: list[tuple[str, int]] | None = None,
    ):
        self.name = name
        self.template = template or "<template>"
        self.lineno = lineno
        self._available_names = available_names
        self.source_snippet = source_snippet
        self.template_stack = template_stack or []
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        location = self.template
        if self.lineno:
            location += f":{self.lineno}"
        msg = f"Undefined variable '{self.name}' in {terminal.location(location)}"

        # "Did you mean?" suggestion via fuzzy matching
        if self._available_names:
            from difflib import get_close_matches

            matches = get_close_matches(
                self.name, self._available_names, n=1, cutoff=0.6
            )
            if matches:
                suggested = terminal.suggestion(matches[0])
                msg += f". Did you mean '{suggested}'?"

        # Source snippet (shows the template line where error occurred)
        if self.source_snippet:
            msg += "\n" + self.source_snippet.format()

        # Template stack trace (Feature 2.1)
        if self.template_stack:
            msg += "\n\n" + format_template_stack(self.template_stack)

        hint_text = f"Use {{{{ {self.name} | default('') }}}} for optional variables"
        msg += f"\n  {terminal.hint('Hint:')} {hint_text}"
        return msg

    def format_compact(self) -> str:
        """Format undefined variable error as structured terminal diagnostic."""
        parts: list[str] = []

        # Header: code + message
        location = self.template
        if self.lineno:
            location += f":{self.lineno}"
        msg = terminal.format_error_header(
            self.code.value if self.code else None,
            f"Undefined variable '{self.name}' in {terminal.location(location)}"
        )

        # "Did you mean?" suggestion
        if self._available_names:
            from difflib import get_close_matches

            matches = get_close_matches(
                self.name, self._available_names, n=1, cutoff=0.6
            )
            if matches:
                suggested = terminal.suggestion(matches[0])
                msg += f". Did you mean '{suggested}'?"
        parts.append(msg)

        # Source snippet
        if self.source_snippet:
            parts.append(self.source_snippet.format())

        # Template stack trace (Feature 2.1)
        if self.template_stack:
            parts.append("")
            parts.append(format_template_stack(self.template_stack))

        # Hint
        hint_text = f"Use {{{{ {self.name} | default('') }}}} for optional variables"
        parts.append(f"  {terminal.hint('Hint:')} {hint_text}")

        # Docs URL
        if self.code:
            parts.append(f"  {terminal.dim_text('Docs:')} {terminal.docs_url(self.code.docs_url)}")

        return "\n".join(parts)
