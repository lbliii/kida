"""Kida RenderAccumulator — opt-in profiling for template rendering.

This module provides accumulated metrics during template rendering:
- Block render times
- Macro call counts
- Include/embed counts
- Filter usage

Zero overhead when disabled (get_accumulator() returns None).

RFC: kida-contextvar-patterns

Example:
    from kida import Environment
    from kida.render_accumulator import profiled_render

    env = Environment(loader=FileSystemLoader("templates/"))
    template = env.get_template("page.html")

    # Normal render (no overhead)
    html = template.render(page=page)

    # Profiled render (opt-in)
    with profiled_render() as metrics:
        html = template.render(page=page)

    print(metrics.summary())
    # {
    #   "total_ms": 12.5,
    #   "blocks": {
    #     "content": {"ms": 8.2, "calls": 1},
    #     "nav": {"ms": 2.1, "calls": 1},
    #   },
    #   "macros": {"render_card": 15, "format_date": 8},
    #   "includes": {"partials/sidebar.html": 1},
    #   "filters": {"escape": 45, "truncate": 12},
    # }

"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Iterator


@dataclass
class BlockTiming:
    """Timing data for a single block render.

    Attributes:
        name: Block name
        duration_ms: Total render time in milliseconds
        call_count: Number of times the block was rendered
    """

    name: str
    duration_ms: float
    call_count: int = 1


@dataclass
class RenderAccumulator:
    """Accumulated metrics during template rendering.

    Opt-in profiling for debugging slow templates.
    Zero overhead when disabled (get_accumulator() returns None).

    Attributes:
        block_timings: Block name → timing data
        macro_calls: Macro name → call count
        include_counts: Template name → include count
        filter_calls: Filter name → call count
        start_time: Render start timestamp
    """

    # Block render times
    block_timings: dict[str, BlockTiming] = field(default_factory=dict)

    # Macro call counts
    macro_calls: dict[str, int] = field(default_factory=dict)

    # Include/embed counts
    include_counts: dict[str, int] = field(default_factory=dict)

    # Filter usage
    filter_calls: dict[str, int] = field(default_factory=dict)

    # Total render time
    start_time: float = field(default_factory=perf_counter)

    def record_block(self, name: str, duration_ms: float) -> None:
        """Record a block render.

        If block was already recorded, adds to existing duration and
        increments call count.

        Args:
            name: Block name
            duration_ms: Render duration in milliseconds
        """
        if name in self.block_timings:
            existing = self.block_timings[name]
            self.block_timings[name] = BlockTiming(
                name=name,
                duration_ms=existing.duration_ms + duration_ms,
                call_count=existing.call_count + 1,
            )
        else:
            self.block_timings[name] = BlockTiming(name=name, duration_ms=duration_ms)

    def record_macro(self, name: str) -> None:
        """Record a macro invocation.

        Args:
            name: Macro name (may include template prefix for imports)
        """
        self.macro_calls[name] = self.macro_calls.get(name, 0) + 1

    def record_include(self, template_name: str) -> None:
        """Record an include/embed.

        Args:
            template_name: Name of included template
        """
        self.include_counts[template_name] = self.include_counts.get(template_name, 0) + 1

    def record_filter(self, name: str) -> None:
        """Record a filter usage.

        Args:
            name: Filter name
        """
        self.filter_calls[name] = self.filter_calls.get(name, 0) + 1

    @property
    def total_duration_ms(self) -> float:
        """Total render duration in milliseconds."""
        return (perf_counter() - self.start_time) * 1000

    def summary(self) -> dict[str, Any]:
        """Get summary of render metrics.

        Returns:
            Dict with total_ms, blocks, macros, includes, filters
        """
        return {
            "total_ms": round(self.total_duration_ms, 2),
            "blocks": {
                name: {"ms": round(t.duration_ms, 2), "calls": t.call_count}
                for name, t in sorted(
                    self.block_timings.items(),
                    key=lambda x: x[1].duration_ms,
                    reverse=True,
                )
            },
            "macros": dict(
                sorted(self.macro_calls.items(), key=lambda x: x[1], reverse=True)
            ),
            "includes": dict(
                sorted(self.include_counts.items(), key=lambda x: x[1], reverse=True)
            ),
            "filters": dict(
                sorted(self.filter_calls.items(), key=lambda x: x[1], reverse=True)
            ),
        }


# Module-level ContextVar
_accumulator: ContextVar[RenderAccumulator | None] = ContextVar(
    "render_accumulator",
    default=None,
)


def get_accumulator() -> RenderAccumulator | None:
    """Get current accumulator (None if profiling disabled).

    Returns:
        Current RenderAccumulator or None if not in profiled render
    """
    return _accumulator.get()


@contextmanager
def profiled_render() -> Iterator[RenderAccumulator]:
    """Context manager for profiled rendering.

    Creates a RenderAccumulator and makes it available via get_accumulator()
    for the duration of the with block. Template code can check for the
    accumulator and record metrics.

    Yields:
        RenderAccumulator that will be populated during render

    Example:
        with profiled_render() as metrics:
            html = template.render(ctx)
            print(metrics.summary())
    """
    acc = RenderAccumulator()
    token: Token[RenderAccumulator | None] = _accumulator.set(acc)
    try:
        yield acc
    finally:
        _accumulator.reset(token)


@contextmanager
def timed_block(name: str) -> Iterator[None]:
    """Time a block render (no-op if profiling disabled).

    Use this to wrap block rendering code. If profiling is not enabled,
    this is a no-op with minimal overhead.

    Args:
        name: Block name for recording

    Yields:
        None (context manager protocol)

    Example:
        with timed_block("content"):
            html = block_func(ctx, blocks)
    """
    acc = get_accumulator()
    if acc is None:
        yield
        return

    start = perf_counter()
    try:
        yield
    finally:
        duration_ms = (perf_counter() - start) * 1000
        acc.record_block(name, duration_ms)
