"""Tests for kida modern operator features: ?|>, ??=, ?|"""

import pytest

from kida import Environment


@pytest.fixture
def env():
    return Environment()


# =============================================================================
# ?|> Safe Pipeline — None-propagating filter chains
# =============================================================================


class TestSafePipeline:
    def test_safe_pipeline_with_value(self, env: Environment):
        """Safe pipeline applies filters normally when value is not None."""
        tmpl = env.from_string("{{ 'hello' ?|> upper }}")
        assert tmpl.render() == "HELLO"

    def test_safe_pipeline_with_none(self, env: Environment):
        """Safe pipeline short-circuits on None — use ?? for empty fallback."""
        tmpl = env.from_string("{{ value ?|> upper ?? '' }}")
        assert tmpl.render(value=None) == ""

    def test_safe_pipeline_none_no_error(self, env: Environment):
        """Safe pipeline does not error when value is None (unlike regular |>)."""
        tmpl = env.from_string("{{ value ?|> upper }}")
        # None propagates through — renders as "None" (kida default for None output)
        assert tmpl.render(value=None) == "None"

    def test_safe_pipeline_chained(self, env: Environment):
        """Chained safe pipeline propagates None through all steps."""
        tmpl = env.from_string("{{ value ?|> upper ?|> trim ?? '' }}")
        assert tmpl.render(value=None) == ""
        assert tmpl.render(value="  hello  ") == "HELLO"

    def test_safe_pipeline_with_args(self, env: Environment):
        """Safe pipeline passes arguments to filters."""
        tmpl = env.from_string("{{ value ?|> truncate(5) ?? '' }}")
        assert tmpl.render(value=None) == ""
        assert tmpl.render(value="hello world") == "he..."

    def test_safe_pipeline_with_optional_chaining(self, env: Environment):
        """Safe pipeline combined with ?. and ?? for full safe navigation."""
        tmpl = env.from_string("{{ user?.name ?|> upper ?? '' }}")
        assert tmpl.render(user=None) == ""
        assert tmpl.render(user={"name": "alice"}) == "ALICE"

    def test_safe_pipeline_preserves_falsy(self, env: Environment):
        """Safe pipeline does not short-circuit on falsy non-None values."""
        tmpl = env.from_string("{{ value ?|> string }}")
        assert tmpl.render(value=0) == "0"
        assert tmpl.render(value="") == ""
        assert tmpl.render(value=False) == "False"


# =============================================================================
# ??= Nullish Assignment — assign only if undefined or None
# =============================================================================


class TestNullishAssignment:
    def test_let_nullish_assign_undefined(self, env: Environment):
        """??= assigns when variable is not yet defined."""
        tmpl = env.from_string(
            """
{% let x ??= "default" %}
{{ x }}
""".strip()
        )
        assert tmpl.render().strip() == "default"

    def test_let_nullish_assign_none(self, env: Environment):
        """??= assigns when variable is explicitly None."""
        tmpl = env.from_string(
            """
{% let x = none %}
{% let x ??= "default" %}
{{ x }}
""".strip()
        )
        assert tmpl.render().strip() == "default"

    def test_let_nullish_assign_preserves_existing(self, env: Environment):
        """??= does NOT overwrite an existing non-None value."""
        tmpl = env.from_string(
            """
{% let x = "original" %}
{% let x ??= "default" %}
{{ x }}
""".strip()
        )
        assert tmpl.render().strip() == "original"

    def test_let_nullish_assign_preserves_falsy(self, env: Environment):
        """??= does NOT overwrite falsy non-None values (0, '', False)."""
        tmpl = env.from_string(
            """
{% let x = 0 %}
{% let x ??= 42 %}
{{ x }}
""".strip()
        )
        assert tmpl.render().strip() == "0"

    def test_let_nullish_assign_from_context(self, env: Environment):
        """??= respects values passed in the render context."""
        tmpl = env.from_string(
            """
{% let title ??= "Untitled" %}
{{ title }}
""".strip()
        )
        assert tmpl.render(title="My Page").strip() == "My Page"
        assert tmpl.render().strip() == "Untitled"

    def test_set_nullish_assign(self, env: Environment):
        """??= works with {% set %} (block-scoped)."""
        tmpl = env.from_string(
            """
{% set x ??= "default" %}
{{ x }}
""".strip()
        )
        assert tmpl.render().strip() == "default"

    def test_export_nullish_assign(self, env: Environment):
        """??= works with {% export %} (scope promotion)."""
        tmpl = env.from_string(
            """
{% let result = "first" %}
{% for item in [1, 2, 3] %}
  {% export result ??= item %}
{% end %}
{{ result }}
""".strip()
        )
        # result is already "first", so ??= should not overwrite
        assert tmpl.render().strip() == "first"

    def test_promote_nullish_assign(self, env: Environment):
        """??= works with {% promote %} alias."""
        tmpl = env.from_string(
            """
{% for item in [1, 2, 3] %}
  {% promote first_item ??= item %}
{% end %}
{{ first_item }}
""".strip()
        )
        # first_item is undefined on first iteration, so ??= sets it to 1
        # subsequent iterations: first_item is 1, so ??= is a no-op
        assert tmpl.render().strip() == "1"

    def test_nullish_assign_template_inheritance(self, env: Environment):
        """??= is ideal for setting defaults in child templates."""
        tmpl = env.from_string(
            """
{% let page_title ??= "Default Title" %}
{% let show_sidebar ??= true %}
Title: {{ page_title }}, Sidebar: {{ show_sidebar }}
""".strip()
        )
        assert tmpl.render(page_title="Custom").strip() == "Title: Custom, Sidebar: True"
        assert tmpl.render().strip() == "Title: Default Title, Sidebar: True"


# =============================================================================
# ?| Optional Filter — skip filter if value is None
# =============================================================================


class TestOptionalFilter:
    def test_optional_filter_with_value(self, env: Environment):
        """?| applies filter normally when value is not None."""
        tmpl = env.from_string("{{ 'hello' ?| upper }}")
        assert tmpl.render() == "HELLO"

    def test_optional_filter_with_none(self, env: Environment):
        """?| skips the filter when value is None — use ?? for fallback."""
        tmpl = env.from_string("{{ value ?| upper ?? '' }}")
        assert tmpl.render(value=None) == ""

    def test_optional_filter_none_no_error(self, env: Environment):
        """?| does not error when value is None (unlike regular |)."""
        tmpl = env.from_string("{{ value ?| upper }}")
        # None propagates — renders as "None" (kida default)
        assert tmpl.render(value=None) == "None"

    def test_optional_filter_chained(self, env: Environment):
        """?| can be chained — each step checks for None independently."""
        tmpl = env.from_string("{{ value ?| upper ?| trim ?? '' }}")
        assert tmpl.render(value=None) == ""
        assert tmpl.render(value="  hello  ") == "HELLO"

    def test_optional_filter_with_args(self, env: Environment):
        """?| passes arguments to the filter."""
        tmpl = env.from_string("{{ value ?| truncate(5) ?? '' }}")
        assert tmpl.render(value=None) == ""
        assert tmpl.render(value="hello world") == "he..."

    def test_optional_filter_with_null_coalesce(self, env: Environment):
        """?| combines with ?? for clean defaults."""
        tmpl = env.from_string("{{ user?.name ?| upper ?? 'ANONYMOUS' }}")
        assert tmpl.render(user=None) == "ANONYMOUS"
        assert tmpl.render(user={"name": "alice"}) == "ALICE"

    def test_optional_filter_preserves_falsy(self, env: Environment):
        """?| does not short-circuit on falsy non-None values."""
        tmpl = env.from_string("{{ value ?| string }}")
        assert tmpl.render(value=0) == "0"
        assert tmpl.render(value=False) == "False"

    def test_optional_filter_with_optional_chaining(self, env: Environment):
        """?| after ?. creates a fully safe expression chain."""
        tmpl = env.from_string("{{ config?.debug ?| string ?? 'unset' }}")
        assert tmpl.render(config=None) == "unset"
        assert tmpl.render(config={"debug": True}) == "True"
        assert tmpl.render(config={"debug": False}) == "False"
