"""Exceptions for Kida template system.

Standalone module with zero internal imports at module level,
breaking the deepest circular import chain (environment → exceptions → environment).

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
from html import escape as html_escape
from typing import Any, final


def _terminal():
    """Lazy import of terminal color utilities (avoids circular imports)."""
    from kida.environment import terminal

    return terminal


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

_KIDA_DOCS_BASE = "https://lbliii.github.io/kida/docs/errors"


class ErrorCode(Enum):
    """Searchable error codes for Kida diagnostics.

    Format: K-{CATEGORY}-{NUMBER}. Categories cover lexer/parser/runtime
    failures plus component, warning, safety, and static-analysis findings.

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
    INVALID_IDENTIFIER = "K-PAR-006"

    # Runtime errors (K-RUN-xxx)
    UNDEFINED_VARIABLE = "K-RUN-001"
    FILTER_ERROR = "K-RUN-002"
    TEST_ERROR = "K-RUN-003"
    REQUIRED_VALUE = "K-RUN-004"
    NONE_COMPARISON = "K-RUN-005"
    INCLUDE_DEPTH = "K-RUN-006"
    RUNTIME_ERROR = "K-RUN-007"
    MACRO_NOT_FOUND = "K-RUN-008"
    KEY_ERROR = "K-RUN-009"
    ATTRIBUTE_ERROR = "K-RUN-010"
    ZERO_DIVISION = "K-RUN-011"
    TYPE_ERROR = "K-RUN-012"
    MACRO_ITERATION = "K-RUN-013"

    # Template loading errors (K-TPL-xxx)
    TEMPLATE_NOT_FOUND = "K-TPL-001"
    SYNTAX_ERROR = "K-TPL-002"
    CIRCULAR_IMPORT = "K-TPL-003"
    DEFINITION_NOT_TOPLEVEL = "K-TPL-004"
    TEMPLATE_ROOT_CONFIGURATION = "K-TPL-005"

    # Security errors (K-SEC-xxx)
    BLOCKED_ATTRIBUTE = "K-SEC-001"
    BLOCKED_TYPE = "K-SEC-002"
    RANGE_LIMIT = "K-SEC-003"
    BLOCKED_CALLABLE = "K-SEC-004"
    OUTPUT_LIMIT = "K-SEC-005"

    # Component validation errors/warnings (K-CMP-xxx)
    COMPONENT_CALL_SIGNATURE = "K-CMP-001"
    COMPONENT_TYPE_MISMATCH = "K-CMP-002"

    # Extended runtime errors (K-RUN-xxx continued)
    ENV_GARBAGE_COLLECTED = "K-RUN-014"
    NOT_COMPILED = "K-RUN-015"
    NO_LOADER = "K-RUN-016"
    NOT_IN_RENDER_CONTEXT = "K-RUN-017"

    # Extended parser errors (K-PAR-xxx continued)
    UNSUPPORTED_SYNTAX = "K-PAR-007"

    # Warnings (K-WARN-xxx) — used with TemplateWarning, not exceptions
    FILTER_PRECEDENCE = "K-WARN-001"
    JINJA2_SET_SCOPING = "K-WARN-002"

    # Static analysis findings (K-{DOMAIN}-xxx)
    PRIVACY_SENSITIVE_CONTEXT = "K-PRI-001"
    PRIVACY_SECRET_LITERAL = "K-PRI-002"
    PRIVACY_SAFE_SENSITIVE_VALUE = "K-PRI-003"
    PRIVACY_BROAD_CONTEXT_OUTPUT = "K-PRI-004"
    PRIVACY_DYNAMIC_TEMPLATE_NAME = "K-PRI-005"
    CONTEXT_MISSING = "K-CTX-001"
    CONTEXT_UNUSED = "K-CTX-002"
    ESCAPE_ESCAPED_OUTPUT = "K-ESC-001"
    ESCAPE_TRUSTED_MARKUP = "K-ESC-002"
    ESCAPE_UNESCAPED_OUTPUT = "K-ESC-003"
    ESCAPE_TRUSTED_JSON = "K-ESC-004"
    ESCAPE_TRUSTED_XMLATTR = "K-ESC-005"
    A11Y_IMG_ALT = "K-A11Y-001"
    A11Y_HEADING_ORDER = "K-A11Y-002"
    A11Y_HTML_LANG = "K-A11Y-003"
    A11Y_INPUT_LABEL = "K-A11Y-004"
    TYPE_UNDECLARED_VARIABLE = "K-TYP-001"
    TYPE_UNUSED_DECLARATION = "K-TYP-002"
    TYPE_TYPO_SUGGESTION = "K-TYP-003"
    FRAGILE_TEMPLATE_PATH = "K-PATH-001"
    MODULARITY_EXTRACTION_CANDIDATE = "K-MOD-102"
    MODULARITY_PASS_THROUGH_COMPONENT = "K-MOD-103"

    @property
    def docs_url(self) -> str:
        """Documentation URL for this error code."""
        anchor = self.value.lower()
        return f"{_KIDA_DOCS_BASE}/#{anchor}"

    @property
    def category(self) -> str:
        """Error category (e.g., 'runtime', 'lexer', 'parser', 'template', 'security')."""
        prefix = self.value.split("-")[1]
        return {
            "LEX": "lexer",
            "PAR": "parser",
            "RUN": "runtime",
            "TPL": "template",
            "SEC": "security",
            "CMP": "component",
            "WARN": "warning",
            "PRI": "privacy",
            "CTX": "context",
            "ESC": "escape",
            "A11Y": "accessibility",
            "TYP": "type",
            "PATH": "path",
            "MOD": "modularity",
        }.get(prefix, "unknown")


# ---------------------------------------------------------------------------
# Compile-time warnings
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TemplateWarning:
    """Compile-time template warning (not an exception)."""

    code: ErrorCode
    message: str
    template_name: str | None = None
    lineno: int | None = None
    suggestion: str | None = None

    def format_message(self) -> str:
        """Format warning for display."""
        parts = []
        loc = ""
        if self.template_name:
            loc += self.template_name
        if self.lineno:
            loc += f":{self.lineno}"
        if loc:
            parts.append(f"[{self.code.value}] {self.message} ({loc})")
        else:
            parts.append(f"[{self.code.value}] {self.message}")
        if self.suggestion:
            parts.append(f"  Hint: {self.suggestion}")
        return "\n".join(parts)


class KidaWarning(UserWarning):
    """Base warning category for Kida template warnings."""


class PrecedenceWarning(KidaWarning):
    """Operator precedence may cause unexpected results."""


class CoercionWarning(KidaWarning):
    """Implicit type coercion in filter."""


class MigrationWarning(KidaWarning):
    """Jinja2 migration: behavior differs from Jinja2."""


class ComponentWarning(KidaWarning):
    """Component contract validation warning."""


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

    terminal = _terminal()
    lines = [terminal.dim_text("Template stack:")]
    for template_name, line_num in stack:
        location_str = f"{template_name}:{line_num}"
        lines.append(f"  • {terminal.location(location_str)}")
    return "\n".join(lines)


def format_component_stack(stack: list[tuple[str, int, str]] | None) -> str:
    """Format component call stack for error messages with colors.

    Args:
        stack: List of (template_name, line_number, def_name) tuples
            showing the def call chain.

    Returns:
        Formatted component stack trace string with colors.

    Example:
        >>> stack = [("page.html", 14, "dashboard"), ("components/card.html", 3, "card")]
        >>> print(format_component_stack(stack))
        Component stack:
          • page.html:14 → dashboard()
          • components/card.html:3 → card()
    """
    if not stack:
        return ""

    terminal = _terminal()
    lines = [terminal.dim_text("Component stack:")]
    for template_name, line_num, def_name in stack:
        location_str = f"{template_name}:{line_num}" if template_name else f"<template>:{line_num}"
        lines.append(f"  • {terminal.location(location_str)} → {def_name}()")
    return "\n".join(lines)


@final
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
        terminal = _terminal()
        parts: list[str] = [terminal.dim_text("   |")]
        for lineno, content in self.lines:
            is_error = lineno == self.error_line
            parts.append(terminal.format_source_line(lineno, content, is_error=is_error))
        if self.column is not None:
            caret = " " * self.column + "^"
            parts.append(f"{terminal.dim_text('   |')} {terminal.error_line(caret)}")
        parts.append(terminal.dim_text("   |"))
        return "\n".join(parts)


@final
@dataclass(frozen=True, slots=True)
class DiagnosticLocation:
    """Surface-neutral template location for exception renderers."""

    template: str
    line: int | None = None
    column: int | None = None
    filename: str | None = None

    def format(self) -> str:
        """Return ``template[:line[:column]]`` without terminal styling."""
        location = self.template
        if self.line:
            location += f":{self.line}"
            if self.column is not None:
                location += f":{self.column}"
        return location


@final
@dataclass(frozen=True, slots=True)
class DiagnosticFrame:
    """Surface-neutral stack frame for template/component diagnostics."""

    template: str
    line: int
    name: str | None = None

    def format(self) -> str:
        """Return a plain frame label."""
        location = f"{self.template}:{self.line}"
        if self.name:
            return f"{location} -> {self.name}()"
        return location


@final
@dataclass(frozen=True, slots=True)
class TemplateDiagnostic:
    """Structured diagnostic data for downstream renderers.

    This payload intentionally stores plain strings and immutable tuples only.
    HTML, markdown, and terminal escaping/styling belongs to the renderer that
    consumes it.
    """

    code: str | None
    title: str
    message: str
    kind: str
    location: DiagnosticLocation
    source_snippet: SourceSnippet | None = None
    hints: tuple[str, ...] = ()
    docs_url: str | None = None
    suggestion: str | None = None
    template_stack: tuple[DiagnosticFrame, ...] = ()
    component_stack: tuple[DiagnosticFrame, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def metadata_dict(self) -> dict[str, str]:
        """Return metadata as a regular dict for consumers that prefer mapping APIs."""
        return dict(self.metadata)

    def format_html_fragment(self) -> str:
        """Render a dependency-free escaped HTML diagnostic fragment.

        This is intentionally compact and unstyled so framework debug pages can
        wrap it in their own chrome without inheriting terminal formatting.
        """

        code = (
            f'<span class="kida-error-code">{html_escape(self.code)}</span> ' if self.code else ""
        )
        parts = [
            '<section class="kida-diagnostic" data-kida-diagnostic="true">',
            f"<h1>{code}{html_escape(self.title)}</h1>",
            f'<p class="kida-diagnostic-message">{html_escape(self.message)}</p>',
            '<dl class="kida-diagnostic-facts">',
            f"<dt>Location</dt><dd>{html_escape(self.location.format())}</dd>",
        ]
        if self.suggestion:
            parts.append(f"<dt>Suggestion</dt><dd>{html_escape(self.suggestion)}</dd>")
        parts.append("</dl>")

        if self.source_snippet:
            parts.append('<pre class="kida-source-snippet"><code>')
            for lineno, content in self.source_snippet.lines:
                marker = ">" if lineno == self.source_snippet.error_line else " "
                parts.append(f"{marker}{lineno:4} | {html_escape(content)}\n")
            if self.source_snippet.column is not None:
                caret = " " * self.source_snippet.column + "^"
                parts.append(f"     | {html_escape(caret)}\n")
            parts.append("</code></pre>")

        if self.hints:
            parts.append('<ol class="kida-diagnostic-hints">')
            parts.extend(f"<li>{html_escape(hint)}</li>" for hint in self.hints)
            parts.append("</ol>")

        if self.component_stack:
            parts.append("<h2>Component stack</h2><ol>")
            parts.extend(
                f"<li>{html_escape(frame.format())}</li>" for frame in self.component_stack
            )
            parts.append("</ol>")
        if self.template_stack:
            parts.append("<h2>Template stack</h2><ol>")
            parts.extend(f"<li>{html_escape(frame.format())}</li>" for frame in self.template_stack)
            parts.append("</ol>")
        if self.docs_url:
            parts.append(
                f'<p class="kida-diagnostic-docs"><a href="{html_escape(self.docs_url)}">'
                "Documentation</a></p>"
            )
        parts.append("</section>")
        return "".join(parts)

    def format_html_page(self, *, page_title: str = "Kida Template Error") -> str:
        """Render a standalone escaped HTML diagnostic page."""
        summary_items = [
            ("Error", self.title),
            ("Location", self.location.format()),
        ]
        if self.suggestion:
            summary_items.append(("Closest name", self.suggestion))
        summary_items.extend((key.replace("_", " ").title(), value) for key, value in self.metadata)

        summary = "".join(
            "<div><dt>" + html_escape(label) + "</dt><dd>" + html_escape(value) + "</dd></div>"
            for label, value in summary_items
        )
        primary_hint = self.hints[0] if self.hints else "Inspect the template location above."
        css = "".join(
            [
                "*{box-sizing:border-box}",
                "body{margin:0;background:#10141f;color:#d8dee9;",
                "font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}",
                ".wrap{max-width:1120px;margin:0 auto;padding:32px}",
                ".hero{border:1px solid #384258;background:#171d2b;border-radius:8px;padding:20px}",
                ".code{color:#ff7b93;font-weight:700}",
                ".message{color:#f2cc8f;margin:12px 0 0;white-space:pre-wrap}",
                ".fix{margin-top:16px;padding:12px 14px;background:#10291d;",
                "border:1px solid #2d6a4f;border-radius:6px;color:#b7f7c9}",
                ".facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));",
                "gap:10px;margin:18px 0 0}",
                ".facts div{border:1px solid #30394d;border-radius:6px;",
                "padding:10px;background:#111827}",
                ".facts dt{color:#8ea4c8;font-size:12px;text-transform:uppercase}",
                ".facts dd{margin:4px 0 0;word-break:break-word}",
                ".panel{margin-top:20px;border:1px solid #30394d;border-radius:8px;",
                "background:#121827;overflow:hidden}",
                ".panel h2{font-size:14px;margin:0;padding:10px 14px;",
                "background:#192235;color:#9cc4ff}",
                ".panel pre{margin:0;padding:14px;overflow:auto}",
                ".panel ol{margin:0;padding:12px 14px 12px 34px}",
                ".panel li{margin:4px 0}",
                ".docs a{color:#9cc4ff}",
                ".trace-note{color:#8ea4c8;margin-top:18px}",
            ]
        )
        parts = [
            "<!doctype html>",
            '<html lang="en"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{html_escape(page_title)}</title>",
            f'<style>{css}</style></head><body><main class="wrap">',
            '<section class="hero">',
            f'<div class="code">{html_escape(self.code or "Kida")}</div>',
            f"<h1>{html_escape(self.title)}</h1>",
            f'<p class="message">{html_escape(self.message)}</p>',
            f'<div class="fix"><strong>First fix:</strong> {html_escape(primary_hint)}</div>',
            f'<dl class="facts">{summary}</dl>',
            "</section>",
        ]
        if self.source_snippet:
            parts.append('<section class="panel"><h2>Template Source</h2><pre><code>')
            for lineno, content in self.source_snippet.lines:
                marker = ">" if lineno == self.source_snippet.error_line else " "
                parts.append(f"{marker}{lineno:4} | {html_escape(content)}\n")
            if self.source_snippet.column is not None:
                caret = " " * self.source_snippet.column + "^"
                parts.append(f"     | {html_escape(caret)}\n")
            parts.append("</code></pre></section>")
        if len(self.hints) > 1:
            parts.append('<section class="panel"><h2>Other Fix Options</h2><ol>')
            parts.extend(f"<li>{html_escape(hint)}</li>" for hint in self.hints[1:])
            parts.append("</ol></section>")
        if self.component_stack:
            parts.append('<section class="panel"><h2>Component Path</h2><ol>')
            parts.extend(
                f"<li>{html_escape(frame.format())}</li>" for frame in self.component_stack
            )
            parts.append("</ol></section>")
        if self.template_stack:
            parts.append('<section class="panel"><h2>Template Path</h2><ol>')
            parts.extend(f"<li>{html_escape(frame.format())}</li>" for frame in self.template_stack)
            parts.append("</ol></section>")
        parts.append(
            '<p class="trace-note">Python traceback frames are secondary for Kida template errors; '
            "the template location above is authoritative.</p>"
        )
        if self.docs_url:
            parts.append(
                f'<p class="docs"><a href="{html_escape(self.docs_url)}">Kida error documentation</a></p>'
            )
        parts.append("</main></body></html>")
        return "".join(parts)

    def format_markdown(self) -> str:
        """Render a GitHub-flavored Markdown diagnostic from plain fields."""
        from kida.utils.markdown_escape import markdown_escape

        heading = f"### {markdown_escape(self.code)}: {markdown_escape(self.title)}"
        if not self.code:
            heading = f"### {markdown_escape(self.title)}"
        parts = [
            heading,
            "",
            markdown_escape(self.message),
            "",
            f"**Location:** `{markdown_escape(self.location.format())}`",
        ]
        if self.source_snippet:
            parts.extend(["", "```text"])
            for lineno, content in self.source_snippet.lines:
                marker = ">" if lineno == self.source_snippet.error_line else " "
                parts.append(f"{marker}{lineno:4} | {content}")
            if self.source_snippet.column is not None:
                caret = " " * self.source_snippet.column + "^"
                parts.append(f"     | {caret}")
            parts.append("```")
        if self.hints:
            parts.extend(["", "**Hints:**"])
            parts.extend(f"- {markdown_escape(hint)}" for hint in self.hints)
        if self.component_stack:
            parts.extend(["", "**Component stack:**"])
            parts.extend(f"- `{markdown_escape(frame.format())}`" for frame in self.component_stack)
        if self.template_stack:
            parts.extend(["", "**Template stack:**"])
            parts.extend(f"- `{markdown_escape(frame.format())}`" for frame in self.template_stack)
        if self.docs_url:
            parts.extend(["", f"[Documentation]({self.docs_url})"])
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

        code_str = f" [{self.code.value}]" if self.code else ""
        header = f"Kida Syntax Error{code_str}: {self.message}\n  --> {location}"

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

        # Header: Kida prefix + code + message
        code_prefix = f"{self.code.value}: " if self.code else ""
        kida_prefix = "Kida " if self.code else ""
        location = self.filename or self.name or "<template>"
        if self.lineno:
            location += f":{self.lineno}"
        parts.append(f"{kida_prefix}{code_prefix}{self.message}")
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
        component_stack: list[tuple[str, int, str]] | None = None,
        code: ErrorCode | None = None,
    ):
        self.message = message
        self.expression = expression
        self.values = values or {}
        self.template_name = template_name
        self.lineno = lineno
        self.suggestion = suggestion
        self.source_snippet = source_snippet
        self.template_stack = template_stack or []
        self.component_stack = component_stack or []
        self.code = code if code is not None else ErrorCode.RUNTIME_ERROR
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        terminal = _terminal()
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

        # Component stack trace (Sprint 1.3: Component Framework)
        if self.component_stack:
            parts.append("")
            parts.append(format_component_stack(self.component_stack))

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
        terminal = _terminal()
        parts: list[str] = []

        # Header: code + message + location
        loc = self.template_name or "<template>"
        if self.lineno:
            loc += f":{self.lineno}"
        parts.append(
            terminal.format_error_header(self.code.value if self.code else None, self.message)
        )
        parts.append(f"  Location: {terminal.location(loc)}")

        # Source snippet
        if self.source_snippet:
            parts.append(self.source_snippet.format())

        # Component stack trace (Sprint 1.3)
        if self.component_stack:
            parts.append("")
            parts.append(format_component_stack(self.component_stack))

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
        component_stack: list[tuple[str, int, str]] | None = None,
        kind: str = "variable",
        declared_definitions: frozenset[str] | None = None,
    ):
        self.name = name
        self.template = template or "<template>"
        self.lineno = lineno
        self.available_names = frozenset(available_names or ())
        self._available_names = self.available_names or None
        self.source_snippet = source_snippet
        self.template_stack = list(template_stack or [])
        self.component_stack = list(component_stack or [])
        self.kind = kind
        self._kind = kind
        # Top-level {% def %} / {% region %} names declared by the current
        # template. When ``self.name`` is one of these, the error swaps the
        # generic ``| default('')`` hint for a directed message pointing the
        # user at the missing top-level declaration. See _hint_text().
        self.declared_definitions = frozenset(declared_definitions or ())
        self._declared_definitions = self.declared_definitions
        self.suggestion = self._closest_available_name()
        super().__init__(self._format_message())

    def _closest_available_name(self) -> str | None:
        """Return the best fuzzy match from available names, if any."""
        if not self._available_names:
            return None
        from difflib import get_close_matches

        matches = get_close_matches(self.name, list(self._available_names), n=1, cutoff=0.6)
        return matches[0] if matches else None

    def _hint_text(self) -> str:
        """Return the hint line shown after the error message.

        When the missing name matches a known top-level definition, point
        the user at the declaration site instead of suggesting ``default``,
        because no default value will work — the name is meant to resolve
        to a {% region %} or {% def %} that is not yet bound at this point
        in the render (typically because it is declared but unreachable
        at module-init time, or render_block was called for the wrong
        block).
        """
        if self.name in self._declared_definitions:
            return (
                f"Did you declare {{% region {self.name} %}} (or {{% def {self.name} %}}) "
                "at the top level of the template? render_block dispatch and "
                "_globals_setup only see top-level definitions."
            )
        return f"Use {{{{ {self.name} | default('') }}}} for optional variables"

    def _nullsafe_hint_text(self) -> str | None:
        """Return an additional null-safe hint for attribute/key errors.

        For missing attributes or dict keys under strict mode, the fix is
        usually to switch the access to a null-safe form rather than to
        supply a default at the variable level. Since v0.8.0, ``?.`` and
        ``?[...]`` on Mapping receivers return ``None`` for missing keys —
        so ``x?.y`` alone is the fix for dict-key misses; object-attr misses
        still need ``?? ""`` or the ``get`` filter.
        """
        if self._kind != "attribute/key":
            return None
        return (
            "For optional access: `x?.y` (None on missing Mapping keys), "
            '`x?.y ?? ""` (covers object-attr misses too), '
            "or `x | get(\"y\", '')`."
        )

    def _format_message(self) -> str:
        terminal = _terminal()
        location = self.template
        if self.lineno:
            location += f":{self.lineno}"
        msg = f"Undefined {self._kind} '{self.name}' in {terminal.location(location)}"

        # "Did you mean?" suggestion via fuzzy matching
        if self.suggestion:
            suggested = terminal.suggestion(self.suggestion)
            msg += f". Did you mean '{suggested}'?"

        # Source snippet (shows the template line where error occurred)
        if self.source_snippet:
            msg += "\n" + self.source_snippet.format()

        # Component stack trace (Sprint 1.3)
        if self.component_stack:
            msg += "\n\n" + format_component_stack(self.component_stack)

        # Template stack trace (Feature 2.1)
        if self.template_stack:
            msg += "\n\n" + format_template_stack(self.template_stack)

        hint_text = self._hint_text()
        msg += f"\n  {terminal.hint('Hint:')} {hint_text}"
        nullsafe = self._nullsafe_hint_text()
        if nullsafe:
            msg += f"\n  {terminal.hint('Hint:')} {nullsafe}"
        return msg

    def diagnostic_hints(self) -> tuple[str, ...]:
        """Return ordered plain-text hints for structured renderers."""
        hints: list[str] = []
        if self.suggestion:
            hints.append(f"Did you mean '{self.suggestion}'?")
        nullsafe = self._nullsafe_hint_text()
        if nullsafe:
            hints.append(nullsafe)
        hints.append(self._hint_text())
        return tuple(hints)

    def to_diagnostic(self) -> TemplateDiagnostic:
        """Return a surface-neutral diagnostic payload for this error."""
        location = DiagnosticLocation(
            template=self.template,
            line=self.lineno,
            column=self.source_snippet.column if self.source_snippet else None,
        )
        message = f"Undefined {self.kind} '{self.name}' in {location.format()}"
        metadata = (
            ("name", self.name),
            ("kind", self.kind),
        )
        return TemplateDiagnostic(
            code=self.code.value if self.code else None,
            title=f"Undefined {self.kind}",
            message=message,
            kind=self.kind,
            location=location,
            source_snippet=self.source_snippet,
            hints=self.diagnostic_hints(),
            docs_url=self.code.docs_url if self.code else None,
            suggestion=self.suggestion,
            template_stack=tuple(
                DiagnosticFrame(template=template, line=line)
                for template, line in self.template_stack
            ),
            component_stack=tuple(
                DiagnosticFrame(template=template, line=line, name=name)
                for template, line, name in self.component_stack
            ),
            metadata=metadata,
        )

    def format_compact(self) -> str:
        """Format undefined variable error as structured terminal diagnostic."""
        terminal = _terminal()
        diagnostic = self.to_diagnostic()
        parts: list[str] = []

        # Header: code + message
        msg = terminal.format_error_header(
            diagnostic.code,
            f"Undefined {diagnostic.kind} '{self.name}' in "
            f"{terminal.location(diagnostic.location.format())}",
        )

        # "Did you mean?" suggestion
        if diagnostic.suggestion:
            suggested = terminal.suggestion(diagnostic.suggestion)
            msg += f". Did you mean '{suggested}'?"
        parts.append(msg)

        # Source snippet
        if diagnostic.source_snippet:
            parts.append(diagnostic.source_snippet.format())

        # Component stack trace (Sprint 1.3)
        if diagnostic.component_stack:
            parts.append("")
            parts.append(format_component_stack(self.component_stack))

        # Template stack trace (Feature 2.1)
        if diagnostic.template_stack:
            parts.append("")
            parts.append(format_template_stack(self.template_stack))

        # Hint
        for hint in diagnostic.hints:
            if hint.startswith("Did you mean "):
                continue
            parts.append(f"  {terminal.hint('Hint:')} {hint}")

        # Docs URL
        if diagnostic.docs_url:
            parts.append(f"  {terminal.dim_text('Docs:')} {terminal.docs_url(diagnostic.docs_url)}")

        return "\n".join(parts)
