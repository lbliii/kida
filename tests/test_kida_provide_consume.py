"""Tests for {% provide %} / consume() render context feature."""

from __future__ import annotations

import pytest

from kida import DictLoader, Environment


@pytest.fixture
def env():
    return Environment()


@pytest.fixture
def env_autoescape():
    return Environment(autoescape=True)


class TestBasicProvideConsume:
    """Basic provide/consume within a single template."""

    def test_provide_and_consume(self, env):
        t = env.from_string('{% provide color = "red" %}{{ consume("color") }}{% end %}')
        assert t.render() == "red"

    def test_consume_default_when_no_provider(self, env):
        t = env.from_string('{{ consume("missing", "fallback") }}')
        assert t.render() == "fallback"

    def test_consume_none_default_when_no_provider(self, env):
        t = env.from_string('{{ consume("missing") or "" }}')
        assert t.render() == ""

    def test_provide_with_variable_value(self, env):
        t = env.from_string('{% provide greeting = name %}{{ consume("greeting") }}{% end %}')
        assert t.render(name="hello") == "hello"

    def test_provide_with_list_value(self, env):
        t = env.from_string(
            '{% provide align = ["left", "right"] %}{{ consume("align")[0] }}{% end %}'
        )
        assert t.render() == "left"

    def test_provide_with_endprovide(self, env):
        t = env.from_string('{% provide x = 1 %}{{ consume("x") }}{% endprovide %}')
        assert t.render() == "1"


class TestNestedProvide:
    """Nested provides: inner shadows outer, restores on exit."""

    def test_inner_shadows_outer(self, env):
        t = env.from_string(
            '{% provide x = "outer" %}{% provide x = "inner" %}{{ consume("x") }}{% end %}{% end %}'
        )
        assert t.render() == "inner"

    def test_outer_restored_after_inner_exits(self, env):
        t = env.from_string(
            '{% provide x = "outer" %}{% provide x = "inner" %}{% end %}{{ consume("x") }}{% end %}'
        )
        assert t.render() == "outer"

    def test_independent_keys(self, env):
        t = env.from_string(
            '{% provide a = "A" %}'
            '{% provide b = "B" %}'
            '{{ consume("a") }}{{ consume("b") }}'
            "{% end %}"
            "{% end %}"
        )
        assert t.render() == "AB"


class TestProvideAcrossSlots:
    """Provide flowing through slot boundaries to child macros."""

    def test_provide_visible_in_slot_content(self, env):
        t = env.from_string(
            "{% def wrapper() %}"
            '{% provide color = "red" %}'
            "{% slot %}"
            "{% endprovide %}"
            "{% end %}"
            "{% call wrapper() %}"
            '{{ consume("color") }}'
            "{% end %}"
        )
        assert t.render().strip() == "red"

    def test_provide_visible_to_macro_in_slot(self, env):
        t = env.from_string(
            "{% def parent() %}"
            '{% provide color = "red" %}'
            "{% slot %}"
            "{% endprovide %}"
            "{% end %}"
            "{% def child() %}"
            '{{ consume("color") }}'
            "{% end %}"
            "{% call parent() %}"
            "{{ child() }}"
            "{% end %}"
        )
        assert "red" in t.render()

    def test_table_row_alignment_pattern(self, env_autoescape):
        """The motivating use case: table passes alignment to row via provide."""
        t = env_autoescape.from_string(
            "{% def table(headers, align=none) %}"
            "{% provide _table_align = align %}"
            "<table><tbody>"
            "{% slot %}"
            "</tbody></table>"
            "{% endprovide %}"
            "{% end %}"
            "{% def row(*cells) %}"
            '{% set align = consume("_table_align") %}'
            "<tr>"
            "{% for cell in cells %}"
            '<td class="{{ "align-" ~ align[loop.index0] if align else "" }}">'
            "{{ cell }}</td>"
            "{% end %}"
            "</tr>"
            "{% end %}"
            '{% call table(headers=["Name", "Count"], align=["left", "right"]) %}'
            '{{ row("Alice", "42") }}'
            "{% end %}"
        )
        result = t.render()
        assert 'class="align-left"' in result
        assert 'class="align-right"' in result
        assert "Alice" in result
        assert "42" in result


class TestProvideWithImportedMacros:
    """Imported macros can consume from the calling template's provide."""

    def test_imported_macro_consumes(self):
        loader = DictLoader(
            {
                "components.html": ('{% def child() %}{{ consume("color") }}{% end %}'),
                "page.html": (
                    '{% from "components.html" import child %}'
                    '{% provide color = "green" %}'
                    "{{ child() }}"
                    "{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        t = env.get_template("page.html")
        assert "green" in t.render()

    def test_imported_macro_in_slot_consumes(self):
        loader = DictLoader(
            {
                "row.html": (
                    "{% def row(*cells) %}"
                    '{% set align = consume("_align") %}'
                    "<tr>"
                    "{% for cell in cells %}"
                    "<td>{{ cell }}</td>"
                    "{% end %}"
                    "</tr>"
                    "{% end %}"
                ),
                "page.html": (
                    '{% from "row.html" import row %}'
                    "{% def table() %}"
                    '{% provide _align = ["left", "right"] %}'
                    "<table>{% slot %}</table>"
                    "{% endprovide %}"
                    "{% end %}"
                    '{% call table() %}{{ row("a", "b") }}{% end %}'
                ),
            }
        )
        env = Environment(loader=loader)
        t = env.get_template("page.html")
        result = t.render()
        assert "<tr>" in result
        assert "<td>a</td>" in result


class TestProvideErrorSafety:
    """Provide cleans up even when body raises."""

    def test_cleanup_on_error(self, env):
        t = env.from_string(
            '{% provide x = "before" %}'
            '{% provide x = "during" %}'
            "{{ 1 / 0 }}"
            "{% end %}"
            '{{ consume("x") }}'
            "{% end %}"
        )
        with pytest.raises(ZeroDivisionError):
            t.render()

        # After error, a fresh render should have clean provider state
        t2 = env.from_string('{{ consume("x", "clean") }}')
        assert t2.render() == "clean"


class TestProvideWithInclude:
    """Provide visible across include boundaries."""

    def test_provide_visible_in_included_template(self):
        loader = DictLoader(
            {
                "child.html": '{{ consume("theme") }}',
                "page.html": ('{% provide theme = "dark" %}{% include "child.html" %}{% end %}'),
            }
        )
        env = Environment(loader=loader)
        t = env.get_template("page.html")
        assert "dark" in t.render()
