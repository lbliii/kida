"""Snapshot-style tests for Kida error messages.

Asserts that error messages include expected structure (location, suggestion,
source snippet) to prevent regressions when enhancing error handling.
"""

from __future__ import annotations

import pytest

from kida.environment import Environment
from kida.environment.exceptions import (
    TemplateRuntimeError,
    UndefinedError,
)


class TestErrorMessageStructure:
    """Error messages must include key structural elements."""

    def test_undefined_error_has_location_and_hint(self) -> None:
        """UndefinedError includes template location and hint."""
        env = Environment()
        tmpl = env.from_string("{{ missing_attr }}", name="test.html")
        with pytest.raises(UndefinedError) as exc_info:
            tmpl.render()
        msg = str(exc_info.value)
        assert "test.html" in msg
        assert "missing_attr" in msg
        assert "Hint:" in msg or "default" in msg.lower()

    def test_division_by_zero_has_suggestion(self) -> None:
        """ZeroDivisionError enhanced with suggestion."""
        env = Environment()
        tmpl = env.from_string("{{ 1 / 0 }}", name="div.html")
        with pytest.raises(TemplateRuntimeError) as exc_info:
            tmpl.render()
        msg = str(exc_info.value)
        assert "div.html" in msg
        assert "Division" in msg or "zero" in msg.lower()

    def test_key_error_has_suggestion(self) -> None:
        """KeyError enhanced with .get() or ?[key] suggestion."""
        env = Environment()
        tmpl = env.from_string("{{ data['missing'] }}", name="key.html")
        with pytest.raises(TemplateRuntimeError) as exc_info:
            tmpl.render(data={})
        msg = str(exc_info.value)
        assert "key.html" in msg
        assert ".get(" in msg or "?[" in msg

    def test_attribute_error_on_none_has_suggestion(self) -> None:
        """AttributeError (e.g. from filter) suggests optional chaining."""
        env = Environment()

        def force_attr(obj: object, name: str) -> object:
            """Filter that raises AttributeError when attr missing."""
            return getattr(obj, name)

        env.add_filter("force_attr", force_attr)
        tmpl = env.from_string("{{ obj | force_attr('title') }}", name="attr.html")
        with pytest.raises(TemplateRuntimeError) as exc_info:
            tmpl.render(obj=None)
        msg = str(exc_info.value)
        assert "attr.html" in msg
        assert "optional" in msg.lower() or "?. " in msg or "is defined" in msg.lower()
