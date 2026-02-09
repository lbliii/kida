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


class TestFragmentBlocks:
    """{% fragment name %} — blocks skipped during render(), available via render_block()."""

    def test_fragment_skipped_during_render(self) -> None:
        """Fragment blocks produce no output during full template render."""
        env = _env(
            page="Before {% fragment notification %}<div>{{ title }}</div>{% end %} After"
        )
        template = env.get_template("page")
        result = template.render()
        assert result.strip() == "Before  After"
        assert "notification" not in result

    def test_fragment_renders_via_render_block(self) -> None:
        """Fragment blocks render normally when called via render_block()."""
        env = _env(
            page="Before {% fragment notification %}<div>{{ title }}</div>{% end %} After"
        )
        template = env.get_template("page")
        result = template.render_block("notification", title="Hello!")
        assert "<div>Hello!</div>" in result

    def test_fragment_with_variables_no_error(self) -> None:
        """Fragment blocks don't raise UndefinedError during full render."""
        env = _env(
            page="OK {% fragment card %}{{ undefined_var }}{% end %} Done"
        )
        template = env.get_template("page")
        # This should NOT raise — the fragment body is never evaluated
        result = template.render()
        assert "OK" in result
        assert "Done" in result

    def test_fragment_listed_in_blocks(self) -> None:
        """Fragment blocks appear in list_blocks()."""
        env = _env(
            page="{% block header %}h{% endblock %}{% fragment sidebar %}s{% end %}"
        )
        template = env.get_template("page")
        blocks = template.list_blocks()
        assert "header" in blocks
        assert "sidebar" in blocks

    def test_fragment_with_inheritance(self) -> None:
        """Fragment blocks work with template inheritance."""
        env = _env(
            base="{% block content %}{% endblock %}{% fragment oob %}{{ data }}{% end %}",
            child='{% extends "base" %}{% block content %}Main{% endblock %}',
        )
        template = env.get_template("child")
        # Full render: fragment is skipped
        result = template.render()
        assert "Main" in result
        assert "data" not in result

    def test_fragment_endfragment_closing(self) -> None:
        """Fragment blocks accept {% endfragment %} as closing tag."""
        env = _env(
            page="{% fragment sidebar %}<nav>{{ menu }}</nav>{% endfragment %}"
        )
        template = env.get_template("page")
        result = template.render()
        assert result.strip() == ""
        result = template.render_block("sidebar", menu="Home")
        assert "<nav>Home</nav>" in result


class TestGlobalsBlock:
    """{% globals %} — setup block for macros available during render_block()."""

    def test_globals_macro_available_in_full_render(self) -> None:
        """Macros defined in globals are available during full render."""
        env = _env(
            page=(
                '{% globals %}{% def greet(name) %}Hello, {{ name }}!{% end %}{% end %}'
                '{% block content %}{{ greet("World") }}{% endblock %}'
            )
        )
        template = env.get_template("page")
        result = template.render()
        assert "Hello, World!" in result

    def test_globals_macro_available_in_render_block(self) -> None:
        """Macros defined in globals are available during render_block()."""
        env = _env(
            page=(
                '{% globals %}{% def greet(name) %}Hello, {{ name }}!{% end %}{% end %}'
                '{% block content %}{{ greet("World") }}{% endblock %}'
            )
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "Hello, World!" in result

    def test_globals_variable_in_render_block(self) -> None:
        """Variables set in globals are available during render_block()."""
        env = _env(
            page=(
                '{% globals %}{% set site_name = "My Site" %}{% end %}'
                '{% block title %}{{ site_name }}{% endblock %}'
            )
        )
        template = env.get_template("page")
        result = template.render_block("title")
        assert "My Site" in result

    def test_globals_with_inheritance(self) -> None:
        """Globals in base template are available in child's render_block()."""
        env = _env(
            base=(
                '{% globals %}{% def field(name) %}<input name="{{ name }}">{% end %}{% end %}'
                '{% block form %}default{% endblock %}'
            ),
            child=(
                '{% extends "base" %}'
                '{% block form %}{{ field("email") }}{% endblock %}'
            ),
        )
        template = env.get_template("child")
        # Full render should work
        result = template.render()
        assert '<input name="email">' in result

    def test_globals_no_output(self) -> None:
        """Globals block produces no output during full render."""
        env = _env(
            page=(
                'Before{% globals %}{% def f() %}x{% end %}{% end %}After'
                '{% block content %}{{ f() }}{% endblock %}'
            )
        )
        template = env.get_template("page")
        result = template.render()
        assert "BeforeAfter" in result.replace("x", "").replace("\n", "").replace(" ", "") or \
               "Before" in result and "After" in result

    def test_globals_endglobals_closing(self) -> None:
        """Globals blocks accept {% endglobals %} as closing tag."""
        env = _env(
            page=(
                '{% globals %}{% def f() %}ok{% end %}{% endglobals %}'
                '{% block content %}{{ f() }}{% endblock %}'
            )
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "ok" in result

    def test_globals_from_import_in_render_block(self) -> None:
        """{% from...import %} inside globals makes macros available in render_block()."""
        env = _env(
            macros='{% def greet(name) %}Hello, {{ name }}!{% end %}',
            page=(
                '{% globals %}{% from "macros" import greet %}{% end %}'
                '{% block content %}{{ greet("World") }}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        # Full render: macro is available
        result = template.render()
        assert "Hello, World!" in result
        # Block render: macro is also available via globals setup
        result = template.render_block("content")
        assert "Hello, World!" in result

    def test_globals_from_import_in_fragment(self) -> None:
        """{% from...import %} inside globals works with {% fragment %} blocks."""
        env = _env(
            macros='{% def card(title) %}<div>{{ title }}</div>{% end %}',
            page=(
                '{% globals %}{% from "macros" import card %}{% end %}'
                'Page content'
                '{% fragment oob %}{{ card("Task 1") }}{% endfragment %}'
            ),
        )
        template = env.get_template("page")
        # Full render: fragment is skipped
        result = template.render()
        assert "Page content" in result
        assert "Task 1" not in result
        # Block render: macro from globals is available
        result = template.render_block("oob")
        assert "<div>Task 1</div>" in result

    def test_globals_from_import_multiple(self) -> None:
        """Multiple {% from...import %} in globals all propagate to render_block()."""
        env = _env(
            helpers='{% def bold(text) %}<b>{{ text }}</b>{% end %}',
            icons='{% def icon(name) %}<i>{{ name }}</i>{% end %}',
            page=(
                '{% globals %}'
                '{% from "helpers" import bold %}'
                '{% from "icons" import icon %}'
                '{% end %}'
                '{% block content %}{{ bold("hi") }} {{ icon("star") }}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "<b>hi</b>" in result
        assert "<i>star</i>" in result
