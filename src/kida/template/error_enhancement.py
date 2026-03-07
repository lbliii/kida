"""Template error enhancement — convert generic exceptions to TemplateRuntimeError.

Pure function: no Template state, no side effects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.environment.exceptions import TemplateRuntimeError
    from kida.render_context import RenderContext


def enhance_template_error(
    error: Exception,
    render_ctx: RenderContext,
    source: str | None,
) -> TemplateRuntimeError:
    """Enhance a generic exception with template context from RenderContext.

    Converts generic Python exceptions into TemplateRuntimeError with
    template name, line number, and source snippet context.
    """
    from kida.environment.exceptions import (
        ErrorCode,
        NoneComparisonError,
        TemplateRuntimeError,
        build_source_snippet,
    )

    template_name = render_ctx.template_name
    lineno = render_ctx.line
    error_str = str(error).strip()
    error_type = type(error).__name__

    # Handle empty or ambiguous error messages (e.g., KeyError(1) yields "1")
    if not error_str:
        if hasattr(error, "args") and error.args:
            non_empty = [str(a) for a in error.args if str(a).strip()]
            if non_empty:
                error_str = f"{error_type}: {', '.join(non_empty)}"
            else:
                error_str = f"{error_type} (no details available)"
        else:
            error_str = f"{error_type} (no details available)"
    elif not error_str.startswith(error_type):
        error_str = f"{error_type}: {error_str}"

    # Build source snippet from template source
    snippet = None
    if source and lineno:
        snippet = build_source_snippet(source, lineno)

    # Handle None comparison errors specially
    if isinstance(error, TypeError) and "NoneType" in error_str:
        return NoneComparisonError(
            None,
            None,
            template_name=template_name,
            lineno=lineno,
            expression="<see stack trace>",
            source_snippet=snippet,
        )

    # Determine error code from exception type
    error_code = ErrorCode.RUNTIME_ERROR
    if isinstance(error, KeyError):
        error_code = ErrorCode.KEY_ERROR
    elif isinstance(error, AttributeError):
        error_code = ErrorCode.ATTRIBUTE_ERROR
    elif isinstance(error, ZeroDivisionError):
        error_code = ErrorCode.ZERO_DIVISION
    elif isinstance(error, TypeError):
        error_code = ErrorCode.TYPE_ERROR

    # TypeError from arithmetic (e.g. str // int) - YAML/config may pass strings
    suggestion = None
    if isinstance(error, TypeError) and (
        "unsupported operand" in error_str or "'str'" in error_str
    ):
        suggestion = (
            "Values from YAML/config may be strings. Use the coerce_int filter "
            "or ensure numeric types at the data source."
        )

    # AttributeError/TypeError: '_Undefined' — attribute access on missing value
    if (isinstance(error, (AttributeError, TypeError))) and (
        "_undefined" in error_str.lower()
        and ("not callable" in error_str.lower() or "has no attribute" in error_str.lower())
    ):
        suggestion = (
            "Attribute access on a missing value. Use optional chaining (`?.`) "
            "or check with `is defined`."
        )

    # AttributeError on None/NoneType — same suggestion (e.g. from filters)
    if (
        suggestion is None
        and isinstance(error, AttributeError)
        and ("has no attribute" in error_str.lower() and "nonetype" in error_str.lower())
    ):
        suggestion = (
            "Attribute access on a missing value. Use optional chaining (`?.`) "
            "or check with `is defined`."
        )

    # KeyError — safe key access
    if isinstance(error, KeyError) and error.args:
        key = error.args[0]
        suggestion = f"Key {key!r} not found. Use `.get({key!r})` or `?[{key}]` for safe access."

    # ZeroDivisionError
    if isinstance(error, ZeroDivisionError):
        suggestion = "Division by zero. Guard with `{% if divisor %}` or use `| default(1)`."

    return TemplateRuntimeError(
        error_str,
        template_name=template_name,
        lineno=lineno,
        source_snippet=snippet,
        template_stack=list(render_ctx.template_stack),
        suggestion=suggestion,
        code=error_code,
    )
