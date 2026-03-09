"""Tests for Template.render_with_blocks() composition path."""

from kida import DictLoader, Environment


def _env(**templates: str) -> Environment:
    """Build an Environment with in-memory templates."""
    return Environment(loader=DictLoader(templates))


class TestRenderWithBlocks:
    """render_with_blocks should support region + call/slot scope lookups."""

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
