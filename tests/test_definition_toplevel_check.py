"""Compile-time check + runtime hint for top-level {% def %} / {% region %}.

Covers feedback K-TPL-004: regions and defs must be declared at the
template's top level so render_block() dispatch and _globals_setup can
bind them. Also verifies that UndefinedError swaps the generic hint for
a more directed message when a missing ctx name matches a known
definition.
"""

from __future__ import annotations

import pytest

from kida import DictLoader, Environment
from kida.exceptions import (
    ErrorCode,
    TemplateSyntaxError,
    UndefinedError,
)


def _env(**templates: str) -> Environment:
    return Environment(loader=DictLoader(templates))


class TestRegionNestingRejected:
    """{% region %} must be top-level — nesting in control flow errors."""

    @pytest.mark.parametrize(
        "wrapper_open,wrapper_close",
        [
            ("{% if cond %}", "{% end %}"),
            ("{% for x in items %}", "{% end %}"),
            ('{% provide color = "red" %}', "{% end %}"),
            ('{% with x = "y" %}', "{% end %}"),
            ("{% try %}", "{% fallback %}fb{% end %}"),
            ("{% match v %}{% case _ %}", "{% end %}"),
            ('{% cache "k" %}', "{% end %}"),
            ('{% push "head" %}', "{% end %}"),
            ("{% capture x %}", "{% end %}"),
            ("{% spaceless %}", "{% end %}"),
        ],
    )
    def test_region_in_scoped_parent_raises(self, wrapper_open: str, wrapper_close: str) -> None:
        env = _env(
            page=(
                f"{wrapper_open}"
                "{% region sidebar(current_path='/') %}<nav/>{% end %}"
                f"{wrapper_close}"
            ),
        )
        with pytest.raises(TemplateSyntaxError) as exc:
            env.get_template("page")
        assert exc.value.code is ErrorCode.DEFINITION_NOT_TOPLEVEL
        assert "region sidebar" in str(exc.value)
        assert "top level" in str(exc.value)

    def test_region_in_nested_for_inside_if_raises(self) -> None:
        env = _env(
            page=(
                "{% if a %}"
                "  {% for x in items %}"
                "    {% region sidebar() %}<nav/>{% end %}"
                "  {% end %}"
                "{% end %}"
            ),
        )
        with pytest.raises(TemplateSyntaxError) as exc:
            env.get_template("page")
        assert exc.value.code is ErrorCode.DEFINITION_NOT_TOPLEVEL


class TestDefNestingRejected:
    """{% def %} nested in control flow errors with the same code."""

    def test_def_in_if_raises(self) -> None:
        env = _env(
            page=("{% if cond %}{% def helper() %}hi{% end %}{% end %}"),
        )
        with pytest.raises(TemplateSyntaxError) as exc:
            env.get_template("page")
        assert exc.value.code is ErrorCode.DEFINITION_NOT_TOPLEVEL
        assert "def helper" in str(exc.value)

    def test_def_in_provide_raises(self) -> None:
        env = _env(
            page=('{% provide color = "red" %}{% def helper() %}hi{% end %}{% end %}'),
        )
        with pytest.raises(TemplateSyntaxError) as exc:
            env.get_template("page")
        assert exc.value.code is ErrorCode.DEFINITION_NOT_TOPLEVEL


class TestAllowedNestings:
    """Top-level and structural nesting still compile cleanly."""

    def test_top_level_region_compiles(self) -> None:
        env = _env(
            page='{% region sidebar(current_path="/") %}<nav/>{% end %}',
        )
        # Should not raise.
        env.get_template("page")

    def test_top_level_def_compiles(self) -> None:
        env = _env(
            page="{% def card(title) %}<h3>{{ title }}</h3>{% end %}",
        )
        env.get_template("page")

    def test_def_inside_def_allowed(self) -> None:
        # Nested defs aren't render_block targets — they aren't restricted
        # by the same rule. Compile must succeed.
        env = _env(
            page=("{% def outer() %}{% def inner() %}hi{% end %}{% end %}"),
        )
        env.get_template("page")

    def test_region_inside_block_allowed(self) -> None:
        # See test_render_block.test_region_with_block_streaming — this is
        # an existing supported pattern (block dispatch forwards to region).
        env = _env(
            layout=(
                "{% block content %}"
                "{% region panel() %}"
                "{% block inner %}DEFAULT{% endblock %}"
                "{% end %}"
                "{{ panel() }}"
                "{% endblock %}"
            ),
        )
        env.get_template("layout")


class TestUndefinedHintForDeclaredDefinitions:
    """UndefinedError swaps the generic hint when name matches a definition."""

    def test_hint_points_to_top_level_when_region_name_missing(self) -> None:
        # 'sidebar' is declared as a region but render_block dispatch is
        # asked for it on a context that doesn't have it bound. Simulate
        # the runtime miss by referencing the name directly inside a body
        # that runs before the region assignment line.
        env = _env(
            page=(
                "{{ sidebar }}"  # Reference before declaration — undefined at this point
                '{% region sidebar(current_path="/") %}<nav/>{% end %}'
            ),
        )
        template = env.get_template("page")
        with pytest.raises(UndefinedError) as exc:
            template.render()
        msg = str(exc.value)
        assert "Did you declare" in msg
        assert "{% region sidebar %}" in msg
        # The generic hint should NOT appear when the directed hint fires.
        assert "| default(" not in msg

    def test_hint_falls_back_to_default_for_unrelated_names(self) -> None:
        env = _env(page="{{ unrelated_var }}")
        template = env.get_template("page")
        with pytest.raises(UndefinedError) as exc:
            template.render()
        msg = str(exc.value)
        assert "Did you declare" not in msg
        # Generic hint still suggests | default('').
        assert "| default(" in msg
