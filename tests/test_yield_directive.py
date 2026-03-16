"""Tests for {% yield %} directive — context-independent slot rendering.

RFC: plan/rfc-yield-directive.md
"""

from __future__ import annotations

import pytest

from kida import DictLoader, Environment
from kida.lexer import Lexer
from kida.nodes import CallBlock, Def, Slot, SlotBlock
from kida.parser import Parser


class TestYieldBasic:
    """{% yield %} always produces a Slot render, even inside {% call %}."""

    def test_yield_in_def(self, env: Environment) -> None:
        """{% yield %} inside def renders caller's default content."""
        tmpl = env.from_string(
            "{% def card() %}<div>{% yield %}</div>{% end %}{% call card() %}Hello{% end %}"
        )
        assert tmpl.render() == "<div>Hello</div>"

    def test_yield_named_in_def(self, env: Environment) -> None:
        """{% yield name %} inside def renders caller's named slot."""
        tmpl = env.from_string(
            "{% def card() %}<div>{% yield footer %}</div>{% end %}"
            "{% call card() %}{% slot footer %}Footer{% end %}{% end %}"
        )
        assert tmpl.render() == "<div>Footer</div>"

    def test_yield_in_nested_call(self, env: Environment) -> None:
        """{% yield %} inside {% call %} renders outer def's caller content."""
        tmpl = env.from_string(
            "{% def inner() %}<div>{{ caller() }}</div>{% end %}"
            "{% def outer() %}{% call inner() %}{% yield %}{% end %}{% end %}"
            "{% call outer() %}Content{% end %}"
        )
        assert tmpl.render() == "<div>Content</div>"

    def test_yield_named_in_nested_call(self, env: Environment) -> None:
        """{% yield name %} inside {% call %} renders outer def's named slot.

        resource_index pattern: {% yield selection %} in a call to selection_bar
        renders "Badges" not "Cards".
        """
        tmpl = env.from_string(
            "{% def selection_bar() %}<bar>{{ caller() }}</bar>{% end %}"
            "{% def index() %}"
            "{% call selection_bar() %}{% yield selection %}{% end %}"
            "{% end %}"
            "{% call index() %}"
            "{% slot selection %}Badges{% end %}"
            "Cards"
            "{% end %}"
        )
        assert tmpl.render() == "<bar>Badges</bar>"

    def test_yield_no_caller_is_silent(self, env: Environment) -> None:
        """{% yield %} without caller produces no output (not an error)."""
        tmpl = env.from_string("{% def card() %}<div>{% yield %}</div>{% end %}{{ card() }}")
        assert tmpl.render() == "<div></div>"

    def test_yield_default_without_name(self, env: Environment) -> None:
        """{% yield %} with no name yields default slot."""
        tmpl = env.from_string(
            "{% def card() %}<div>{% yield %}</div>{% end %}"
            "{% call card() %}Default content{% end %}"
        )
        assert tmpl.render() == "<div>Default content</div>"


class TestYieldScoping:
    """Verify that yield resolves to the nearest enclosing def's caller."""

    def test_yield_in_doubly_nested_call(self, env: Environment) -> None:
        """{% yield %} in inner call still resolves to the def's caller."""
        tmpl = env.from_string(
            "{% def leaf() %}<leaf>{{ caller() }}</leaf>{% end %}"
            "{% def mid() %}<mid>{{ caller() }}</mid>{% end %}"
            "{% def outer() %}"
            "{% call mid() %}"
            "{% call leaf() %}"
            "{% yield %}"
            "{% end %}"
            "{% end %}"
            "{% end %}"
            "{% call outer() %}Content{% end %}"
        )
        assert tmpl.render() == "<mid><leaf>Content</leaf></mid>"

    def test_yield_outside_def_is_noop(self, env: Environment) -> None:
        """{% yield %} at template top level produces no output."""
        tmpl = env.from_string("{% yield %}<p>hello</p>")
        assert tmpl.render() == "<p>hello</p>"

    def test_yield_named_slot_not_provided(self, env: Environment) -> None:
        """{% yield X %} when caller doesn't define slot X → empty string."""
        tmpl = env.from_string(
            "{% def card() %}<div>{% yield sidebar %}</div>{% end %}{% call card() %}Body{% end %}"
        )
        assert tmpl.render() == "<div></div>"


class TestYieldComposite:
    """End-to-end tests for composite macro slot forwarding."""

    def test_resource_index_pattern(self) -> None:
        """Full resource_index→selection_bar→yield chain."""
        loader = DictLoader(
            {
                "selection_bar.html": (
                    "{% def selection_bar(count=0) %}"
                    '<div class="selection-bar"><span>{{ count }}</span>'
                    '<div class="actions">{{ caller() }}</div></div>'
                    "{% end %}"
                ),
                "resource_index.html": (
                    "{% from 'selection_bar.html' import selection_bar %}"
                    "{% def resource_index(title) %}"
                    '<div class="resource-index"><h1>{{ title }}</h1>'
                    "{% call selection_bar(count=3) %}{% yield selection %}{% end %}"
                    '<div class="results">{% slot %}</div></div>'
                    "{% end %}"
                ),
                "page.html": (
                    '{% from "resource_index.html" import resource_index %}'
                    "{% call resource_index('Skills') %}"
                    "{% slot selection %}<span>Badges</span>{% end %}"
                    "<article>Skill A</article>"
                    "{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        page = env.get_template("page.html")
        html = page.render()
        assert "Badges" in html
        assert "Skill A" in html
        assert "selection-bar" in html
        # Selection bar should show Badges, not Skill A
        badges_pos = html.find("Badges")
        skill_pos = html.find("Skill A")
        selection_bar_end = html.find("</div>", html.find("selection-bar"))
        assert badges_pos < selection_bar_end
        assert skill_pos > selection_bar_end

    def test_resource_index_filter_bar_pattern(self) -> None:
        """resource_index→filter_bar with multiple yields."""
        loader = DictLoader(
            {
                "filter_bar.html": (
                    "{% def filter_bar() %}"
                    '<form><div class="controls">{{ caller("filter_controls") }}</div>'
                    '<div class="actions">{{ caller("filter_actions") }}</div></form>'
                    "{% end %}"
                ),
                "resource_index.html": (
                    "{% from 'filter_bar.html' import filter_bar %}"
                    "{% def resource_index() %}"
                    "{% call filter_bar() %}"
                    "{% slot filter_controls %}{% yield filter_controls %}{% end %}"
                    "{% slot filter_actions %}{% yield filter_actions %}{% end %}"
                    "{% end %}"
                    "{% end %}"
                ),
                "page.html": (
                    '{% from "resource_index.html" import resource_index %}'
                    "{% call resource_index() %}"
                    "{% slot filter_controls %}<input type='text'>{% end %}"
                    "{% slot filter_actions %}<button>Go</button>{% end %}"
                    "{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        page = env.get_template("page.html")
        html = page.render()
        assert "<input" in html
        assert "<button>Go</button>" in html

    def test_yield_replaces_double_nesting_workaround(self, env: Environment) -> None:
        """{% yield X %} produces same output as {% slot X %}{% slot X %}{% end %}.

        Both patterns forward the outer caller's slot x into the inner call's
        default slot. Inner uses {% slot x %} to render (workaround) or caller()
        receives yield output (yield).
        """
        with_yield = env.from_string(
            "{% def inner() %}<div>{{ caller() }}</div>{% end %}"
            "{% def outer() %}{% call inner() %}{% yield x %}{% end %}{% end %}"
            "{% call outer() %}{% slot x %}Content{% end %}{% end %}"
        )
        with_workaround = env.from_string(
            "{% def inner() %}<div>{% slot x %}</div>{% end %}"
            "{% def outer() %}{% call inner() %}"
            "{% slot x %}{% slot x %}{% end %}{% end %}{% end %}"
            "{% call outer() %}{% slot x %}Content{% end %}{% end %}"
        )
        assert with_yield.render() == "<div>Content</div>"
        assert with_workaround.render() == "<div>Content</div>"

    def test_yield_mixed_with_slot_definitions(self, env: Environment) -> None:
        """{% yield %} and {% slot X %}content{% end %} coexist in same call block."""
        tmpl = env.from_string(
            "{% def inner() %}"
            "<h>{{ caller('header') }}</h>"
            "<b>{{ caller() }}</b>"
            "{% end %}"
            "{% def outer() %}"
            "{% call inner() %}"
            "{% slot header %}Static header{% end %}"
            "{% yield body %}"
            "{% end %}"
            "{% end %}"
            "{% call outer() %}{% slot body %}Dynamic{% end %}{% end %}"
        )
        assert tmpl.render() == "<h>Static header</h><b>Dynamic</b>"

    def test_yield_with_inline_content_in_call(self, env: Environment) -> None:
        """{% yield %} alongside plain text in the same call default slot."""
        tmpl = env.from_string(
            "{% def inner() %}<div>{{ caller() }}</div>{% end %}"
            "{% def outer() %}"
            "{% call inner() %}"
            "<prefix/>"
            "{% yield %}"
            "<suffix/>"
            "{% end %}"
            "{% end %}"
            "{% call outer() %}Middle{% end %}"
        )
        assert tmpl.render() == "<div><prefix/>Middle<suffix/></div>"

    def test_multiple_yields_in_same_call(self, env: Environment) -> None:
        """Multiple {% yield %} tags concatenate in order."""
        tmpl = env.from_string(
            "{% def inner() %}<div>{{ caller() }}</div>{% end %}"
            "{% def outer() %}"
            "{% call inner() %}"
            "{% yield header %}"
            "{% yield footer %}"
            "{% end %}"
            "{% end %}"
            "{% call outer() %}"
            "{% slot header %}H{% end %}"
            "{% slot footer %}F{% end %}"
            "{% end %}"
        )
        assert tmpl.render() == "<div>HF</div>"

    def test_yield_cross_template_import(self) -> None:
        """Yield works when macros are imported from different templates."""
        loader = DictLoader(
            {
                "child.html": "{% def child() %}<c>{{ caller() }}</c>{% end %}",
                "parent.html": (
                    "{% from 'child.html' import child %}"
                    "{% def parent() %}{% call child() %}{% yield x %}{% end %}{% end %}"
                ),
                "page.html": (
                    '{% from "parent.html" import parent %}'
                    "{% call parent() %}{% slot x %}Cross{% end %}{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        page = env.get_template("page.html")
        assert page.render() == "<c>Cross</c>"

    def test_yield_three_level_nesting(self, env: Environment) -> None:
        """page → composite → wrapper → leaf with yield at each level."""
        tmpl = env.from_string(
            "{% def leaf() %}<l>{{ caller() }}</l>{% end %}"
            "{% def wrapper() %}<w>{% call leaf() %}{% yield %}{% end %}</w>{% end %}"
            "{% def composite() %}<c>{% call wrapper() %}{% yield %}{% end %}</c>{% end %}"
            "{% call composite() %}Deep{% end %}"
        )
        assert tmpl.render() == "<c><w><l>Deep</l></w></c>"

    def test_yield_does_not_trigger_delegation(self) -> None:
        """Call block with yield has non-empty default slot — delegation skipped.

        Verifies that _slot_body_is_empty returns False for a slot body
        containing a Slot node.
        """
        loader = DictLoader(
            {
                "inner.html": ('{% def inner() %}<div class="inner">{{ caller() }}</div>{% end %}'),
                "outer.html": (
                    "{% from 'inner.html' import inner %}"
                    "{% def outer() %}"
                    "{% call inner() %}{% yield selection %}{% end %}"
                    "{% end %}"
                ),
                "page.html": (
                    '{% from "outer.html" import outer %}'
                    "{% call outer() %}"
                    "{% slot selection %}Tag badges{% end %}"
                    "Resource cards"
                    "{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        page = env.get_template("page.html")
        html = page.render()
        # inner's caller() receives yield output (Tag badges), not default (Resource cards)
        assert "Tag badges" in html
        # Tag badges must appear inside .inner div; Resource cards go to outer results
        inner_start = html.find('<div class="inner">')
        inner_end = html.find("</div>", inner_start)
        inner_content = html[inner_start:inner_end]
        assert "Tag badges" in inner_content
        assert "Resource cards" not in inner_content

    def test_yield_and_delegation_coexist(self, env: Environment) -> None:
        """Same call block: one named slot delegates (empty), default uses yield."""
        tmpl = env.from_string(
            "{% def inner() %}"
            "<h>{{ caller('header') }}</h>"
            "<b>{{ caller() }}</b>"
            "{% end %}"
            "{% def outer() %}"
            "{% call inner() %}"
            "{% slot header %}{% end %}"
            "{% yield footer %}"
            "{% end %}"
            "{% end %}"
            "{% call outer() %}{% slot footer %}Footer content{% end %}{% end %}"
        )
        # header: empty slot delegates → outer caller has no header slot → empty
        # footer: yield renders outer's footer slot
        assert tmpl.render() == "<h></h><b>Footer content</b>"


class TestYieldParser:
    """Parser-level tests for AST node production."""

    def _parse_template(self, source: str) -> tuple:
        """Parse source and return (body, template)."""
        lexer = Lexer(source)
        tokens = list(lexer.tokenize())
        parser = Parser(tokens, None, None, source)
        tree = parser.parse()
        return tree.body, tree

    def test_yield_produces_slot_node(self) -> None:
        """Parser returns Slot (not SlotBlock) regardless of block context."""
        source = "{% def f() %}{% call g() %}{% yield %}{% end %}{% end %}"
        body, _ = self._parse_template(source)
        def_node = body[0]
        assert isinstance(def_node, Def)
        call_node = def_node.body[0]
        assert isinstance(call_node, CallBlock)
        default_slot_body = call_node.slots.get("default", ())
        assert len(default_slot_body) == 1
        assert isinstance(default_slot_body[0], Slot)
        assert not isinstance(default_slot_body[0], SlotBlock)

    def test_yield_named_produces_slot_with_name(self) -> None:
        """{% yield foo %} → Slot(name='foo')."""
        source = "{% def f() %}{% yield foo %}{% end %}"
        body, _ = self._parse_template(source)
        def_node = body[0]
        assert isinstance(def_node, Def)
        yield_node = def_node.body[0]
        assert isinstance(yield_node, Slot)
        assert yield_node.name == "foo"

    def test_yield_default_produces_slot_default(self) -> None:
        """{% yield %} → Slot(name='default')."""
        source = "{% def f() %}{% yield %}{% end %}"
        body, _ = self._parse_template(source)
        def_node = body[0]
        assert isinstance(def_node, Def)
        yield_node = def_node.body[0]
        assert isinstance(yield_node, Slot)
        assert yield_node.name == "default"

    def test_yield_parse_error_no_block_end(self) -> None:
        """{% yield foo produces a clear parse error."""
        from kida.environment.exceptions import TemplateSyntaxError

        env = Environment()
        with pytest.raises(TemplateSyntaxError):
            env.from_string("{% yield foo")

    def test_yield_in_call_body_lands_in_default_slot(self) -> None:
        """Yield Slot node ends up in CallBlock.slots['default']."""
        source = "{% def f() %}{% call g() %}{% yield x %}{% end %}{% end %}"
        body, _ = self._parse_template(source)
        def_node = body[0]
        assert isinstance(def_node, Def)
        call_node = def_node.body[0]
        assert isinstance(call_node, CallBlock)
        default_slot = call_node.slots.get("default", ())
        assert len(default_slot) == 1
        slot_node = default_slot[0]
        assert isinstance(slot_node, Slot)
        assert slot_node.name == "x"

    def test_yield_ast_matches_slot_in_def(self) -> None:
        """{% yield X %} and {% slot X %} (inside def) produce identical Slot nodes."""
        source_yield = "{% def f() %}{% yield foo %}{% end %}"
        source_slot = "{% def f() %}{% slot foo %}{% end %}"
        body_yield, _ = self._parse_template(source_yield)
        body_slot, _ = self._parse_template(source_slot)
        def_yield = body_yield[0]
        def_slot = body_slot[0]
        assert isinstance(def_yield, Def)
        assert isinstance(def_slot, Def)
        node_yield = def_yield.body[0]
        node_slot = def_slot.body[0]
        assert isinstance(node_yield, Slot)
        assert isinstance(node_slot, Slot)
        assert node_yield.name == node_slot.name == "foo"
