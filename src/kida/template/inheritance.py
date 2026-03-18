"""Template inheritance mixin — block resolution across extends chain.

Requires host class to define slots: _inheritance_chain_cache,
_effective_blocks_cache, _inheritance_cache_lock, _extends_target,
_local_blocks_sync, _local_blocks_stream, _local_blocks_async_stream,
_env_ref, _name. Requires _get_env_limits() method.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from threading import Lock

    from kida.environment import Environment
    from kida.template.core import Template


class TemplateInheritanceMixin:
    """Mixin for inherited block resolution.

    Adds _build_local_block_maps, _inheritance_chain, _effective_block_map.
    """

    if TYPE_CHECKING:
        # Host attributes (from Template.__slots__ / __init__)
        _inheritance_chain_cache: tuple[Template, ...] | None
        _effective_blocks_cache: dict[str, dict[str, Any]]
        _inheritance_cache_lock: Lock
        _extends_target: str | None
        _local_blocks_sync: dict[str, Any]
        _local_blocks_stream: dict[str, Any]
        _local_blocks_async_stream: dict[str, Any]
        _name: str | None
        _env: Environment

        def _get_env_limits(self) -> tuple[int, int]: ...

    @staticmethod
    def _build_local_block_maps(
        namespace: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Precompute per-template block function maps from compiled namespace."""
        sync_map: dict[str, Any] = {}
        stream_map: dict[str, Any] = {}
        async_stream_map: dict[str, Any] = {}

        for key, value in namespace.items():
            if not key.startswith("_block_") or not callable(value):
                continue
            if key.endswith("_stream_async"):
                async_stream_map[key[7:-13]] = value
            elif key.endswith("_stream"):
                stream_map[key[7:-7]] = value
            else:
                sync_map[key[7:]] = value

        return sync_map, stream_map, async_stream_map

    def _inheritance_chain(self) -> tuple[Template, ...] | list[Any]:
        """Return [self, parent, grandparent, ...] for inherited block resolution."""
        from kida.environment.exceptions import TemplateRuntimeError

        # Skip cache when auto_reload: parent templates can be reloaded independently
        if not self._env.auto_reload:
            cached_chain = self._inheritance_chain_cache
            if cached_chain is not None:
                return cached_chain  # Return cached tuple directly; callers only iterate

        chain: list[Any] = [self]
        current: Any = self
        max_depth, _ = self._get_env_limits()
        depth = 0
        while current._extends_target is not None and depth < max_depth:
            parent = current._env.get_template(current._extends_target)
            chain.append(parent)
            current = parent
            depth += 1
        if current._extends_target is not None and depth >= max_depth:
            raise TemplateRuntimeError(
                f"Maximum extends depth exceeded ({max_depth}) "
                f"when resolving inheritance chain for '{self._name or '(inline)'}'",
                template_name=self._name,
                suggestion="Check for circular inheritance: A extends B extends A",
            )
        if not self._env.auto_reload:
            with self._inheritance_cache_lock:
                if self._inheritance_chain_cache is None:
                    self._inheritance_chain_cache = tuple(chain)
        return chain

    def _effective_block_map(self, kind: str) -> dict[str, Any]:
        """Build nearest-child-wins block map for render_block inheritance.

        kind: "sync" | "stream" | "async_stream"
        Returns dict of block_name -> callable for that kind.
        """
        if not self._env.auto_reload:
            cached_map = self._effective_blocks_cache.get(kind)
            if cached_map is not None:
                return cached_map

        with self._inheritance_cache_lock:
            if not self._env.auto_reload:
                cached_map = self._effective_blocks_cache.get(kind)
                if cached_map is not None:
                    return cached_map
        # Build outside lock — _inheritance_chain() acquires it when populating
        # Single-pass: collect all three kinds at once to avoid repeated chain traversal
        if kind == "sync":
            block_attrs = ("_local_blocks_sync",)
        elif kind == "stream":
            block_attrs = ("_local_blocks_stream", "_local_blocks_sync")
        else:
            block_attrs = (
                "_local_blocks_async_stream",
                "_local_blocks_stream",
                "_local_blocks_sync",
            )
        effective: dict[str, Any] = {}
        for t in self._inheritance_chain():
            for attr in block_attrs:
                for name, fn in getattr(t, attr).items():
                    effective.setdefault(name, fn)
        if not self._env.auto_reload:
            with self._inheritance_cache_lock:
                self._effective_blocks_cache.setdefault(kind, effective)
        return effective
