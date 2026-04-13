"""End-to-end property tests: arbitrary source -> compile -> render.

Verifies that the full pipeline (from_string + render) never crashes.
Output is always str when render succeeds.
"""

from __future__ import annotations

import contextlib

from hypothesis import given, settings

from kida import Environment
from kida.environment.exceptions import (
    TemplateNotFoundError,
    TemplateRuntimeError,
    TemplateSyntaxError,
    UndefinedError,
)
from kida.lexer import LexerError

from .strategies import arbitrary_template_source, e2e_fuzz_source

# Expected exceptions for invalid/malformed input
_EXPECTED_E2E_ERRORS = (
    TemplateSyntaxError,
    TemplateRuntimeError,
    UndefinedError,
    TemplateNotFoundError,
    LexerError,
)


class TestE2EFuzz:
    """E2E: source -> compile -> render never crashes."""

    @given(source=arbitrary_template_source)
    @settings(max_examples=200)
    def test_compile_render_no_crash(self, source: str) -> None:
        """from_string + render: no segfault, no unhandled exception."""
        env = Environment()
        try:
            tmpl = env.from_string(source)
            result = tmpl.render()
        except _EXPECTED_E2E_ERRORS:
            return  # Expected errors for invalid/malformed input
        assert isinstance(result, str)

    @given(source=e2e_fuzz_source)
    @settings(max_examples=150)
    def test_e2e_fuzz_output_is_str(self, source: str) -> None:
        """When render succeeds, output is always str."""
        env = Environment()
        with contextlib.suppress(*_EXPECTED_E2E_ERRORS):
            tmpl = env.from_string(source)
            result = tmpl.render()
            assert isinstance(result, str)
