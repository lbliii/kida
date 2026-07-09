"""Tests for the component-inlining partial-evaluation phase."""

import pytest

from kida import Environment


def _env() -> Environment:
    return Environment(autoescape=False)


def _inline_env() -> Environment:
    return Environment(autoescape=False, inline_components=True)


class TestComponentInlining:
    """Small defs with constant args are inlined at compile time."""

    def test_simple_inline(self):
        """A def called with all-static args is inlined."""
        env = _inline_env()
        tmpl = env.from_string(
            '{% def greeting(name) %}Hello, {{ name }}!{% end %}{{ greeting("World") }}',
            static_context={"_placeholder": True},  # Need static_context to trigger
        )
        assert tmpl.render() == "Hello, World!"

    def test_inline_with_defaults(self):
        """Default params are resolved at compile time."""
        env = _inline_env()
        tmpl = env.from_string(
            '{% def tag(text, cls="default") %}'
            '<span class="{{ cls }}">{{ text }}</span>'
            "{% end %}"
            '{{ tag("hi") }}',
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == '<span class="default">hi</span>'

    def test_inline_with_static_context(self):
        """Def body references static context vars."""
        env = _inline_env()
        tmpl = env.from_string(
            "{% def header() %}<h1>{{ site_name }}</h1>{% end %}{{ header() }}",
            static_context={"site_name": "Kida"},
        )
        assert tmpl.render() == "<h1>Kida</h1>"

    def test_no_inline_with_slots(self):
        """Defs with slots are NOT inlined (too complex)."""
        env = _inline_env()
        tmpl = env.from_string(
            "{% def card(title) %}<div>{{ title }}{% slot %}</div>{% end %}"
            "{% call card('X') %}content{% end %}",
            static_context={"_placeholder": True},
        )
        # Should still work, just not inlined
        assert "X" in tmpl.render()

    def test_no_inline_without_flag(self):
        """Inlining is off by default."""
        env = _env()
        tmpl = env.from_string(
            '{% def greeting(name) %}Hello, {{ name }}!{% end %}{{ greeting("World") }}',
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == "Hello, World!"

    def test_inline_with_dynamic_args_skipped(self):
        """Calls with dynamic args are not inlined."""
        env = _inline_env()
        tmpl = env.from_string(
            "{% def greeting(name) %}Hello, {{ name }}!{% end %}{{ greeting(user_name) }}",
            static_context={"_placeholder": True},
        )
        # Dynamic arg — falls back to runtime
        assert tmpl.render(user_name="Alice") == "Hello, Alice!"


class TestComponentInliningEdgeCases:
    """Edge cases for component inlining."""

    def test_inline_with_default_args(self):
        """Def with default args — missing args filled from defaults."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            '{% def greet(name, greeting="Hello") %}{{ greeting }} {{ name }}{% end %}'
            '{% call greet("World") %}{% end %}',
            static_context={"_inline": True},
        )
        assert "Hello World" in tmpl.render()

    def test_no_inline_with_slots(self):
        """Def with slots is not inlined but still works."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            "{% def card(title) %}<div>{{ title }}{% slot %}</div>{% end %}"
            "{% call card('Hi') %} body{% end %}"
        )
        assert "Hi" in tmpl.render()
        assert "body" in tmpl.render()

    def test_no_inline_with_scoping_nodes(self):
        """Def with scoping nodes (set) is not inlined."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            "{% def calc(x) %}{% set y = x %}{{ y }}{% end %}{% call calc(5) %}{% end %}",
            static_context={"_inline": True},
        )
        assert tmpl.render() == "5"


class TestComponentInliningInternals:
    """Component inlining edge cases."""

    def test_inline_too_many_args(self):
        """Too many positional args — not inlined, raises at runtime."""
        from kida.environment.exceptions import TemplateRuntimeError

        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            "{% def greet(name) %}Hello {{ name }}{% end %}"
            "{% call greet('World', 'extra') %}{% end %}"
        )
        with pytest.raises(TemplateRuntimeError):
            tmpl.render()

    def test_inline_with_kwargs(self):
        """Keyword args in call — resolved for inlining."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            '{% def greet(name, greeting="Hi") %}{{ greeting }} {{ name }}{% end %}'
            '{% call greet(greeting="Hey", name="World") %}{% end %}',
            static_context={"_inline": True},
        )
        assert "Hey World" in tmpl.render()

    def test_no_inline_vararg(self):
        """Def with *args — not inlined but still works."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            "{% def greet(*names) %}Hello{% end %}{% call greet('a', 'b') %}{% end %}"
        )
        assert "Hello" in tmpl.render()
