"""Async rendering tests for Kida template engine.

Kida templates are synchronous. The `render_async()` method is a convenience
wrapper that runs sync rendering in a thread pool, allowing use from async code
without blocking the event loop.

Note: Async filters, globals, and callables are NOT supported. Load async data
before rendering and pass it as context.
"""

from __future__ import annotations

import asyncio

import pytest

from kida import Environment


class TestAsyncRenderWrapper:
    """Test render_async() as a thread-pool wrapper for sync render."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    @pytest.mark.asyncio
    async def test_async_render_basic(self, env: Environment) -> None:
        """render_async() produces same output as render()."""
        tmpl = env.from_string("Hello {{ name }}")

        sync_result = tmpl.render(name="World")
        async_result = await tmpl.render_async(name="World")

        assert sync_result == async_result == "Hello World"

    @pytest.mark.asyncio
    async def test_async_render_with_expressions(self, env: Environment) -> None:
        """Expressions work via render_async()."""
        tmpl = env.from_string("{{ x }} + {{ y }} = {{ x + y }}")

        result = await tmpl.render_async(x=1, y=2)
        assert result == "1 + 2 = 3"

    @pytest.mark.asyncio
    async def test_async_render_with_filters(self, env: Environment) -> None:
        """Sync filters work via render_async()."""
        tmpl = env.from_string("{{ name | upper }}")

        result = await tmpl.render_async(name="world")
        assert result == "WORLD"

    @pytest.mark.asyncio
    async def test_async_render_with_loops(self, env: Environment) -> None:
        """For loops work via render_async()."""
        tmpl = env.from_string("{% for x in items %}{{ x }}{% endfor %}")

        result = await tmpl.render_async(items=[1, 2, 3])
        assert result == "123"

    @pytest.mark.asyncio
    async def test_async_render_with_conditionals(self, env: Environment) -> None:
        """Conditionals work via render_async()."""
        tmpl = env.from_string("{% if show %}visible{% endif %}")

        result = await tmpl.render_async(show=True)
        assert result == "visible"

        result = await tmpl.render_async(show=False)
        assert result == ""


class TestAsyncConcurrency:
    """Test concurrent async rendering (thread-pool isolation)."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    @pytest.mark.asyncio
    async def test_concurrent_renders_same_template(self, env: Environment) -> None:
        """Multiple concurrent renders of same template are isolated."""
        tmpl = env.from_string("{{ name }}")

        tasks = [tmpl.render_async(name=f"User{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            assert result == f"User{i}"

    @pytest.mark.asyncio
    async def test_concurrent_renders_different_templates(self, env: Environment) -> None:
        """Concurrent renders of different templates."""
        tmpls = [env.from_string(f"Template {i}: {{{{ x }}}}") for i in range(5)]

        tasks = [t.render_async(x=i) for i, t in enumerate(tmpls)]
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            assert f"Template {i}:" in result
            assert str(i) in result


class TestAsyncWithInheritance:
    """Test render_async() with template inheritance."""

    @pytest.mark.asyncio
    async def test_async_render_with_extends(self) -> None:
        """Template inheritance works via render_async()."""
        from kida import DictLoader

        loader = DictLoader(
            {
                "base.html": "<html>{% block content %}{% endblock %}</html>",
            }
        )
        env = Environment(loader=loader)

        tmpl = env.from_string("""
{% extends "base.html" %}
{% block content %}{{ name }}{% endblock %}
""")

        result = await tmpl.render_async(name="World")
        assert "<html>" in result
        assert "World" in result

    @pytest.mark.asyncio
    async def test_async_render_with_include(self) -> None:
        """Include works via render_async()."""
        from kida import DictLoader

        loader = DictLoader(
            {
                "partial.html": "{{ name }}",
            }
        )
        env = Environment(loader=loader)

        tmpl = env.from_string('{% include "partial.html" %}')

        result = await tmpl.render_async(name="World")
        assert result == "World"


class TestAsyncWithMacros:
    """Test render_async() with macros and defs."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    @pytest.mark.asyncio
    async def test_def_with_async_render(self, env: Environment) -> None:
        """Def blocks work via render_async()."""
        tmpl = env.from_string("""
{% def greet(name) %}Hello {{ name }}{% enddef %}
{{ greet('World') }}
""")

        result = await tmpl.render_async()
        assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_def_with_args(self, env: Environment) -> None:
        """Def with arguments works via render_async()."""
        tmpl = env.from_string("""
{% def greet(name, greeting="Hi") %}{{ greeting }} {{ name }}!{% enddef %}
{{ greet('World') }} {{ greet('Alice', 'Hello') }}
""")

        result = await tmpl.render_async()
        assert "Hi World!" in result
        assert "Hello Alice!" in result


class TestAsyncWithCache:
    """Test render_async() with cache blocks."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    @pytest.mark.asyncio
    async def test_cache_with_async_render(self, env: Environment) -> None:
        """Cache blocks work via render_async()."""
        tmpl = env.from_string("""
{% cache 'test_key' %}
cached content
{% endcache %}
""")

        result = await tmpl.render_async()
        assert "cached content" in result


class TestAsyncDataPattern:
    """Test the recommended pattern: load async data before rendering."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    @pytest.mark.asyncio
    async def test_load_async_data_then_render(self, env: Environment) -> None:
        """Recommended pattern: await data, then render."""

        async def fetch_user() -> dict[str, str]:
            await asyncio.sleep(0)  # Simulate async I/O
            return {"name": "Alice", "role": "Admin"}

        # Load async data BEFORE rendering
        user = await fetch_user()

        tmpl = env.from_string("{{ user.name }} ({{ user.role }})")
        result = await tmpl.render_async(user=user)

        assert result == "Alice (Admin)"

    @pytest.mark.asyncio
    async def test_parallel_data_loading_then_render(self, env: Environment) -> None:
        """Load multiple async sources in parallel, then render."""

        async def fetch_users() -> list[str]:
            await asyncio.sleep(0)
            return ["Alice", "Bob", "Charlie"]

        async def fetch_title() -> str:
            await asyncio.sleep(0)
            return "Team Members"

        # Load all async data in parallel
        users, title = await asyncio.gather(fetch_users(), fetch_title())

        tmpl = env.from_string("""
{{ title }}:
{% for user in users %}{{ user }}{% if not loop.last %}, {% endif %}{% endfor %}
""")
        result = await tmpl.render_async(users=users, title=title)

        assert "Team Members" in result
        assert "Alice" in result
        assert "Bob" in result
        assert "Charlie" in result
