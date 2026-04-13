"""Tests for DefMetadata introspection API and component call stack (Sprint 1).

Validates:
- template.def_metadata() and template.list_defs() (Sprint 1.1 + 1.2)
- Component call stack in error reporting (Sprint 1.3)
"""

from __future__ import annotations

import pytest

from kida import Environment
from kida.analysis.metadata import DefMetadata, DefParamInfo
from kida.exceptions import UndefinedError


@pytest.fixture
def env():
    return Environment()


class TestDefMetadata:
    """template.def_metadata() returns correct DefMetadata for defs."""

    def test_basic_def(self, env):
        """Simple def with no params or slots."""
        t = env.from_string("{% def greeting() %}Hello{% end %}")
        meta = t.def_metadata()
        assert "greeting" in meta
        dm = meta["greeting"]
        assert dm.name == "greeting"
        assert dm.params == ()
        assert dm.slots == ()
        assert dm.has_default_slot is False

    def test_def_with_typed_params(self, env):
        """Def with type-annotated parameters."""
        t = env.from_string(
            "{% def card(title: str, count: int) %}<div>{{ title }} ({{ count }})</div>{% end %}"
        )
        meta = t.def_metadata()
        card = meta["card"]
        assert len(card.params) == 2

        title_param = card.params[0]
        assert title_param.name == "title"
        assert title_param.annotation == "str"
        assert title_param.is_required is True
        assert title_param.has_default is False

        count_param = card.params[1]
        assert count_param.name == "count"
        assert count_param.annotation == "int"
        assert count_param.is_required is True

    def test_def_with_defaults(self, env):
        """Def with default parameter values."""
        t = env.from_string(
            '{% def button(label: str, variant: str = "primary", disabled: bool = False) %}'
            "<button>{{ label }}</button>"
            "{% end %}"
        )
        meta = t.def_metadata()
        btn = meta["button"]
        assert len(btn.params) == 3

        assert btn.params[0].name == "label"
        assert btn.params[0].is_required is True
        assert btn.params[0].has_default is False

        assert btn.params[1].name == "variant"
        assert btn.params[1].is_required is False
        assert btn.params[1].has_default is True

        assert btn.params[2].name == "disabled"
        assert btn.params[2].is_required is False
        assert btn.params[2].has_default is True

    def test_def_with_default_slot(self, env):
        """Def with an unnamed (default) slot."""
        t = env.from_string("{% def wrapper() %}<div>{% slot %}</div>{% end %}")
        meta = t.def_metadata()
        assert meta["wrapper"].has_default_slot is True
        assert meta["wrapper"].slots == ()

    def test_def_with_named_slots(self, env):
        """Def with named slots."""
        t = env.from_string(
            "{% def card(title) %}"
            "<div><h3>{{ title }}</h3>"
            "<div>{% slot header_actions %}</div>"
            "<div>{% slot footer %}</div>"
            "<div>{% slot %}</div>"
            "</div>"
            "{% end %}"
        )
        meta = t.def_metadata()
        card = meta["card"]
        assert "header_actions" in card.slots
        assert "footer" in card.slots
        assert card.has_default_slot is True

    def test_multiple_defs(self, env):
        """Multiple defs in one template."""
        t = env.from_string(
            "{% def a() %}A{% end %}{% def b(x) %}B{% end %}{% def c(x, y: int = 0) %}C{% end %}"
        )
        meta = t.def_metadata()
        assert set(meta.keys()) == {"a", "b", "c"}
        assert len(meta["a"].params) == 0
        assert len(meta["b"].params) == 1
        assert len(meta["c"].params) == 2

    def test_no_defs(self, env):
        """Template with no defs returns empty dict."""
        t = env.from_string("<p>Hello {{ name }}</p>")
        assert t.def_metadata() == {}

    def test_def_with_untyped_params(self, env):
        """Def with untyped parameters."""
        t = env.from_string("{% def greet(name, greeting) %}{{ greeting }}, {{ name }}!{% end %}")
        meta = t.def_metadata()
        greet = meta["greet"]
        assert greet.params[0].annotation is None
        assert greet.params[1].annotation is None

    def test_caching(self, env):
        """def_metadata() is cached after first call."""
        t = env.from_string("{% def x() %}X{% end %}")
        meta1 = t.def_metadata()
        meta2 = t.def_metadata()
        assert meta1 is meta2

    def test_no_ast_returns_empty(self, env):
        """When AST is not preserved, returns empty dict."""
        t = env.from_string("{% def x() %}X{% end %}")
        t._optimized_ast = None
        t._def_metadata_cache = None
        assert t.def_metadata() == {}


class TestListDefs:
    """template.list_defs() returns correct def names."""

    def test_list_defs(self, env):
        t = env.from_string("{% def card() %}C{% end %}{% def button() %}B{% end %}")
        names = t.list_defs()
        assert set(names) == {"card", "button"}

    def test_list_defs_empty(self, env):
        t = env.from_string("<p>No defs here</p>")
        assert t.list_defs() == []


class TestDefParamInfo:
    """DefParamInfo dataclass correctness."""

    def test_frozen(self):
        p = DefParamInfo(name="x", annotation="str")
        with pytest.raises(AttributeError):
            p.name = "y"

    def test_defaults(self):
        p = DefParamInfo(name="x")
        assert p.annotation is None
        assert p.has_default is False
        assert p.is_required is True


class TestDefMetadataDataclass:
    """DefMetadata dataclass correctness."""

    def test_frozen(self):
        dm = DefMetadata(name="card")
        with pytest.raises(AttributeError):
            dm.name = "button"

    def test_defaults(self):
        dm = DefMetadata(name="card")
        assert dm.template_name is None
        assert dm.lineno == 0
        assert dm.params == ()
        assert dm.slots == ()
        assert dm.has_default_slot is False
        assert dm.depends_on == frozenset()


class TestComponentCallStack:
    """Component call stack in error reporting (Sprint 1.3)."""

    def test_single_def_error_shows_component(self, env):
        """Error inside a single def shows the def in component stack."""
        t = env.from_string(
            "{% def card() %}{{ missing_var }}{% end %}{{ card() }}",
            name="page.html",
        )
        with pytest.raises(UndefinedError) as exc_info:
            t.render()
        err = exc_info.value
        assert len(err.component_stack) == 1
        assert err.component_stack[0][2] == "card"

    def test_nested_def_error_shows_call_chain(self, env):
        """Error in nested defs shows the full call chain."""
        t = env.from_string(
            "{% def inner() %}{{ boom }}{% end %}"
            "{% def outer() %}{{ inner() }}{% end %}"
            "{{ outer() }}",
            name="test.html",
        )
        with pytest.raises(UndefinedError) as exc_info:
            t.render()
        err = exc_info.value
        assert len(err.component_stack) == 2
        assert err.component_stack[0][2] == "outer"
        assert err.component_stack[1][2] == "inner"

    def test_no_component_stack_outside_def(self, env):
        """Errors outside defs have empty component stack."""
        t = env.from_string("{{ nope }}", name="test.html")
        with pytest.raises(UndefinedError) as exc_info:
            t.render()
        assert exc_info.value.component_stack == []

    def test_component_stack_in_error_message(self, env):
        """Component stack appears in the formatted error message."""
        t = env.from_string(
            "{% def widget() %}{{ x }}{% end %}{{ widget() }}",
            name="page.html",
        )
        with pytest.raises(UndefinedError) as exc_info:
            t.render()
        msg = str(exc_info.value)
        assert "Component stack:" in msg
        assert "widget()" in msg

    def test_component_stack_cleaned_on_success(self, env):
        """Component stack is empty after successful def calls."""
        t = env.from_string(
            "{% def ok() %}hi{% end %}{{ ok() }}{{ nope }}",
            name="test.html",
        )
        with pytest.raises(UndefinedError) as exc_info:
            t.render()
        # The error is outside the def, so component stack should be empty
        assert exc_info.value.component_stack == []
