"""Render helper factories for Template namespace.

Extracted from core.py to reduce Template.__init__ size and improve
testability. Each factory takes env_ref and returns a closure used by
compiled template code.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, final

from kida.template.cached_blocks import CachedBlocksDict
from kida.template.error_enhancement import enhance_template_error
from kida.template.helpers import UNDEFINED

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from kida.environment import Environment
    from kida.render_context import RenderContext
    from kida.template.types import BlocksDict


_TTL_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhdSMHD]?)\s*$")


def _coerce_ttl_seconds(ttl: object) -> float | None:
    """Convert template ttl argument to seconds.

    Supports numeric values (seconds) and compact duration strings:
    - "30" / "30s" -> 30
    - "5m" -> 300
    - "2h" -> 7200
    - "1d" -> 86400

    Returns None for invalid values, negative values, or when ttl is None.
    """
    if ttl is None:
        return None

    if isinstance(ttl, bool):
        return None

    if isinstance(ttl, int | float):
        ttl_seconds = float(ttl)
        return ttl_seconds if ttl_seconds >= 0 else None

    text = str(ttl)
    match = _TTL_DURATION_RE.match(text)
    if match is None:
        return None

    value = float(match.group(1))
    if value < 0:
        return None

    unit = match.group(2).lower()
    multiplier = 1.0
    if unit == "m":
        multiplier = 60.0
    elif unit == "h":
        multiplier = 3600.0
    elif unit == "d":
        multiplier = 86400.0

    return value * multiplier


def _wrap_blocks_if_cached(
    blocks: BlocksDict | dict[str, Any],
    render_ctx: RenderContext,
) -> dict[str, Any] | CachedBlocksDict:
    """Wrap blocks with CachedBlocksDict if render context has cached blocks."""
    if (
        not render_ctx.cached_blocks
        or isinstance(blocks, CachedBlocksDict)
        or not render_ctx.cached_block_names
    ):
        return blocks
    return CachedBlocksDict(
        blocks,
        render_ctx.cached_blocks,
        render_ctx.cached_block_names,
        stats=render_ctx.cache_stats,
    )


@final
@dataclass(frozen=True, slots=True)
class MacroWrapper:
    """Callable wrapper for imported macros with source attribution metadata.

    Used for error attribution: template_stack, template_name, and source
    are set on render_ctx before calling the macro. The _kida_source_*
    attributes are available for future error enhancement (e.g. source snippets).

    Injects _defining_namespace as _outer_ctx so macros see their defining
    template's namespace (e.g. tag_list when article_card calls it).
    """

    _fn: Callable[..., object]
    _defining_namespace: dict[str, Any]
    _kida_source_template: str
    _kida_source_file: str | None
    _source: str | None
    _kida_macro_name: str | None
    _needs_outer_ctx: bool = False

    def __call__(self, *args: object, **kwargs: object) -> object:
        from kida.render_context import get_render_context_required

        render_ctx = get_render_context_required()
        caller_name = render_ctx.template_name
        caller_line = render_ctx.line
        render_ctx.template_stack.append((caller_name or "<template>", caller_line))
        prev_name = render_ctx.template_name
        prev_line = render_ctx.line
        prev_source = render_ctx.source
        render_ctx.template_name = self._kida_source_template
        render_ctx.line = 0
        render_ctx.source = self._source
        if self._needs_outer_ctx:
            kwargs_to_use = {**kwargs, "_outer_ctx": self._defining_namespace}
        else:
            kwargs_to_use = kwargs
        try:
            return self._fn(*args, **kwargs_to_use)
        finally:
            render_ctx.template_stack.pop()
            render_ctx.template_name = prev_name
            render_ctx.line = prev_line
            render_ctx.source = prev_source

    def __iter__(self) -> Iterator[object]:
        """Raise helpful error when a macro is used in a for loop.

        This commonly happens when a macro and context variable share the same
        name (e.g. route_tabs). The macro shadows the variable, so {% for x in
        route_tabs %} iterates over the macro instead of the intended list.
        """
        name = self._kida_macro_name or "macro"
        raise TypeError(
            f"Cannot iterate over macro '{name}'. "
            "A macro may be shadowing a template variable with the same name. "
            "Consider renaming the macro (e.g. render_route_tabs) to avoid collisions."
        )


def _make_macro_wrapper(
    macro_fn: Callable[..., object],
    source_template: str,
    source_file: str | None,
    source: str | None = None,
    macro_name: str | None = None,
    defining_namespace: dict[str, Any] | None = None,
) -> MacroWrapper:
    """Wrap imported macro to push/pop template_stack for error attribution."""
    # Pre-compute whether _outer_ctx injection is needed (avoids inspect.signature per call)
    needs_outer_ctx = False
    try:
        sig = inspect.signature(macro_fn)
        needs_outer_ctx = "_outer_ctx" in sig.parameters
    except ValueError, TypeError:
        pass
    return MacroWrapper(
        _fn=macro_fn,
        _defining_namespace=defining_namespace or {},
        _kida_source_template=source_template,
        _kida_source_file=source_file,
        _source=source,
        _kida_macro_name=macro_name,
        _needs_outer_ctx=needs_outer_ctx,
    )


def make_render_helpers(
    env_ref: Callable[[], Environment | None],
) -> dict[str, Any]:
    """Create all render helpers for a Template namespace.

    Args:
        env_ref: WeakRef to Environment (callable returning Environment or None)

    Returns:
        Dict with _include, _extends, _include_stream, _extends_stream,
        _include_stream_async, _extends_stream_async, _import_macros,
        _cache_get, _cache_set.
    """
    from kida.exceptions import (
        ErrorCode,
        TemplateError,
        TemplateNotFoundError,
        TemplateRuntimeError,
        TemplateSyntaxError,
    )
    from kida.render_accumulator import get_accumulator
    from kida.render_context import (
        get_render_context_required,
        reset_render_context,
        set_render_context,
    )
    from kida.utils.template_keys import normalize_template_name

    def _resolve_env(template_name: str) -> Environment:
        _env = env_ref()
        if _env is None:
            raise TemplateRuntimeError(
                f"Environment has been garbage collected while including '{template_name}'",
                template_name=template_name,
                code=ErrorCode.ENV_GARBAGE_COLLECTED,
                suggestion="Keep a reference to the Environment for the lifetime of its templates.",
            )
        return _env

    def _enter_child_context(
        template_name: str,
        *,
        for_extends: bool,
    ):
        """Shared setup for include/extends variants.

        Handles depth check, accumulator recording (includes only),
        environment resolution, and child context creation.

        Returns:
            tuple of (child_ctx, template, token) — caller MUST call
            reset_render_context(token) in a finally block.
        """
        render_ctx = get_render_context_required()
        if for_extends:
            render_ctx.check_extends_depth(template_name)
        else:
            render_ctx.check_include_depth(template_name)
            acc = get_accumulator()
            if acc is not None:
                acc.record_include(template_name)
        _env = _resolve_env(template_name)
        try:
            tmpl = _env.get_template(template_name)
        except TemplateNotFoundError as e:
            # Enrich with caller context so users know which template triggered it
            caller = render_ctx.template_name
            if caller:
                tag = "extends" if for_extends else "include"
                loc = f"{caller}:{render_ctx.line}" if render_ctx.line else caller
                raise TemplateNotFoundError(
                    f"{e} (referenced by {{% {tag} %}} in {loc})",
                ) from e
            raise
        if for_extends:
            child_ctx = render_ctx.child_context_for_extends(template_name, source=tmpl._source)
        else:
            child_ctx = render_ctx.child_context(template_name, source=tmpl._source)
        token = set_render_context(child_ctx)
        return child_ctx, tmpl, token

    def _include(
        template_name: str,
        context: dict[str, Any],
        ignore_missing: bool = False,
        *,
        blocks: dict[str, Any] | None = None,
    ) -> str:
        caller_name = get_render_context_required().template_name
        try:
            child_ctx, included, token = _enter_child_context(template_name, for_extends=False)
            try:
                if included.is_async:
                    raise TemplateRuntimeError(
                        f"Sync template '{caller_name}' cannot include "
                        f"async template '{template_name}'. Use render_stream_async() "
                        f"to render templates with async includes.",
                        template_name=caller_name,
                    )
                try:
                    if blocks is not None and included._render_func is not None:
                        result: str = included._render_func(context, blocks)
                        return result
                    if included._render_func is not None:
                        result = included._render_func(context, None)
                        return str(result) if result is not None else ""
                    return str(included.render(**context))
                except TemplateError:
                    raise
                except Exception as e:
                    raise enhance_template_error(e, child_ctx, included._source) from e
            finally:
                reset_render_context(token)
        except TemplateError as e:
            if ignore_missing and isinstance(e, TemplateNotFoundError):
                return ""
            raise

    def _extends(template_name: str, context: dict[str, Any], blocks: BlocksDict) -> str:
        child_ctx, parent, token = _enter_child_context(template_name, for_extends=True)
        try:
            if parent._render_func is None:
                raise TemplateRuntimeError(
                    f"Template '{template_name}' not properly compiled: "
                    f"_render_func is None. Check for syntax errors in the template.",
                    template_name=template_name,
                    code=ErrorCode.NOT_COMPILED,
                    suggestion="Ensure the template was compiled via env.get_template() or env.from_string().",
                )
            blocks_to_use = _wrap_blocks_if_cached(blocks, child_ctx)
            result: str = parent._render_func(context, blocks_to_use)
            return result
        finally:
            reset_render_context(token)

    def _include_stream(
        template_name: str,
        context: dict[str, Any],
        ignore_missing: bool = False,
        *,
        blocks: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        try:
            _child_ctx, included, token = _enter_child_context(template_name, for_extends=False)
            try:
                stream_func = included._namespace.get("render_stream")
                if stream_func is not None:
                    if blocks is not None:
                        yield from stream_func(context, blocks)
                    else:
                        yield from stream_func(context, None)
                else:
                    yield included.render(**context)
            finally:
                reset_render_context(token)
        except TemplateNotFoundError, TemplateSyntaxError, TemplateRuntimeError:
            if ignore_missing:
                return
            raise

    def _extends_stream(
        template_name: str, context: dict[str, Any], blocks: dict[str, Any]
    ) -> Iterator[str]:
        child_ctx, parent, token = _enter_child_context(template_name, for_extends=True)
        try:
            stream_func = parent._namespace.get("render_stream")
            if stream_func is None:
                raise TemplateRuntimeError(
                    f"Template '{template_name}' not properly compiled: render_stream is None.",
                    template_name=template_name,
                    code=ErrorCode.NOT_COMPILED,
                    suggestion="Ensure the template was compiled with streaming support.",
                )
            blocks_to_use = _wrap_blocks_if_cached(blocks, child_ctx)
            yield from stream_func(context, blocks_to_use)
        finally:
            reset_render_context(token)

    async def _include_stream_async(
        template_name: str,
        context: dict[str, Any],
        ignore_missing: bool = False,
        *,
        blocks: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        try:
            _child_ctx, included, token = _enter_child_context(template_name, for_extends=False)
            try:
                async_func = included._namespace.get("render_stream_async")
                if async_func is not None:
                    if blocks is not None:
                        async for chunk in async_func(context, blocks):
                            yield chunk
                    else:
                        async for chunk in async_func(context, None):
                            yield chunk
                else:
                    sync_func = included._namespace.get("render_stream")
                    if sync_func is not None:
                        if blocks is not None:
                            for chunk in sync_func(context, blocks):
                                yield chunk
                        else:
                            for chunk in sync_func(context, None):
                                yield chunk
                    else:
                        yield included.render(**context)
            finally:
                reset_render_context(token)
        except TemplateNotFoundError, TemplateSyntaxError, TemplateRuntimeError:
            if ignore_missing:
                return
            raise

    async def _extends_stream_async(
        template_name: str, context: dict[str, Any], blocks: dict[str, Any]
    ) -> AsyncIterator[str]:
        child_ctx, parent, token = _enter_child_context(template_name, for_extends=True)
        try:
            blocks_to_use = _wrap_blocks_if_cached(blocks, child_ctx)
            async_func = parent._namespace.get("render_stream_async")
            if async_func is not None:
                async for chunk in async_func(context, blocks_to_use):
                    yield chunk
            else:
                sync_func = parent._namespace.get("render_stream")
                if sync_func is None:
                    raise TemplateRuntimeError(
                        f"Template '{template_name}' not properly compiled: render_stream is None.",
                        template_name=template_name,
                        code=ErrorCode.NOT_COMPILED,
                        suggestion="Ensure the template was compiled with streaming support.",
                    )
                for chunk in sync_func(context, blocks_to_use):
                    yield chunk
        finally:
            reset_render_context(token)

    def _import_macros(
        template_name: str,
        with_context: bool,
        context: dict[str, Any],
        names: list[str] | None = None,
    ) -> dict[str, Any]:
        template_name = normalize_template_name(template_name)
        _env = env_ref()
        if _env is None:
            raise TemplateRuntimeError(
                f"Environment has been garbage collected while importing '{template_name}'",
                template_name=template_name,
                code=ErrorCode.ENV_GARBAGE_COLLECTED,
                suggestion="Keep a reference to the Environment for the lifetime of its templates.",
            )
        render_ctx = get_render_context_required()
        if template_name in render_ctx.import_stack:
            chain = " → ".join([*render_ctx.import_stack, template_name])
            raise TemplateRuntimeError(
                f"Circular import detected: '{template_name}' imports itself (via {chain})",
                template_name=render_ctx.template_name,
                code=ErrorCode.CIRCULAR_IMPORT,
            )
        render_ctx.import_stack.append(template_name)
        try:
            imported = _env.get_template(template_name)
            child_ctx = render_ctx.child_context(template_name, source=imported._source)
            token = set_render_context(child_ctx)
            try:
                if imported._render_func is None:
                    raise TemplateRuntimeError(
                        f"Template '{template_name}' not properly compiled: "
                        f"_render_func is None. Check for syntax errors in the template.",
                        template_name=template_name,
                        code=ErrorCode.NOT_COMPILED,
                        suggestion="Ensure the template was compiled via env.get_template() or env.from_string().",
                    )
                import_ctx = dict(_env.get_filtered_globals())
                if with_context:
                    import_ctx.update(context)
                imported._render_func(import_ctx, None)
                if names is not None:
                    for name in names:
                        val = import_ctx.get(name, UNDEFINED)
                        if val is UNDEFINED or not callable(val):
                            raise TemplateRuntimeError(
                                f"Macro '{name}' not found in template '{template_name}'",
                                template_name=render_ctx.template_name,
                                code=ErrorCode.MACRO_NOT_FOUND,
                                suggestion=(
                                    "Check the imported template defines this macro. "
                                    "Verify name and import path."
                                ),
                            )
                source_file = imported._filename if imported else None
                macro_source = imported._source if imported else None
                # Snapshot namespace before wrapping so macros see their siblings
                defining_namespace = dict(import_ctx)
                # Single-pass: wrap callables in-place (keys() snapshot avoids dict-changed)
                for key in list(import_ctx):
                    val = import_ctx[key]
                    if callable(val) and not isinstance(val, type):
                        import_ctx[key] = _make_macro_wrapper(
                            val,
                            template_name,
                            source_file,
                            macro_source,
                            macro_name=key,
                            defining_namespace=defining_namespace,
                        )
                return import_ctx
            finally:
                reset_render_context(token)
        finally:
            render_ctx.import_stack.pop()

    def _cache_get(key: str) -> str | None:
        _env = env_ref()
        if _env is None:
            return None
        return _env._fragment_cache.get(key)

    def _cache_set(key: str, value: str, ttl: object = None) -> str:
        _env = env_ref()
        if _env is None:
            return value
        ttl_seconds = _coerce_ttl_seconds(ttl)
        return _env._fragment_cache.get_or_set(key, lambda: value, ttl=ttl_seconds)

    return {
        "_include": _include,
        "_extends": _extends,
        "_include_stream": _include_stream,
        "_extends_stream": _extends_stream,
        "_include_stream_async": _include_stream_async,
        "_extends_stream_async": _extends_stream_async,
        "_import_macros": _import_macros,
        "_cache_get": _cache_get,
        "_cache_set": _cache_set,
    }
