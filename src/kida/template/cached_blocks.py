"""Cached blocks dict wrapper for block cache optimization."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class CachedBlocksDict:
    """Dict wrapper that returns cached HTML for site-scoped blocks.

    Used by Kida's block cache optimization to intercept .get() calls
    from templates and return pre-rendered HTML for site-wide blocks
    (nav, footer, etc.).

    Complexity: O(1) for lookups.

    """

    __slots__ = ("_cached", "_cached_names", "_original", "_stats")

    def __init__(
        self,
        original: dict[str, Any] | None,
        cached: dict[str, str],
        cached_names: frozenset[str] | set[str],
        stats: dict[str, int] | None = None,
    ):
        # Ensure original is a dict even if None is passed
        self._original = original if original is not None else {}
        self._cached = cached
        self._cached_names = cached_names
        self._stats = stats

    def get(self, key: str, default: Any = None) -> Any:
        """Intercept .get() calls to return cached HTML when available."""
        if key in self._cached_names:
            cached_html = self._cached[key]

            # Record hit in shared stats if available
            if self._stats is not None:
                self._stats["hits"] = self._stats.get("hits", 0) + 1

            # Return a wrapper function that matches the block function signature:
            # _block_name(ctx, _blocks)
            def cached_block_func(_ctx: dict[str, Any], _blocks: dict[str, Any]) -> str:
                return cached_html

            return cached_block_func

        # Record miss in shared stats if available (block exists but not cached)
        if self._stats is not None:
            self._stats["misses"] = self._stats.get("misses", 0) + 1

        # Fall back to original dict behavior
        return self._original.get(key, default)

    def setdefault(self, key: str, default: Any = None) -> Any:
        """Preserve setdefault() behavior for block registration.

        Kida templates use .setdefault() to register their own block functions
        if not already overridden by a child template.
        """
        if key in self._cached_names:
            # Cached blocks take precedence - return cached wrapper
            cached_html = self._cached[key]

            # Record hit in shared stats if available
            if self._stats is not None:
                self._stats["hits"] = self._stats.get("hits", 0) + 1

            def cached_block_func(_ctx: dict[str, Any], _blocks: dict[str, Any]) -> str:
                return cached_html

            return cached_block_func

        # For non-cached blocks, use normal setdefault
        return self._original.setdefault(key, default)

    def __getitem__(self, key: str) -> Any:
        """Support dict[key] access."""
        if key in self._cached_names:
            cached_html = self._cached[key]

            # Record hit in shared stats if available
            if self._stats is not None:
                self._stats["hits"] = self._stats.get("hits", 0) + 1

            def cached_block_func(_ctx: dict[str, Any], _blocks: dict[str, Any]) -> str:
                return cached_html

            return cached_block_func
        return self._original[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Support dict[key] = value assignment."""
        self._original[key] = value

    def __contains__(self, key: str) -> bool:
        """Support 'key in dict' checks."""
        return key in self._original or key in self._cached_names

    def keys(self) -> set[str]:
        """Support .keys() iteration."""
        return self._original.keys() | self._cached_names

    def copy(self) -> dict[str, Any]:
        """Support .copy() for embed/include operations."""
        result = self._original.copy()
        # Add cached wrappers to copy (properly capture in closure)
        for name in self._cached_names:
            cached_html = self._cached[name]

            # Create wrapper with proper closure capture
            def make_wrapper(
                html: str, stats: dict[str, int] | None
            ) -> Callable[[dict[str, Any], dict[str, Any]], str]:
                def wrapper(_ctx: dict[str, Any], _blocks: dict[str, Any]) -> str:
                    if stats is not None:
                        stats["hits"] = stats.get("hits", 0) + 1
                    return html

                return wrapper

            result[name] = make_wrapper(cached_html, self._stats)
        return result
