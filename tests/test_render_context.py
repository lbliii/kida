"""Tests for RenderContext and RenderAccumulator.

RFC: kida-contextvar-patterns
"""

import threading

import pytest

from kida import Environment
from kida.render_context import (
    RenderContext,
    get_render_context,
    get_render_context_required,
    render_context,
    reset_render_context,
    set_render_context,
)


class TestRenderContext:
    """Tests for RenderContext dataclass."""

    def test_default_values(self):
        """RenderContext has sensible defaults."""
        ctx = RenderContext()
        assert ctx.template_name is None
        assert ctx.filename is None
        assert ctx.line == 0
        assert ctx.include_depth == 0
        assert ctx.max_include_depth == 50
        assert ctx.cached_blocks == {}
        assert ctx.cached_block_names == frozenset()
        assert ctx.cache_stats is None

    def test_check_include_depth_within_limit(self):
        """check_include_depth passes when within limit."""
        ctx = RenderContext(include_depth=10, max_include_depth=50)
        # Should not raise
        ctx.check_include_depth("test.html")

    def test_check_include_depth_at_limit(self):
        """check_include_depth raises when at limit."""
        from kida.environment.exceptions import TemplateRuntimeError

        ctx = RenderContext(include_depth=50, max_include_depth=50)
        with pytest.raises(TemplateRuntimeError) as exc_info:
            ctx.check_include_depth("test.html")
        assert "Maximum include depth exceeded" in str(exc_info.value)
        assert "test.html" in str(exc_info.value)

    def test_child_context_increments_depth(self):
        """child_context creates context with incremented depth."""
        parent = RenderContext(
            template_name="parent.html",
            include_depth=5,
            max_include_depth=50,
            cached_blocks={"nav": "<nav>"},
            cache_stats={"hits": 0},
        )

        child = parent.child_context("child.html")

        assert child.template_name == "child.html"
        assert child.include_depth == 6
        assert child.max_include_depth == 50
        # Shared references
        assert child.cached_blocks is parent.cached_blocks
        assert child.cache_stats is parent.cache_stats
        assert child.line == 0  # Reset for child

    def test_child_context_inherits_template_name(self):
        """child_context inherits parent template name if not specified."""
        parent = RenderContext(template_name="parent.html")
        child = parent.child_context()
        assert child.template_name == "parent.html"


class TestRenderContextContextVar:
    """Tests for ContextVar-based render context management."""

    def test_get_render_context_outside_render(self):
        """get_render_context returns None outside render."""
        assert get_render_context() is None

    def test_get_render_context_required_outside_render(self):
        """get_render_context_required raises outside render."""
        with pytest.raises(RuntimeError) as exc_info:
            get_render_context_required()
        assert "Not in a render context" in str(exc_info.value)

    def test_render_context_manager_sets_context(self):
        """render_context context manager sets and clears context."""
        assert get_render_context() is None

        with render_context(template_name="test.html") as ctx:
            assert get_render_context() is ctx
            assert ctx.template_name == "test.html"

        assert get_render_context() is None

    def test_render_context_manager_with_cached_blocks(self):
        """render_context initializes cached_block_names from cached_blocks."""
        cached = {"nav": "<nav>", "footer": "<footer>"}

        with render_context(cached_blocks=cached) as ctx:
            assert ctx.cached_blocks == cached
            assert ctx.cached_block_names == frozenset(["nav", "footer"])

    def test_nested_render_contexts(self):
        """Nested render contexts are properly isolated."""
        with render_context(template_name="outer.html") as outer:
            assert get_render_context() is outer

            with render_context(template_name="inner.html") as inner:
                assert get_render_context() is inner
                assert inner.template_name == "inner.html"

            # Restored to outer
            assert get_render_context() is outer
            assert outer.template_name == "outer.html"

        assert get_render_context() is None

    def test_set_and_reset_render_context(self):
        """Low-level set/reset functions work correctly."""
        ctx = RenderContext(template_name="manual.html")
        token = set_render_context(ctx)

        assert get_render_context() is ctx

        reset_render_context(token)
        assert get_render_context() is None


class TestRenderContextThreadSafety:
    """Tests for thread safety of RenderContext."""

    def test_concurrent_renders_isolated(self):
        """Concurrent renders have isolated RenderContext."""
        results = {}

        def render_worker(thread_id: int, template_name: str):
            with render_context(template_name=template_name) as ctx:
                # Simulate some work
                ctx.line = thread_id * 10
                results[thread_id] = {
                    "template": get_render_context().template_name,
                    "line": get_render_context().line,
                }

        threads = [
            threading.Thread(target=render_worker, args=(i, f"template_{i}.html")) for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread saw its own context
        assert results[0]["template"] == "template_0.html"
        assert results[0]["line"] == 0
        assert results[1]["template"] == "template_1.html"
        assert results[1]["line"] == 10
        assert results[2]["template"] == "template_2.html"
        assert results[2]["line"] == 20
        assert results[3]["template"] == "template_3.html"
        assert results[3]["line"] == 30


class TestRenderContextIntegration:
    """Integration tests with Template.render()."""

    def test_user_context_is_clean(self):
        """User context has no internal keys after render."""
        env = Environment()
        template = env.from_string("{{ name }}")
        ctx = {"name": "World"}
        template.render(ctx)

        # No internal keys in user context
        assert "_template" not in ctx
        assert "_line" not in ctx
        assert "_include_depth" not in ctx
        assert "_cached_blocks" not in ctx
        assert "_cached_stats" not in ctx

    def test_user_can_use_underscore_template(self):
        """User can use _template as a variable name."""
        env = Environment()
        template = env.from_string("{{ _template }}")
        html = template.render(_template="my_value")
        assert html == "my_value"

    def test_user_can_use_underscore_line(self):
        """User can use _line as a variable name."""
        env = Environment()
        template = env.from_string("{{ _line }}")
        html = template.render(_line=42)
        assert html == "42"

    def test_error_messages_include_line(self):
        """Runtime errors include line numbers from RenderContext."""
        from kida.environment.exceptions import UndefinedError

        env = Environment()
        # Line 2 has the error
        template = env.from_string("line1\n{{ undefined_var.attr }}")

        with pytest.raises(UndefinedError) as exc_info:
            template.render()

        # Error should include template info from RenderContext
        assert "undefined_var" in str(exc_info.value)
        assert "<template>" in str(exc_info.value)

    def test_include_depth_tracked_via_render_context(self):
        """Include depth tracked via RenderContext, not ctx dict."""
        from kida.environment.loaders import DictLoader

        loader = DictLoader(
            {
                "a.html": "{% include 'b.html' %}",
                "b.html": "depth: {{ _include_depth | default('N/A') }}",
            }
        )
        env = Environment(loader=loader)

        template = env.get_template("a.html")
        html = template.render()

        # _include_depth should NOT be in user context (shows 'N/A')
        assert "N/A" in html

    def test_circular_include_detection(self):
        """Circular includes are detected via RenderContext."""
        from kida.environment.exceptions import TemplateRuntimeError
        from kida.environment.loaders import DictLoader

        loader = DictLoader(
            {
                "a.html": "A{% include 'b.html' %}",
                "b.html": "B{% include 'a.html' %}",
            }
        )
        env = Environment(loader=loader)

        template = env.get_template("a.html")

        with pytest.raises(TemplateRuntimeError) as exc_info:
            template.render()

        assert "Maximum include depth exceeded" in str(exc_info.value)

    def test_circular_import_detection(self):
        """Circular macro imports ({% from X import y %} where X imports itself) raise K-TPL-003."""
        from kida.environment.exceptions import ErrorCode, TemplateRuntimeError
        from kida.environment.loaders import DictLoader

        # Self-import: _tab_content imports from itself
        loader = DictLoader(
            {
                "showcase/_tab_content.html": (
                    "{% from 'showcase/_tab_content.html' import tab_section %}"
                    "{% def tab_section() %}content{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        template = env.get_template("showcase/_tab_content.html")

        with pytest.raises(TemplateRuntimeError) as exc_info:
            template.render()

        assert "Circular import detected" in str(exc_info.value)
        assert exc_info.value.code == ErrorCode.CIRCULAR_IMPORT
        assert "showcase/_tab_content.html" in str(exc_info.value)

    def test_transitive_circular_import_detection(self):
        """Transitive circular imports (A→B→A) raise K-TPL-003."""
        from kida.environment.exceptions import ErrorCode, TemplateRuntimeError
        from kida.environment.loaders import DictLoader

        loader = DictLoader(
            {
                "a.html": "{% from 'b.html' import x %}{{ x() }}",
                "b.html": "{% from 'a.html' import y %}{% def x() %}b{% end %}",
            }
        )
        env = Environment(loader=loader)
        template = env.get_template("a.html")

        with pytest.raises(TemplateRuntimeError) as exc_info:
            template.render()

        assert "Circular import detected" in str(exc_info.value)
        assert exc_info.value.code == ErrorCode.CIRCULAR_IMPORT


class TestRenderAccumulator:
    """Tests for RenderAccumulator profiling."""

    def test_accumulator_disabled_by_default(self):
        """get_accumulator returns None when profiling disabled."""
        from kida.render_accumulator import get_accumulator

        assert get_accumulator() is None

    def test_profiled_render_enables_accumulator(self):
        """profiled_render context manager enables accumulator."""
        from kida.render_accumulator import get_accumulator, profiled_render

        with profiled_render() as acc:
            assert get_accumulator() is acc
            assert acc is not None

        assert get_accumulator() is None

    def test_record_block_timing(self):
        """record_block accumulates block timings."""
        from kida.render_accumulator import RenderAccumulator

        acc = RenderAccumulator()
        acc.record_block("content", 5.0)
        acc.record_block("content", 3.0)  # Second call

        assert "content" in acc.block_timings
        assert acc.block_timings["content"].duration_ms == 8.0
        assert acc.block_timings["content"].call_count == 2

    def test_record_macro(self):
        """record_macro counts macro calls."""
        from kida.render_accumulator import RenderAccumulator

        acc = RenderAccumulator()
        acc.record_macro("format_date")
        acc.record_macro("format_date")
        acc.record_macro("render_card")

        assert acc.macro_calls["format_date"] == 2
        assert acc.macro_calls["render_card"] == 1

    def test_record_include(self):
        """record_include counts includes."""
        from kida.render_accumulator import RenderAccumulator

        acc = RenderAccumulator()
        acc.record_include("partials/nav.html")
        acc.record_include("partials/nav.html")
        acc.record_include("partials/footer.html")

        assert acc.include_counts["partials/nav.html"] == 2
        assert acc.include_counts["partials/footer.html"] == 1

    def test_record_filter(self):
        """record_filter counts filter usage."""
        from kida.render_accumulator import RenderAccumulator

        acc = RenderAccumulator()
        acc.record_filter("escape")
        acc.record_filter("escape")
        acc.record_filter("truncate")

        assert acc.filter_calls["escape"] == 2
        assert acc.filter_calls["truncate"] == 1

    def test_summary_output(self):
        """summary() returns structured metrics."""
        from kida.render_accumulator import RenderAccumulator

        acc = RenderAccumulator()
        acc.record_block("content", 10.0)
        acc.record_block("nav", 5.0)
        acc.record_macro("format_date")
        acc.record_include("partials/nav.html")
        acc.record_filter("escape")

        summary = acc.summary()

        assert "total_ms" in summary
        assert "blocks" in summary
        assert "content" in summary["blocks"]
        assert summary["blocks"]["content"]["ms"] == 10.0
        assert summary["blocks"]["content"]["calls"] == 1
        assert summary["macros"]["format_date"] == 1
        assert summary["includes"]["partials/nav.html"] == 1
        assert summary["filters"]["escape"] == 1

    def test_timed_block_context_manager(self):
        """timed_block records timing when profiling enabled."""
        import time

        from kida.render_accumulator import profiled_render, timed_block

        with profiled_render() as metrics, timed_block("test_block"):
            time.sleep(0.01)  # 10ms

        assert "test_block" in metrics.block_timings
        # Should be at least 10ms (might be slightly more due to overhead)
        assert metrics.block_timings["test_block"].duration_ms >= 9.0

    def test_timed_block_no_op_when_disabled(self):
        """timed_block is no-op when profiling disabled."""
        from kida.render_accumulator import get_accumulator, timed_block

        # Should not raise, just pass through
        with timed_block("test_block"):
            pass

        assert get_accumulator() is None

    def test_profiled_render_integration(self):
        """profiled_render captures include counts during real render."""
        from kida.environment.loaders import DictLoader
        from kida.render_accumulator import profiled_render

        loader = DictLoader(
            {
                "main.html": "{% include 'partial.html' %}{% include 'partial.html' %}",
                "partial.html": "PARTIAL",
            }
        )
        env = Environment(loader=loader)

        template = env.get_template("main.html")

        with profiled_render() as metrics:
            html = template.render()

        assert html == "PARTIALPARTIAL"
        # Two includes of partial.html
        assert metrics.include_counts.get("partial.html") == 2


class TestCompilerEmittedProfiling:
    """Test that the compiler emits profiling instrumentation for blocks, filters, macros."""

    def test_block_profiling_auto_instrumented(self):
        """Block calls are automatically recorded with timing."""
        from kida.render_accumulator import profiled_render

        env = Environment()
        tmpl = env.from_string("{% block header %}H{% end %}{% block body %}B{% end %}")
        with profiled_render() as acc:
            result = tmpl.render()
            summary = acc.summary()

        assert result == "HB"
        assert "header" in summary["blocks"]
        assert "body" in summary["blocks"]
        assert summary["blocks"]["header"]["calls"] == 1
        assert summary["blocks"]["body"]["calls"] == 1
        assert summary["blocks"]["header"]["ms"] >= 0

    def test_filter_profiling_auto_instrumented(self):
        """Filter calls are automatically recorded."""
        from kida.render_accumulator import profiled_render

        env = Environment()
        tmpl = env.from_string("{{ name | upper | trim }}")
        with profiled_render() as acc:
            result = tmpl.render(name="  alice  ")
            summary = acc.summary()

        assert result == "ALICE"
        assert summary["filters"]["upper"] == 1
        assert summary["filters"]["trim"] == 1

    def test_macro_profiling_auto_instrumented(self):
        """Macro ({% def %}) calls are automatically recorded."""
        from kida.render_accumulator import profiled_render

        env = Environment()
        tmpl = env.from_string(
            "{% def greet(name) %}Hi {{ name }}{% end %}{{ greet('A') }}{{ greet('B') }}"
        )
        with profiled_render() as acc:
            result = tmpl.render()
            summary = acc.summary()

        assert "Hi A" in result
        assert "Hi B" in result
        assert summary["macros"]["greet"] == 2

    def test_profiling_zero_cost_when_disabled(self):
        """When profiling is disabled, templates render normally."""
        env = Environment()
        tmpl = env.from_string(
            "{% block title %}Title{% end %}"
            "{{ name | upper }}"
            "{% def f(x) %}{{ x }}{% end %}{{ f('ok') }}"
        )
        result = tmpl.render(name="test")
        assert "Title" in result
        assert "TEST" in result
        assert "ok" in result

    def test_profiling_with_inheritance(self):
        """Profiling works with template inheritance."""
        from kida.environment.loaders import DictLoader
        from kida.render_accumulator import profiled_render

        loader = DictLoader(
            {
                "base.html": "{% block content %}BASE{% end %}",
                "child.html": ("{% extends 'base.html' %}{% block content %}CHILD{% end %}"),
            }
        )
        env = Environment(loader=loader)
        tmpl = env.get_template("child.html")

        with profiled_render() as acc:
            result = tmpl.render()
            summary = acc.summary()

        assert result == "CHILD"
        assert "content" in summary["blocks"]

    def test_pipeline_filter_profiling(self):
        """Pipeline operator filters are also recorded."""
        from kida.render_accumulator import profiled_render

        env = Environment()
        tmpl = env.from_string("{{ name |> upper |> trim }}")
        with profiled_render() as acc:
            result = tmpl.render(name="  bob  ")
            summary = acc.summary()

        assert result == "BOB"
        assert summary["filters"]["upper"] == 1
        assert summary["filters"]["trim"] == 1
