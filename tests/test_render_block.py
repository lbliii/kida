"""Tests for Template.render_block() — block-level rendering.

This is the contract that chirp's Fragment return type depends on.
If these tests break, chirp's core differentiator (HTML fragments) breaks.
"""

import pytest

from kida import DictLoader, Environment, TemplateError


def _env(**templates: str) -> Environment:
    """Build an Environment with in-memory templates."""
    return Environment(loader=DictLoader(templates))


class TestRenderBlock:
    """Basic render_block functionality."""

    def test_simple_block(self) -> None:
        env = _env(
            page="Header {% block content %}Hello, {{ name }}!{% endblock %} Footer"
        )
        template = env.get_template("page")
        result = template.render_block("content", name="World")
        assert result.strip() == "Hello, World!"

    def test_block_with_context(self) -> None:
        env = _env(
            page="{% block items %}{% for x in things %}<li>{{ x }}</li>{% endfor %}{% endblock %}"
        )
        template = env.get_template("page")
        result = template.render_block("items", things=["a", "b", "c"])
        assert "<li>a</li>" in result
        assert "<li>b</li>" in result
        assert "<li>c</li>" in result

    def test_block_isolates_output(self) -> None:
        """render_block should only return the block, not surrounding content."""
        env = _env(
            page="BEFORE {% block middle %}MIDDLE{% endblock %} AFTER"
        )
        template = env.get_template("page")
        result = template.render_block("middle")
        assert "MIDDLE" in result
        assert "BEFORE" not in result
        assert "AFTER" not in result

    def test_nonexistent_block_raises(self) -> None:
        env = _env(page="{% block real %}content{% endblock %}")
        template = env.get_template("page")
        with pytest.raises((KeyError, TemplateError)):
            template.render_block("nonexistent")

    def test_empty_block(self) -> None:
        env = _env(page="{% block empty %}{% endblock %}")
        template = env.get_template("page")
        result = template.render_block("empty")
        assert result.strip() == ""


class TestRenderBlockInheritance:
    """render_block with template inheritance ({% extends %})."""

    def test_child_overrides_block(self) -> None:
        env = _env(
            base="<html>{% block content %}default{% endblock %}</html>",
            child='{% extends "base" %}{% block content %}overridden{% endblock %}',
        )
        template = env.get_template("child")
        result = template.render_block("content")
        assert "overridden" in result
        assert "default" not in result

    def test_child_block_with_context(self) -> None:
        env = _env(
            base="<html>{% block content %}{% endblock %}</html>",
            child='{% extends "base" %}{% block content %}<h1>{{ title }}</h1>{% endblock %}',
        )
        template = env.get_template("child")
        result = template.render_block("content", title="Hello")
        assert "<h1>Hello</h1>" in result
        assert "<html>" not in result

    def test_unoverridden_block_not_available(self) -> None:
        """Blocks not overridden by the child are not available via render_block."""
        env = _env(
            base="{% block sidebar %}Default Sidebar{% endblock %} {% block content %}{% endblock %}",
            child='{% extends "base" %}{% block content %}Page Content{% endblock %}',
        )
        template = env.get_template("child")
        # sidebar wasn't overridden — kida only exposes blocks the child defines
        with pytest.raises((KeyError, TemplateError)):
            template.render_block("sidebar")


class TestListBlocks:
    """Template.list_blocks() — discover available block names."""

    def test_single_block(self) -> None:
        env = _env(page="{% block content %}hello{% endblock %}")
        template = env.get_template("page")
        blocks = template.list_blocks()
        assert "content" in blocks

    def test_multiple_blocks(self) -> None:
        env = _env(
            page="{% block header %}h{% endblock %}{% block content %}c{% endblock %}{% block footer %}f{% endblock %}"
        )
        template = env.get_template("page")
        blocks = template.list_blocks()
        assert "header" in blocks
        assert "content" in blocks
        assert "footer" in blocks

    def test_no_blocks(self) -> None:
        env = _env(page="Just text, no blocks")
        template = env.get_template("page")
        blocks = template.list_blocks()
        assert blocks == []

    def test_inherited_blocks_only_overridden(self) -> None:
        """list_blocks only returns blocks the child explicitly defines."""
        env = _env(
            base="{% block a %}{% endblock %}{% block b %}{% endblock %}",
            child='{% extends "base" %}{% block a %}overridden{% endblock %}',
        )
        template = env.get_template("child")
        blocks = template.list_blocks()
        assert "a" in blocks
        # b was not overridden — kida doesn't list it
        assert "b" not in blocks
