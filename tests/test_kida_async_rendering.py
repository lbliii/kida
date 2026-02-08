"""Native async rendering tests for Kida template engine.

Tests for {% async for %}, {{ await }}, render_stream_async(),
render_block_stream_async(), AsyncLoopContext, and related error paths.

Part of RFC: rfc-async-rendering.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from kida import DictLoader, Environment
from kida.environment.exceptions import TemplateRuntimeError, TemplateSyntaxError
from kida.template.loop_context import AsyncLoopContext

# ─────────────────────────────────────────────────────────────────────────────
# Helpers — mock async iterables for testing
# ─────────────────────────────────────────────────────────────────────────────


async def async_range(n: int) -> AsyncIterator[int]:
    """Async generator that yields 0..n-1."""
    for i in range(n):
        yield i


async def async_items(items: list) -> AsyncIterator:
    """Async generator that yields items from a list."""
    for item in items:
        yield item


async def async_empty() -> AsyncIterator:
    """Async generator that yields nothing."""
    return
    yield


async def async_coroutine_value(value: str) -> str:
    """A coroutine that returns a string after a tiny delay."""
    return value


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def env() -> Environment:
    return Environment()


@pytest.fixture
def env_with_loader() -> Environment:
    loader = DictLoader({
        "base.html": (
            "<html><body>{% block content %}{% endblock %}</body></html>"
        ),
        "sync_partial.html": "<p>sync partial</p>",
    })
    return Environment(loader=loader)


# ─────────────────────────────────────────────────────────────────────────────
# Parsing tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncForParsing:
    """Verify {% async for %} parses to AsyncFor node."""

    def test_parse_async_for_basic(self, env: Environment) -> None:
        """Basic async for loop parses without error."""
        tmpl = env.from_string(
            "{% async for item in items %}{{ item }}{% end %}"
        )
        assert tmpl.is_async is True

    def test_parse_async_for_with_inline_if(self, env: Environment) -> None:
        """Async for with inline if filter parses correctly."""
        tmpl = env.from_string(
            "{% async for x in items if x %}{{ x }}{% end %}"
        )
        assert tmpl.is_async is True

    def test_parse_async_for_with_empty(self, env: Environment) -> None:
        """Async for with {% empty %} clause parses correctly."""
        tmpl = env.from_string(
            "{% async for x in items %}{{ x }}{% empty %}none{% end %}"
        )
        assert tmpl.is_async is True

    def test_parse_async_for_with_tuple_unpack(self, env: Environment) -> None:
        """Async for with tuple unpacking parses correctly."""
        tmpl = env.from_string(
            "{% async for k, v in items %}{{ k }}={{ v }}{% end %}"
        )
        assert tmpl.is_async is True

    def test_sync_template_not_async(self, env: Environment) -> None:
        """A template without async constructs has is_async=False."""
        tmpl = env.from_string("{% for x in items %}{{ x }}{% end %}")
        assert tmpl.is_async is False


# ─────────────────────────────────────────────────────────────────────────────
# AsyncLoopContext tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncLoopContext:
    """Verify AsyncLoopContext provides index-forward variables and errors on others."""

    def test_advance_updates_index(self) -> None:
        ctx = AsyncLoopContext()
        ctx.advance("a")
        assert ctx.index == 1
        assert ctx.index0 == 0
        assert ctx.first is True

        ctx.advance("b")
        assert ctx.index == 2
        assert ctx.index0 == 1
        assert ctx.first is False

    def test_previtem(self) -> None:
        ctx = AsyncLoopContext()
        ctx.advance("a")
        assert ctx.previtem is None

        ctx.advance("b")
        assert ctx.previtem == "a"

        ctx.advance("c")
        assert ctx.previtem == "b"

    def test_cycle(self) -> None:
        ctx = AsyncLoopContext()
        ctx.advance("x")
        assert ctx.cycle("odd", "even") == "odd"
        ctx.advance("y")
        assert ctx.cycle("odd", "even") == "even"
        ctx.advance("z")
        assert ctx.cycle("odd", "even") == "odd"

    def test_last_raises(self) -> None:
        ctx = AsyncLoopContext()
        ctx.advance("a")
        with pytest.raises(TemplateRuntimeError, match=r"loop\.last"):
            _ = ctx.last

    def test_length_raises(self) -> None:
        ctx = AsyncLoopContext()
        ctx.advance("a")
        with pytest.raises(TemplateRuntimeError, match=r"loop\.length"):
            _ = ctx.length

    def test_revindex_raises(self) -> None:
        ctx = AsyncLoopContext()
        ctx.advance("a")
        with pytest.raises(TemplateRuntimeError, match=r"loop\.revindex"):
            _ = ctx.revindex

    def test_revindex0_raises(self) -> None:
        ctx = AsyncLoopContext()
        ctx.advance("a")
        with pytest.raises(TemplateRuntimeError, match=r"loop\.revindex0"):
            _ = ctx.revindex0

    def test_nextitem_raises(self) -> None:
        ctx = AsyncLoopContext()
        ctx.advance("a")
        with pytest.raises(TemplateRuntimeError, match=r"loop\.nextitem"):
            _ = ctx.nextitem

    def test_repr(self) -> None:
        ctx = AsyncLoopContext()
        ctx.advance("x")
        assert "AsyncLoopContext" in repr(ctx)


# ─────────────────────────────────────────────────────────────────────────────
# render_stream_async() tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRenderStreamAsync:
    """Test native async streaming rendering."""

    @pytest.mark.asyncio
    async def test_basic_async_for(self, env: Environment) -> None:
        """{% async for %} iterates over async iterable and streams output."""
        tmpl = env.from_string(
            "{% async for i in items %}{{ i }}{% end %}"
        )
        chunks = [chunk async for chunk in tmpl.render_stream_async(items=async_range(3))]
        result = "".join(chunks)
        assert "0" in result
        assert "1" in result
        assert "2" in result

    @pytest.mark.asyncio
    async def test_async_for_with_surrounding_content(self, env: Environment) -> None:
        """Async for-loop within static content."""
        tmpl = env.from_string(
            "<ul>{% async for x in items %}<li>{{ x }}</li>{% end %}</ul>"
        )
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                items=async_items(["a", "b"])
            )
        ]
        result = "".join(chunks)
        assert "<ul>" in result
        assert "<li>a</li>" in result
        assert "<li>b</li>" in result
        assert "</ul>" in result

    @pytest.mark.asyncio
    async def test_async_for_empty_clause(self, env: Environment) -> None:
        """{% empty %} renders when async iterable yields nothing."""
        tmpl = env.from_string(
            "{% async for x in items %}{{ x }}{% empty %}empty{% end %}"
        )
        chunks = [chunk async for chunk in tmpl.render_stream_async(items=async_empty())]
        result = "".join(chunks)
        assert result == "empty"

    @pytest.mark.asyncio
    async def test_async_for_inline_if(self, env: Environment) -> None:
        """Inline if filter skips items that don't match."""
        tmpl = env.from_string(
            "{% async for x in items if x %}{{ x }}{% end %}"
        )
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                items=async_items(["a", "", "c"])
            )
        ]
        result = "".join(chunks)
        assert "a" in result
        assert "c" in result
        # Empty string item should be filtered out
        assert result.count("a") == 1

    @pytest.mark.asyncio
    async def test_async_for_loop_index(self, env: Environment) -> None:
        """loop.index and loop.first work in async for-loops."""
        tmpl = env.from_string(
            "{% async for x in items %}"
            "{{ loop.index }}:{{ x }}"
            "{% if loop.first %}!{% end %} "
            "{% end %}"
        )
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                items=async_items(["a", "b", "c"])
            )
        ]
        result = "".join(chunks)
        assert "1:a!" in result
        assert "2:b" in result
        assert "3:c" in result

    @pytest.mark.asyncio
    async def test_sync_template_via_async_stream(self, env: Environment) -> None:
        """render_stream_async() works on sync templates (wraps sync stream)."""
        tmpl = env.from_string("Hello {{ name }}")
        chunks = [chunk async for chunk in tmpl.render_stream_async(name="World")]
        result = "".join(chunks)
        assert result == "Hello World"


# ─────────────────────────────────────────────────────────────────────────────
# render_block_stream_async() tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRenderBlockStreamAsync:
    """Test async block streaming."""

    @pytest.mark.asyncio
    async def test_async_block_stream(self, env: Environment) -> None:
        """render_block_stream_async() streams a single async block."""
        tmpl = env.from_string(
            "{% block content %}"
            "{% async for x in items %}{{ x }}{% end %}"
            "{% endblock %}"
        )
        chunks = [
            chunk
            async for chunk in tmpl.render_block_stream_async(
                "content", items=async_items(["a", "b"])
            )
        ]
        result = "".join(chunks)
        assert "a" in result
        assert "b" in result

    @pytest.mark.asyncio
    async def test_block_not_found_raises(self, env: Environment) -> None:
        """Missing block raises KeyError."""
        tmpl = env.from_string(
            "{% block content %}hello{% endblock %}"
        )
        with pytest.raises(KeyError, match="nonexistent"):
            async for _ in tmpl.render_block_stream_async("nonexistent"):
                pass


# ─────────────────────────────────────────────────────────────────────────────
# {{ await }} tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAwaitExpression:
    """Test {{ await expr }} inline awaitable resolution."""

    @pytest.mark.asyncio
    async def test_await_coroutine(self, env: Environment) -> None:
        """{{ await expr }} resolves a coroutine inline."""
        tmpl = env.from_string("Result: {{ await coro }}")
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                coro=async_coroutine_value("hello")
            )
        ]
        result = "".join(chunks)
        assert "Result: hello" in result

    @pytest.mark.asyncio
    async def test_await_marks_template_async(self, env: Environment) -> None:
        """A template with {{ await }} is flagged as async."""
        tmpl = env.from_string("{{ await x }}")
        assert tmpl.is_async is True


# ─────────────────────────────────────────────────────────────────────────────
# Template inheritance tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncInheritance:
    """Test async blocks in child templates with sync parents."""

    @pytest.mark.asyncio
    async def test_child_async_block_with_sync_parent(
        self, env_with_loader: Environment,
    ) -> None:
        """Child template overrides parent block with async content."""
        env_with_loader.loader._mapping["async_child.html"] = (  # type: ignore[union-attr]
            '{% extends "base.html" %}'
            "{% block content %}"
            "{% async for x in items %}{{ x }}{% end %}"
            "{% endblock %}"
        )
        tmpl = env_with_loader.get_template("async_child.html")
        assert tmpl.is_async is True

        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                items=async_items(["hello"])
            )
        ]
        result = "".join(chunks)
        assert "hello" in result
        assert "<html>" in result
        assert "</html>" in result


# ─────────────────────────────────────────────────────────────────────────────
# Include tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncInclude:
    """Test include behavior across sync/async boundaries."""

    @pytest.mark.asyncio
    async def test_async_template_includes_sync(
        self, env_with_loader: Environment,
    ) -> None:
        """Async template can include a sync partial."""
        env_with_loader.loader._mapping["async_page.html"] = (  # type: ignore[union-attr]
            '{% include "sync_partial.html" %}'
            "{% async for x in items %}{{ x }}{% end %}"
        )
        tmpl = env_with_loader.get_template("async_page.html")
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                items=async_items(["x"])
            )
        ]
        result = "".join(chunks)
        assert "sync partial" in result
        assert "x" in result


# ─────────────────────────────────────────────────────────────────────────────
# Sync guard tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSyncGuard:
    """Test that sync render methods reject async templates."""

    def test_render_rejects_async_template(self, env: Environment) -> None:
        """render() on async template raises TemplateRuntimeError."""
        tmpl = env.from_string(
            "{% async for x in items %}{{ x }}{% end %}"
        )
        with pytest.raises(TemplateRuntimeError, match="async constructs"):
            tmpl.render(items=[1, 2, 3])

    def test_render_stream_rejects_async_template(self, env: Environment) -> None:
        """render_stream() on async template raises TemplateRuntimeError."""
        tmpl = env.from_string(
            "{% async for x in items %}{{ x }}{% end %}"
        )
        with pytest.raises(TemplateRuntimeError, match="async constructs"):
            list(tmpl.render_stream(items=[1, 2, 3]))

    def test_sync_include_of_async_raises(
        self, env_with_loader: Environment,
    ) -> None:
        """Sync template including an async template raises error."""
        env_with_loader.loader._mapping["async_widget.html"] = (  # type: ignore[union-attr]
            "{% async for x in items %}{{ x }}{% end %}"
        )
        env_with_loader.loader._mapping["sync_page.html"] = (  # type: ignore[union-attr]
            '{% include "async_widget.html" %}'
        )
        tmpl = env_with_loader.get_template("sync_page.html")
        with pytest.raises(TemplateRuntimeError, match="cannot include async"):
            tmpl.render(items=[1, 2, 3])


# ─────────────────────────────────────────────────────────────────────────────
# Cancellation tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCancellation:
    """Test that aclose() propagates through async rendering."""

    @pytest.mark.asyncio
    async def test_aclose_stops_iteration(self, env: Environment) -> None:
        """Closing the async stream stops consuming the underlying iterable."""
        consumed = []

        async def tracked_items() -> AsyncIterator[str]:
            for item in ["a", "b", "c", "d", "e"]:
                consumed.append(item)
                yield item

        tmpl = env.from_string(
            "{% async for x in items %}{{ x }}{% end %}"
        )
        stream = tmpl.render_stream_async(items=tracked_items())

        # Consume only 1-2 chunks then close
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
            if "b" in "".join(chunks):
                break  # triggers aclose on the async generator

        # Should have consumed at most a few items, not all 5
        # (exact number depends on buffering, but should be < 5)
        assert len(consumed) < 5


# ─────────────────────────────────────────────────────────────────────────────
# Parser error tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncParserErrors:
    """Verify parser rejects invalid async constructs."""

    def test_async_without_for_raises(self, env: Environment) -> None:
        """{% async %} without 'for' raises TemplateSyntaxError."""
        with pytest.raises(TemplateSyntaxError, match="Expected 'for' after 'async'"):
            env.from_string("{% async something %}")

    def test_async_bare_raises(self, env: Environment) -> None:
        """{% async %} alone (block-end) raises TemplateSyntaxError."""
        with pytest.raises(TemplateSyntaxError):
            env.from_string("{% async %}")


# ─────────────────────────────────────────────────────────────────────────────
# Sync fallback via async API
# ─────────────────────────────────────────────────────────────────────────────


class TestSyncFallbackViaAsyncAPI:
    """Verify async API works seamlessly on purely sync templates."""

    @pytest.mark.asyncio
    async def test_render_block_stream_async_on_sync_template(
        self, env: Environment,
    ) -> None:
        """render_block_stream_async() wraps a sync block correctly."""
        tmpl = env.from_string(
            "{% block title %}Hello {{ name }}{% endblock %}"
        )
        assert tmpl.is_async is False

        chunks = [
            chunk
            async for chunk in tmpl.render_block_stream_async("title", name="World")
        ]
        result = "".join(chunks)
        assert "Hello World" in result


# ─────────────────────────────────────────────────────────────────────────────
# Nested and combined async constructs
# ─────────────────────────────────────────────────────────────────────────────


class TestNestedAsyncConstructs:
    """Test async constructs nested inside other constructs."""

    @pytest.mark.asyncio
    async def test_nested_async_for_loops(self, env: Environment) -> None:
        """Nested {% async for %} loops maintain separate loop contexts."""
        tmpl = env.from_string(
            "{% async for row in rows %}"
            "[{% async for col in cols %}{{ loop.index }}{% end %}]"
            "{% end %}"
        )
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                rows=async_items(["a", "b"]),
                cols=async_items(["x", "y", "z"]),
            )
        ]
        result = "".join(chunks)
        # Inner loop should reset to 1 each time
        assert "[123]" in result

    @pytest.mark.asyncio
    async def test_async_for_inside_if(self, env: Environment) -> None:
        """{% async for %} inside {% if %} renders conditionally."""
        tmpl = env.from_string(
            "{% if show %}"
            "{% async for x in items %}{{ x }}{% end %}"
            "{% end %}"
        )
        # Condition true
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                show=True, items=async_items(["a", "b"]),
            )
        ]
        assert "a" in "".join(chunks)

        # Condition false
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                show=False, items=async_items(["a", "b"]),
            )
        ]
        assert "".join(chunks).strip() == ""

    @pytest.mark.asyncio
    async def test_await_inside_async_for(self, env: Environment) -> None:
        """{{ await }} works inside {% async for %} body."""
        async def make_coro(val: str) -> str:
            return val.upper()

        tmpl = env.from_string(
            "{% async for fn in funcs %}{{ await fn }}{% end %}"
        )
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                funcs=async_items([make_coro("a"), make_coro("b")]),
            )
        ]
        result = "".join(chunks)
        assert "A" in result
        assert "B" in result


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncEdgeCases:
    """Verify edge cases in async rendering."""

    @pytest.mark.asyncio
    async def test_empty_iterable_without_empty_clause(self, env: Environment) -> None:
        """Empty async iterable with no {% empty %} produces no loop output."""
        tmpl = env.from_string(
            "before{% async for x in items %}{{ x }}{% end %}after"
        )
        chunks = [chunk async for chunk in tmpl.render_stream_async(items=async_empty())]
        result = "".join(chunks)
        assert result == "beforeafter"

    @pytest.mark.asyncio
    async def test_tuple_unpack_with_inline_if(self, env: Environment) -> None:
        """Tuple unpacking combined with inline if filter."""
        tmpl = env.from_string(
            "{% async for k, v in pairs if v %}"
            "{{ k }}={{ v }} "
            "{% end %}"
        )
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                pairs=async_items([("a", "1"), ("b", ""), ("c", "3")]),
            )
        ]
        result = "".join(chunks)
        assert "a=1" in result
        assert "c=3" in result
        assert "b=" not in result

    @pytest.mark.asyncio
    async def test_loop_cycle_and_previtem_in_rendering(
        self, env: Environment,
    ) -> None:
        """loop.cycle() and loop.previtem work together in async for."""
        tmpl = env.from_string(
            "{% async for x in items %}"
            "{{ loop.cycle('odd', 'even') }}:{{ x }}"
            "{% if loop.previtem %}(prev={{ loop.previtem }}){% end %} "
            "{% end %}"
        )
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                items=async_items(["a", "b", "c"]),
            )
        ]
        result = "".join(chunks)
        assert "odd:a" in result
        assert "even:b" in result
        assert "(prev=a)" in result
        assert "odd:c" in result
        assert "(prev=b)" in result


# ─────────────────────────────────────────────────────────────────────────────
# Include inside async loop
# ─────────────────────────────────────────────────────────────────────────────


class TestIncludeInsideAsyncFor:
    """Test {% include %} within async for loop body."""

    @pytest.mark.asyncio
    async def test_include_inside_async_for(
        self, env_with_loader: Environment,
    ) -> None:
        """{% include %} works correctly inside {% async for %} body."""
        env_with_loader.loader._mapping["loop_page.html"] = (  # type: ignore[union-attr]
            "{% async for x in items %}"
            '[{% include "sync_partial.html" %}]'
            "{% end %}"
        )
        tmpl = env_with_loader.get_template("loop_page.html")
        chunks = [
            chunk
            async for chunk in tmpl.render_stream_async(
                items=async_items(["a", "b"]),
            )
        ]
        result = "".join(chunks)
        # The partial should be included once per iteration
        assert result.count("sync partial") == 2


# ─────────────────────────────────────────────────────────────────────────────
# Exception propagation
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncExceptionPropagation:
    """Test that errors in async iterables propagate correctly."""

    @pytest.mark.asyncio
    async def test_error_in_async_iterable_propagates(
        self, env: Environment,
    ) -> None:
        """Exception raised by async iterable surfaces during rendering."""

        async def exploding_items() -> AsyncIterator[str]:
            yield "ok"
            raise ValueError("boom")

        tmpl = env.from_string(
            "{% async for x in items %}{{ x }}{% end %}"
        )
        with pytest.raises(ValueError, match="boom"):
            async for _ in tmpl.render_stream_async(items=exploding_items()):
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Concurrent rendering (ContextVar isolation)
# ─────────────────────────────────────────────────────────────────────────────


class TestConcurrentAsyncRendering:
    """Verify concurrent render_stream_async() calls don't interfere."""

    @pytest.mark.asyncio
    async def test_concurrent_renders_isolated(self, env: Environment) -> None:
        """Two concurrent async renders of different data produce correct results."""

        async def slow_items(prefix: str, n: int) -> AsyncIterator[str]:
            for i in range(n):
                await asyncio.sleep(0)  # yield control
                yield f"{prefix}{i}"

        tmpl = env.from_string(
            "{% async for x in items %}{{ x }},{% end %}"
        )

        async def collect(prefix: str, n: int) -> str:
            chunks = [
                chunk
                async for chunk in tmpl.render_stream_async(
                    items=slow_items(prefix, n),
                )
            ]
            return "".join(chunks)

        result_a, result_b = await asyncio.gather(
            collect("A", 3),
            collect("B", 3),
        )
        assert "A0" in result_a
        assert "A1" in result_a
        assert "A2" in result_a
        assert "B0" in result_b
        assert "B1" in result_b
        assert "B2" in result_b
        # No cross-contamination
        assert "B" not in result_a
        assert "A" not in result_b


# ─────────────────────────────────────────────────────────────────────────────
# Macro / caller async guard tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMacroAsyncGuard:
    """Verify {% def %} and {% call %} correctly guard against async mode."""

    def test_def_with_async_for_compiles(self, env: Environment) -> None:
        """A {% def %} containing {% async for %} compiles without SyntaxError.

        The async for is silenced in the sync macro body — it produces no
        output but must not crash the compiler.
        """
        # This should NOT raise SyntaxError
        tmpl = env.from_string(
            "{% def greet(items) %}"
            "{% async for x in items %}{{ x }}{% end %}"
            "{% enddef %}"
            "{{ greet(data) }}"
        )
        # Macro is sync, so async for is effectively no-op inside it
        assert tmpl is not None

    def test_def_with_include_in_async_template(
        self, env_with_loader: Environment,
    ) -> None:
        """Macro with {% include %} inside an async template compiles correctly.

        This is the regression case: during the async compilation pass,
        macros must not generate 'async for' or 'yield from' conflicts.
        """
        env_with_loader.loader._mapping["macro_page.html"] = (  # type: ignore[union-attr]
            '{% def widget() %}{% include "sync_partial.html" %}{% enddef %}'
            "{{ widget() }}"
            "{% async for x in items %}{{ x }}{% end %}"
        )
        tmpl = env_with_loader.get_template("macro_page.html")
        assert tmpl.is_async is True
