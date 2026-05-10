"""Tests for Template.render_with_blocks() composition path."""

import pytest

from kida import DictLoader, Environment, Markup, TemplateRuntimeError


def _env(**templates: str) -> Environment:
    """Build an Environment with in-memory templates."""
    return Environment(loader=DictLoader(templates))


class TestRenderWithBlocks:
    """render_with_blocks should support region + call/slot scope lookups."""

    def test_override_values_are_trusted_pre_rendered_html(self) -> None:
        env = _env(layout="<main>{% block content %}base{% endblock %}</main>")
        template = env.get_template("layout")

        result = template.render_with_blocks({"content": "<strong>trusted</strong>"})

        assert "<strong>trusted</strong>" in result
        assert "&lt;strong&gt;" not in result

    def test_markup_override_passes_through_without_double_escape(self) -> None:
        env = _env(layout="<main>{% block content %}base{% endblock %}</main>")
        template = env.get_template("layout")

        result = template.render_with_blocks({"content": Markup("<em>safe</em>")})

        assert "<em>safe</em>" in result

    def test_inherited_layout_sibling_block_override(self) -> None:
        env = _env(
            base=(
                "<main>{% block content %}base{% endblock %}</main>"
                "<aside>{% block sidebar %}side{% endblock %}</aside>"
            ),
            page='{% extends "base" %}{% block content %}page{% endblock %}',
        )
        template = env.get_template("page")

        result = template.render_with_blocks({"sidebar": "<nav>links</nav>"})

        assert "<main>page</main>" in result
        assert "<aside><nav>links</nav></aside>" in result

    def test_unknown_block_raises_structured_error(self) -> None:
        env = _env(layout="<main>{% block content %}base{% endblock %}</main>")
        template = env.get_template("layout")

        with pytest.raises(TemplateRuntimeError) as exc_info:
            template.render_with_blocks({"contentt": "typo"})

        assert "unknown block(s)" in str(exc_info.value)
        assert "did you mean 'content'" in str(exc_info.value)

    def test_override_content_can_invoke_region_with_outer_context(self) -> None:
        env = _env(
            layout="""{% region shell(current_path="/") %}
{{ breadcrumb_items | default([{"label":"Home","href":"/"}]) | length }}
{% end %}
<main>{% block content %}base{% endblock %}</main>"""
        )
        template = env.get_template("layout")
        region_html = template.render_block(
            "shell",
            breadcrumb_items=[{"label": "Docs", "href": "/docs"}],
        )
        result = template.render_with_blocks(
            {"content": region_html},
        )
        assert "<main>" in result
        assert "1" in result

    def test_override_content_region_with_imported_call_slot(self) -> None:
        env = _env(
            forms="""{% def form(action, method="get") %}
<form action="{{ action }}" method="{{ method }}">{% slot %}</form>
{% end %}""",
            layout="""{% from "forms" import form %}
{% region shell(current_path="/") %}
{% call form("/search") %}{{ selected_tags | join(",") }}{% end %}
{% end %}
<main>{% block content %}base{% endblock %}</main>""",
        )
        template = env.get_template("layout")
        region_html = template.render_block("shell", selected_tags=["a", "b"])
        result = template.render_with_blocks(
            {"content": region_html},
        )
        assert "<form" in result
        assert "a,b" in result
