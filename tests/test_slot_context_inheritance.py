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
                "{% block page_content %}{% call form() %}{{ page_var }}{% end %}{% endblock %}"
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
                "{% block page_content %}{% call form() %}{{ page_var }}{% end %}{% endblock %}"
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
                "{% block page_content %}"
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
                "{% block content %}{% call wrapper() %}{{ missing_var }}{% end %}{% endblock %}"
            ),
        )
        template = env.get_template("page")
        with pytest.raises(UndefinedError):
            template.render_block("content")


class TestNestedImportedMacrosSlotContext:
    """Reproduce Dori skills page: container → stack → form with page vars in innermost slot.

    These tests mirror the chirpui layout chain. If they fail with UndefinedError,
    they confirm the slot context inheritance bug in nested imported macros.
    """

    def test_container_stack_form_selected_tags_via_render_block(self) -> None:
        """selected_tags in form slot with container→stack→form from separate templates."""
        env = _env(
            layout=(
                "{% def container(cls='') %}"
                '<div class="container{{ " " ~ cls if cls else "" }}">{% slot %}</div>'
                "{% end %}"
                "{% def stack(gap='') %}"
                '<div class="stack{{ " chirpui-stack--" ~ gap if gap else "" }}">{% slot %}</div>'
                "{% end %}"
            ),
            forms=(
                "{% def form(action, method='get') %}"
                '<form action="{{ action }}" method="{{ method }}">{% slot %}</form>'
                "{% end %}"
            ),
            page=(
                '{% from "layout" import container, stack %}'
                '{% from "forms" import form %}'
                "{% block page_content %}"
                "{% call container() %}"
                '{% call stack(gap="lg") %}'
                "<h1>Skills</h1>"
                '{% call form("/skills", method="get") %}'
                '{{ selected_tags | join(",") }}'
                "{% end %}"
                "{% end %}"
                "{% end %}"
                "{% endblock %}"
            ),
        )
        template = env.get_template("page")
        result = template.render_block("page_content", selected_tags=["a", "b"])
        assert "a,b" in result
        assert 'action="/skills"' in result

    def test_container_stack_form_all_tags_via_render_block(self) -> None:
        """all_tags in stack slot (between form and container) with nested imported macros."""
        env = _env(
            layout=(
                '{% def container() %}<div class="container">{% slot %}</div>{% end %}'
                '{% def stack() %}<div class="stack">{% slot %}</div>{% end %}'
            ),
            page=(
                '{% from "layout" import container, stack %}'
                "{% block page_content %}"
                "{% call container() %}"
                "{% call stack() %}"
                "{% for tag in all_tags %}{{ tag }}{% end %}"
                "{% end %}"
                "{% end %}"
                "{% endblock %}"
            ),
        )
        template = env.get_template("page")
        result = template.render_block("page_content", all_tags=["x", "y"])
        assert "xy" in result

    def test_triple_nested_all_vars_via_render_block(self) -> None:
        """selected_tags, all_tags, q in triple-nested container→stack→form."""
        env = _env(
            layout=(
                "{% def container() %}<div>{% slot %}</div>{% end %}"
                "{% def stack() %}<div>{% slot %}</div>{% end %}"
            ),
            forms=('{% def form(action) %}<form action="{{ action }}">{% slot %}</form>{% end %}'),
            page=(
                '{% from "layout" import container, stack %}'
                '{% from "forms" import form %}'
                "{% block page_content %}"
                "{% call container() %}"
                "{% call stack() %}"
                '{% call form("/search") %}'
                'q={{ q }} tags={{ selected_tags | join(",") }} all={{ all_tags | join(",") }}'
                "{% end %}"
                "{% end %}"
                "{% end %}"
                "{% endblock %}"
            ),
        )
        template = env.get_template("page")
        result = template.render_block(
            "page_content",
            q="hello",
            selected_tags=["a"],
            all_tags=["a", "b"],
        )
        assert "q=hello" in result
        assert "tags=a" in result
        assert "all=a,b" in result

    def test_chirpui_style_imports_and_paths(self) -> None:
        """Exact Chirp/Dori structure: chirpui/layout.html, chirpui/forms.html, skills/page.html."""
        env = _env(
            chirpui_layout=(
                "{% def container(cls='') %}"
                '<div class="chirpui-container{{ " " ~ cls if cls else "" }}">{% slot %}</div>'
                "{% end %}"
                "{% def stack(gap='') %}"
                '<div class="chirpui-stack{{ " chirpui-stack--" ~ gap if gap else "" }}">{% slot %}</div>'
                "{% end %}"
            ),
            chirpui_forms=(
                "{% def form(action, method='get') %}"
                '<form action="{{ action }}" method="{{ method }}">{% slot %}</form>'
                "{% end %}"
            ),
            skills_page=(
                '{% from "chirpui_layout" import container, stack %}'
                '{% from "chirpui_forms" import form %}'
                "{% block page_content %}"
                "{% call container() %}"
                '{% call stack(gap="lg") %}'
                "<h1>Skills</h1>"
                '{% call form("/skills", method="get") %}'
                "q={{ q }}"
                '{% if selected_tags %}{{ selected_tags | join(",") }}{% end %}'
                "{% if all_tags %}{% for tag in all_tags %}{{ tag }}{% end %}{% end %}"
                "{% end %}"
                "{% end %}"
                "{% end %}"
                "{% endblock %}"
            ),
        )
        template = env.get_template("skills_page")
        result = template.render_block(
            "page_content",
            q="search",
            selected_tags=["a", "b"],
            all_tags=["a", "b", "c"],
        )
        assert "a,b" in result
        assert "abc" in result
        assert 'action="/skills"' in result
