"""Kida RenderContext — per-render state isolated from user context.

This module implements ContextVar-based render state management, replacing
the internal keys (_template, _line, _include_depth, _cached_blocks,
_cached_stats) that were previously injected into the user's ctx dict.

Benefits:
    - Clean user context (no internal key pollution)
    - No key collision risk (user can use _template as variable)
    - Centralized state management
    - Thread-safe via ContextVar
    - Async-safe (ContextVars propagate to asyncio.to_thread in Python 3.14)

RFC: kida-contextvar-patterns

"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class RenderContext:
    """Per-render state isolated from user context.

    Replaces the _template, _line, _include_depth, _cached_blocks, and
    _cached_stats keys that were previously injected into the user's ctx dict.

    Thread Safety:
        ContextVars are thread-local by design. Each thread/async task
        has its own RenderContext instance.

    Async Safety:
        ContextVars propagate correctly to asyncio.to_thread() in Python 3.14,
        so render_async() works without special handling.

    Attributes:
        template_name: Current template name for error messages
        filename: Source file path for error messages
        line: Current line number (updated during render by generated code)
        include_depth: Current include/embed depth (DoS protection)
        max_include_depth: Maximum allowed include depth
        cached_blocks: Site-scoped block cache (shared across includes)
        cached_block_names: Frozenset of cached block names for O(1) lookup
        cache_stats: Optional dict for cache hit/miss tracking
    """

    # Template identification (for error messages)
    template_name: str | None = None
    filename: str | None = None

    # Current source position (updated during render by generated code)
    line: int = 0

    # Include/embed tracking (DoS protection)
    include_depth: int = 0
    max_include_depth: int = 50

    # Block caching (RFC: kida-template-introspection)
    cached_blocks: dict[str, str] = field(default_factory=dict)
    cached_block_names: frozenset[str] = field(default_factory=frozenset)
    cache_stats: dict[str, int] | None = None

    def check_include_depth(self, template_name: str) -> None:
        """Check if include depth limit exceeded.

        Args:
            template_name: Name of template being included

        Raises:
            TemplateRuntimeError: If depth >= max_include_depth
        """
        if self.include_depth >= self.max_include_depth:
            from kida.environment.exceptions import TemplateRuntimeError

            raise TemplateRuntimeError(
                f"Maximum include depth exceeded ({self.max_include_depth}) "
                f"when including '{template_name}'",
                template_name=self.template_name,
                suggestion="Check for circular includes: A → B → A",
            )

    def child_context(self, template_name: str | None = None) -> RenderContext:
        """Create child context for include/embed with incremented depth.

        Shares cached_blocks and cache_stats with parent (they're document-wide).

        Args:
            template_name: Optional override for child template name

        Returns:
            New RenderContext with incremented include_depth
        """
        return RenderContext(
            template_name=template_name or self.template_name,
            filename=self.filename,
            line=0,
            include_depth=self.include_depth + 1,
            max_include_depth=self.max_include_depth,
            cached_blocks=self.cached_blocks,
            cached_block_names=self.cached_block_names,
            cache_stats=self.cache_stats,
        )


# Module-level ContextVar
_render_context: ContextVar[RenderContext | None] = ContextVar(
    "render_context",
    default=None,
)


def get_render_context() -> RenderContext | None:
    """Get current render context (None if not in render).

    Returns:
        Current RenderContext or None if not in a render call
    """
    return _render_context.get()


def get_render_context_required() -> RenderContext:
    """Get current render context, raise if not in render.

    Used by generated code for line tracking.

    Returns:
        Current RenderContext

    Raises:
        RuntimeError: If not in a render context
    """
    ctx = _render_context.get()
    if ctx is None:
        raise RuntimeError("Not in a render context")
    return ctx


@contextmanager
def render_context(
    template_name: str | None = None,
    filename: str | None = None,
    cached_blocks: dict[str, str] | None = None,
    cache_stats: dict[str, int] | None = None,
) -> Iterator[RenderContext]:
    """Context manager for render-scoped state.

    Creates a new RenderContext and sets it as the current context for
    the duration of the with block. Automatically restores the previous
    context when exiting.

    Args:
        template_name: Template name for error messages
        filename: Source file path for error messages
        cached_blocks: Site-scoped block cache
        cache_stats: Optional dict for cache hit/miss tracking

    Yields:
        The new RenderContext

    Example:
        with render_context(template_name="page.html") as ctx:
            html = template._render_func(user_ctx, blocks)
            # ctx.line updated during render for error tracking
    """
    ctx = RenderContext(
        template_name=template_name,
        filename=filename,
        cached_blocks=cached_blocks or {},
        cached_block_names=frozenset(cached_blocks.keys()) if cached_blocks else frozenset(),
        cache_stats=cache_stats,
    )
    token: Token[RenderContext | None] = _render_context.set(ctx)
    try:
        yield ctx
    finally:
        _render_context.reset(token)


def set_render_context(ctx: RenderContext) -> Token[RenderContext | None]:
    """Set a RenderContext and return the reset token.

    Low-level function for cases where the context manager isn't suitable
    (e.g., nested include/embed calls that need to restore context manually).

    Args:
        ctx: The RenderContext to set

    Returns:
        Token for resetting to previous context via _render_context.reset()
    """
    return _render_context.set(ctx)


def reset_render_context(token: Token[RenderContext | None]) -> None:
    """Reset render context using a token from set_render_context.

    Args:
        token: Token returned from set_render_context()
    """
    _render_context.reset(token)
