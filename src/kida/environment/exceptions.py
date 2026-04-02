# DEPRECATED: This module is a backward-compatibility re-export shim.
# All internal code should import directly from ``kida.exceptions``.
# This module is retained only for external consumers that may depend on
# ``kida.environment.exceptions`` and will not be removed without a major
# version bump.
"""Re-export shim — canonical definitions live in kida.exceptions.

This module exists for backward compatibility. All exception classes,
ErrorCode, SourceSnippet, and helper functions are defined in
``kida.exceptions`` (zero internal imports at module level) to break
circular import chains.

.. deprecated::
    Import from ``kida.exceptions`` directly instead.
"""

from kida.exceptions import (
    ErrorCode,
    NoneComparisonError,
    RequiredValueError,
    SourceSnippet,
    TemplateError,
    TemplateNotFoundError,
    TemplateRuntimeError,
    TemplateSyntaxError,
    UndefinedError,
    build_source_snippet,
    format_template_stack,
)

__all__ = [
    "ErrorCode",
    "NoneComparisonError",
    "RequiredValueError",
    "SourceSnippet",
    "TemplateError",
    "TemplateNotFoundError",
    "TemplateRuntimeError",
    "TemplateSyntaxError",
    "UndefinedError",
    "build_source_snippet",
    "format_template_stack",
]
