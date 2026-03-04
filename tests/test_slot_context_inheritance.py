"""Regression test for slot context inheritance.

When page variables (e.g. selected_tags) are used inside macro slot content
(e.g. form body), they must be available from the caller's render context.
This tests that render_block and render both pass context correctly into
slot bodies without requiring | default() workarounds.
"""

import pytest

from kida import DictLoader, Environment


def _env(**templates: str) -> Environment:
    """Build an Environment with in-memory templates."""
    return Environment(loader=DictLoader(templates))


class TestSlotContextInheritance:
    """Slot content must inherit caller's render context."""

    def test_page_var_in_slot_via_render_block(self) -> None:
        """page_var from render_block context is available in slot content."""
        env = _env(
            page=(
                "{% globals %}{% def form() %}"
                "<form>{% slot %}</form>"
                "{% end %}{% end %}"
                '{% block page_content %}{% call form() %}{{ page_var }}{% end %}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        result = template.render_block("page_content", page_var="hello")
        assert "hello" in result
        assert "<form>" in result

    def test_page_var_in_slot_via_full_render(self) -> None:
        """page_var from render context is available in slot content."""
        env = _env(
            page=(
                "{% def form() %}"
                "<form>{% slot %}</form>"
                "{% end %}"
                '{% block page_content %}{% call form() %}{{ page_var }}{% end %}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        result = template.render(page_var="world")
        assert "world" in result

    def test_imported_macro_slot_gets_page_context(self) -> None:
        """Slot content in imported macro receives page context (mirrors Chirp UI form)."""
        env = _env(
            forms=(
                "{% def form(action, method='get') %}"
                '<form action="{{ action }}" method="{{ method }}">'
                "{% slot %}"
                "</form>"
                "{% end %}"
            ),
            page=(
                '{% from "forms" import form %}'
                '{% block page_content %}'
                '{% call form("/search") %}{{ selected_tags | join(",") }}{% end %}'
                "{% endblock %}"
            ),
        )
        template = env.get_template("page")
        result = template.render_block("page_content", selected_tags=["a", "b"])
        assert "a,b" in result
        assert 'action="/search"' in result

    def test_slot_without_default_raises_when_var_missing(self) -> None:
        """Using undefined var in slot without | default() raises UndefinedError."""
        from kida.environment.exceptions import UndefinedError

        env = _env(
            page=(
                "{% def wrapper() %}<div>{% slot %}</div>{% end %}"
                '{% block content %}{% call wrapper() %}{{ missing_var }}{% end %}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        with pytest.raises(UndefinedError):
            template.render_block("content")
