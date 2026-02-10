"""Kida Template — compiled template object ready for rendering.

The Template class wraps a compiled code object and provides the ``render()``
API. Templates are immutable and thread-safe for concurrent rendering.

Architecture:
    ```
    Template
    ├── _env_ref: WeakRef[Environment]  # Prevents circular refs
    ├── _code: code object              # Compiled Python bytecode
    ├── _render_func: callable          # Extracted render() function
    └── _name, _filename                # For error messages
    ```

StringBuilder Pattern:
Generated code uses ``buf.append()`` + ``''.join(buf)``:
    ```python
    def render(ctx, _blocks=None):
        buf = []
        _append = buf.append
        _append("Hello, ")
        _append(_e(_s(ctx["name"])))
        return ''.join(buf)
    ```
This is O(n) vs O(n²) for string concatenation.

Memory Safety:
Uses ``weakref.ref(env)`` to break potential cycles:
``Template → (weak) → Environment → cache → Template``

Thread-Safety:
- Templates are immutable after construction
- ``render()`` creates only local state (buf list)
- Multiple threads can call ``render()`` concurrently

Complexity:
- ``render()``: O(n) where n = output size
- ``_escape()``: O(n) single-pass via ``str.translate()``

"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

from kida.template.cached_blocks import CachedBlocksDict
from kida.template.helpers import (
    STATIC_NAMESPACE,
    UNDEFINED,
    coerce_numeric,
    default_safe,
    is_defined,
    lookup,
    lookup_scope,
    null_coalesce,
    spaceless,
    str_safe,
)
from kida.template.introspection import TemplateIntrospectionMixin
from kida.template.loop_context import AsyncLoopContext, LoopContext
from kida.utils.html import html_escape

if TYPE_CHECKING:
    import types

    from kida.analysis import TemplateMetadata
    from kida.environment import Environment
    from kida.nodes import Template as TemplateNode
    from kida.render_context import RenderContext


class Template(TemplateIntrospectionMixin):
    """Compiled template ready for rendering.

    Wraps a compiled code object containing a ``render(ctx, _blocks)`` function.
    Templates are immutable and thread-safe for concurrent ``render()`` calls.

    Thread-Safety:
        - Template object is immutable after construction
        - Each ``render()`` call creates local state only (buf list)
        - Multiple threads can render the same template simultaneously

    Memory Safety:
        Uses ``weakref.ref(env)`` to prevent circular reference leaks:
        ``Template → (weak) → Environment → _cache → Template``

    Attributes:
        name: Template identifier (for error messages)
        filename: Source file path (for error messages)

    Methods:
        render(**context): Render template with given variables
        render_async(**context): Async render for templates with await

    Error Enhancement:
        Runtime errors are caught and enhanced with template context:
            ```
            TemplateRuntimeError: 'NoneType' has no attribute 'title'
              Location: article.html:15
              Expression: {{ post.title }}
              Values:
                post = None (NoneType)
              Suggestion: Check if 'post' is defined before accessing .title
            ```

    Example:
            >>> from kida import Environment
            >>> env = Environment()
            >>> t = env.from_string("Hello, {{ name | upper }}!")
            >>> t.render(name="World")
            'Hello, WORLD!'

            >>> t.render({"name": "World"})  # Dict context also works
            'Hello, WORLD!'

    """

    __slots__ = (
        "_code",
        "_env_ref",
        "_filename",
        "_metadata_cache",  # Cached analysis results
        "_name",
        "_namespace",  # Compiled namespace with block functions
        "_optimized_ast",  # Preserved AST for introspection (or None)
        "_render_async_func",
        "_render_func",
        "_render_stream_async_func",  # RFC: rfc-async-rendering
        "_render_stream_func",
        "_source",  # Template source for runtime error snippets
    )

    def __init__(
        self,
        env: Environment,
        code: types.CodeType,
        name: str | None,
        filename: str | None,
        optimized_ast: TemplateNode | None = None,
        source: str | None = None,
    ):
        """Initialize template with compiled code.

        Args:
            env: Parent Environment (stored as weak reference)
            code: Compiled Python code object
            name: Template name (for error messages)
            filename: Source filename (for error messages)
            optimized_ast: Optional preserved AST for introspection.
                If None, introspection methods return empty results.
            source: Template source for runtime error snippets.
                Stored for use by _enhance_error() to provide source
                context in TemplateRuntimeError exceptions.
        """
        # Use weakref to prevent circular reference: Template <-> Environment
        self._env_ref: weakref.ref[Environment] = weakref.ref(env)
        self._code = code
        self._name = name
        self._filename = filename
        self._optimized_ast = optimized_ast
        self._source = source
        self._metadata_cache: TemplateMetadata | None = None

        # Capture env reference for closures (will be dereferenced at call time)
        env_ref = self._env_ref

        # Include helper - loads and renders included template
        def _include(
            template_name: str,
            context: dict[str, Any],
            ignore_missing: bool = False,
            *,  # Force remaining args to be keyword-only
            blocks: dict[str, Any] | None = None,
        ) -> str:
            from kida.environment.exceptions import (
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

            render_ctx = get_render_context_required()

            # Check include depth (DoS protection)
            render_ctx.check_include_depth(template_name)

            # Record include for profiling (RFC: kida-contextvar-patterns)
            acc = get_accumulator()
            if acc is not None:
                acc.record_include(template_name)

            _env = env_ref()
            if _env is None:
                raise RuntimeError(
                    f"Environment has been garbage collected while including '{template_name}'"
                )
            try:
                included = _env.get_template(template_name)

                # Guard: sync template cannot include an async template
                if included.is_async:
                    raise TemplateRuntimeError(
                        f"Sync template '{render_ctx.template_name}' cannot include "
                        f"async template '{template_name}'. Use render_stream_async() "
                        f"to render templates with async includes.",
                        template_name=render_ctx.template_name,
                    )

                # Create child context with incremented depth
                child_ctx = render_ctx.child_context(template_name)

                # Set child context for the included template's render
                token = set_render_context(child_ctx)
                try:
                    # If blocks are provided (for embed), call the render function directly
                    # with blocks parameter
                    if blocks is not None and included._render_func is not None:
                        result: str = included._render_func(context, blocks)
                        return result
                    # Call _render_func directly to avoid context manager overhead
                    if included._render_func is not None:
                        result = included._render_func(context, None)
                        return str(result) if result is not None else ""
                    return str(included.render(**context))
                finally:
                    reset_render_context(token)
            except (TemplateNotFoundError, TemplateSyntaxError, TemplateRuntimeError):
                if ignore_missing:
                    return ""
                raise

        # Extends helper - renders parent template with child's blocks
        def _extends(
            template_name: str, context: dict[str, Any], blocks: dict[str, Any]
        ) -> str:
            from kida.render_context import get_render_context_required

            render_ctx = get_render_context_required()

            _env = env_ref()
            if _env is None:
                raise RuntimeError(
                    f"Environment has been garbage collected while extending '{template_name}'"
                )
            parent = _env.get_template(template_name)
            # Guard against templates that failed to compile properly
            if parent._render_func is None:
                raise RuntimeError(
                    f"Template '{template_name}' not properly compiled: "
                    f"_render_func is None. Check for syntax errors in the template."
                )
            # Apply cached blocks wrapper from RenderContext
            blocks_to_use: dict[str, Any] | CachedBlocksDict = blocks
            if (
                render_ctx.cached_blocks
                and not isinstance(blocks, CachedBlocksDict)
                and render_ctx.cached_block_names
            ):
                blocks_to_use = CachedBlocksDict(
                    blocks,
                    render_ctx.cached_blocks,
                    render_ctx.cached_block_names,
                    stats=render_ctx.cache_stats,
                )

            result: str = parent._render_func(context, blocks_to_use)
            return result

        # Streaming include helper - yields chunks from included template
        def _include_stream(
            template_name: str,
            context: dict[str, Any],
            ignore_missing: bool = False,
            *,
            blocks: dict[str, Any] | None = None,
        ):  # -> Iterator[str]
            from kida.environment.exceptions import (
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

            render_ctx = get_render_context_required()
            render_ctx.check_include_depth(template_name)

            acc = get_accumulator()
            if acc is not None:
                acc.record_include(template_name)

            _env = env_ref()
            if _env is None:
                raise RuntimeError(
                    f"Environment has been garbage collected while including '{template_name}'"
                )
            try:
                included = _env.get_template(template_name)
                child_ctx = render_ctx.child_context(template_name)
                token = set_render_context(child_ctx)
                try:
                    stream_func = included._namespace.get("render_stream")
                    if stream_func is not None:
                        if blocks is not None:
                            yield from stream_func(context, blocks)
                        else:
                            yield from stream_func(context, None)
                    else:
                        # Fallback: render full string and yield it
                        yield included.render(**context)
                finally:
                    reset_render_context(token)
            except (TemplateNotFoundError, TemplateSyntaxError, TemplateRuntimeError):
                if ignore_missing:
                    return
                raise

        # Streaming extends helper - yields chunks from parent template
        def _extends_stream(
            template_name: str, context: dict[str, Any], blocks: dict[str, Any]
        ):  # -> Iterator[str]
            from kida.render_context import get_render_context_required

            render_ctx = get_render_context_required()

            _env = env_ref()
            if _env is None:
                raise RuntimeError(
                    f"Environment has been garbage collected while extending '{template_name}'"
                )
            parent = _env.get_template(template_name)
            stream_func = parent._namespace.get("render_stream")
            if stream_func is None:
                raise RuntimeError(
                    f"Template '{template_name}' not properly compiled: "
                    f"render_stream is None."
                )
            # Apply cached blocks wrapper from RenderContext
            blocks_to_use: dict[str, Any] | CachedBlocksDict = blocks
            if (
                render_ctx.cached_blocks
                and not isinstance(blocks, CachedBlocksDict)
                and render_ctx.cached_block_names
            ):
                blocks_to_use = CachedBlocksDict(
                    blocks,
                    render_ctx.cached_blocks,
                    render_ctx.cached_block_names,
                    stats=render_ctx.cache_stats,
                )

            yield from stream_func(context, blocks_to_use)

        # Async streaming include helper — yields chunks from included template
        # RFC: rfc-async-rendering
        async def _include_stream_async(
            template_name: str,
            context: dict[str, Any],
            ignore_missing: bool = False,
            *,
            blocks: dict[str, Any] | None = None,
        ):  # -> AsyncIterator[str]
            from kida.environment.exceptions import (
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

            render_ctx = get_render_context_required()
            render_ctx.check_include_depth(template_name)

            acc = get_accumulator()
            if acc is not None:
                acc.record_include(template_name)

            _env = env_ref()
            if _env is None:
                raise RuntimeError(
                    f"Environment has been garbage collected while including '{template_name}'"
                )
            try:
                included = _env.get_template(template_name)
                child_ctx = render_ctx.child_context(template_name)
                token = set_render_context(child_ctx)
                try:
                    # Check if included template has async streaming
                    async_func = included._namespace.get("render_stream_async")
                    if async_func is not None:
                        if blocks is not None:
                            async for chunk in async_func(context, blocks):
                                yield chunk
                        else:
                            async for chunk in async_func(context, None):
                                yield chunk
                    else:
                        # Fall back to sync stream (works inside async generator)
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
            except (TemplateNotFoundError, TemplateSyntaxError, TemplateRuntimeError):
                if ignore_missing:
                    return
                raise

        # Async streaming extends helper — yields chunks from parent template
        # RFC: rfc-async-rendering
        async def _extends_stream_async(
            template_name: str, context: dict[str, Any], blocks: dict[str, Any]
        ):  # -> AsyncIterator[str]
            from kida.render_context import get_render_context_required

            render_ctx = get_render_context_required()

            _env = env_ref()
            if _env is None:
                raise RuntimeError(
                    f"Environment has been garbage collected while extending '{template_name}'"
                )
            parent = _env.get_template(template_name)

            # Apply cached blocks wrapper from RenderContext
            blocks_to_use: dict[str, Any] | CachedBlocksDict = blocks
            if (
                render_ctx.cached_blocks
                and not isinstance(blocks, CachedBlocksDict)
                and render_ctx.cached_block_names
            ):
                blocks_to_use = CachedBlocksDict(
                    blocks,
                    render_ctx.cached_blocks,
                    render_ctx.cached_block_names,
                    stats=render_ctx.cache_stats,
                )

            # Always use async streaming — all templates generate render_stream_async
            async_func = parent._namespace.get("render_stream_async")
            if async_func is not None:
                async for chunk in async_func(context, blocks_to_use):
                    yield chunk
            else:
                # Fallback for templates compiled before async support
                sync_func = parent._namespace.get("render_stream")
                if sync_func is None:
                    raise RuntimeError(
                        f"Template '{template_name}' not properly compiled: "
                        f"render_stream is None."
                    )
                for chunk in sync_func(context, blocks_to_use):
                    yield chunk

        # Import macros from another template
        def _import_macros(
            template_name: str, with_context: bool, context: dict[str, Any]
        ) -> dict[str, Any]:
            _env = env_ref()
            if _env is None:
                raise RuntimeError(
                    f"Environment has been garbage collected while importing '{template_name}'"
                )
            imported = _env.get_template(template_name)
            if imported._render_func is None:
                raise RuntimeError(
                    f"Template '{template_name}' not properly compiled: "
                    f"_render_func is None. Check for syntax errors in the template."
                )
            import_ctx = dict(_env.globals)
            if with_context:
                import_ctx.update(context)
            imported._render_func(import_ctx, None)
            return import_ctx

        # Cache helpers - use environment's LRU cache
        def _cache_get(key: str) -> str | None:
            """Get cached fragment by key (with TTL support)."""
            _env = env_ref()
            if _env is None:
                return None
            return _env._fragment_cache.get(key)

        def _cache_set(key: str, value: str, ttl: str | None = None) -> str:
            """Set cached fragment and return stored value."""
            _env = env_ref()
            if _env is None:
                return value
            return _env._fragment_cache.get_or_set(key, lambda: value)

        # Execute the code to get the render function
        # Start with shared static namespace (copied once, not constructed)
        namespace: dict[str, Any] = STATIC_NAMESPACE.copy()

        # Import RenderContext getter for generated code
        from kida.render_context import get_render_context_required

        # Add per-template dynamic entries
        namespace.update(
            {
                "_env": env,
                "_filters": env._filters,
                "_tests": env._tests,
                "_escape": self._escape,
                "_getattr": self._safe_getattr,
                "_getattr_none": self._getattr_preserve_none,
                "_lookup": lookup,
                "_lookup_scope": lookup_scope,
                "_default_safe": default_safe,
                "_is_defined": is_defined,
                "_null_coalesce": null_coalesce,
                "_coerce_numeric": coerce_numeric,
                "_spaceless": spaceless,
                "_str_safe": str_safe,
                "_include": _include,
                "_extends": _extends,
                "_include_stream": _include_stream,
                "_extends_stream": _extends_stream,
                "_include_stream_async": _include_stream_async,
                "_extends_stream_async": _extends_stream_async,
                "_import_macros": _import_macros,
                "_cache_get": _cache_get,
                "_cache_set": _cache_set,
                "_LoopContext": LoopContext,
                "_AsyncLoopContext": AsyncLoopContext,
                # RFC: kida-contextvar-patterns - for generated code line tracking
                "_get_render_ctx": get_render_context_required,
            }
        )
        exec(code, namespace)
        self._render_func = namespace.get("render")
        self._render_async_func = namespace.get("render_async")
        self._render_stream_func = namespace.get("render_stream")
        self._render_stream_async_func = namespace.get("render_stream_async")
        self._namespace = namespace  # Keep for render_block()

    @property
    def _env(self) -> Environment:
        """Get the Environment (dereferences weak reference)."""
        env = self._env_ref()
        if env is None:
            raise RuntimeError(
                f"Environment has been garbage collected"
                f" (template: {self._name or 'unknown'})"
            )
        return env

    @property
    def name(self) -> str | None:
        """Template name."""
        return self._name

    @property
    def filename(self) -> str | None:
        """Source filename."""
        return self._filename

    def render(self, *args: Any, **kwargs: Any) -> str:
        """Render template with given context.

        User context is now CLEAN - no internal keys injected.
        Internal state (_template, _line, _include_depth, _cached_blocks,
        _cached_stats) is managed via RenderContext ContextVar.

        Args:
            *args: Single dict of context variables
            **kwargs: Context variables as keyword arguments

        Returns:
            Rendered template as string

        Example:
            >>> t.render(name="World")
            'Hello, World!'
            >>> t.render({"name": "World"})
            'Hello, World!'
        """
        from kida.environment.exceptions import TemplateRuntimeError
        from kida.render_context import render_context

        # Guard: async templates must use render_stream_async()
        if self.is_async:
            raise TemplateRuntimeError(
                f"Template '{self._name or '(inline)'}' uses async constructs "
                f"(async for / await). Use render_stream_async() or "
                f"render_block_stream_async() instead of render().",
                template_name=self._name,
            )

        # Build context (CLEAN - no internal keys!)
        ctx: dict[str, Any] = {}

        # Add globals
        ctx.update(self._env.globals)

        # Add positional dict arg
        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                ctx.update(args[0])
            else:
                raise TypeError(
                    f"render() takes at most 1 positional argument (a dict), got {len(args)}"
                )

        # Add keyword args
        ctx.update(kwargs)

        # Extract internal state from kwargs (backward compat for Bengal)
        cached_blocks = ctx.pop("_cached_blocks", {})
        cache_stats = ctx.pop("_cached_stats", None)

        render_func = self._render_func

        if render_func is None:
            raise RuntimeError(
                f"Template '{self._name or '(inline)'}' not properly compiled"
            )

        with render_context(
            template_name=self._name,
            filename=self._filename,
            source=self._source,
            cached_blocks=cached_blocks,
            cache_stats=cache_stats,
        ) as render_ctx:
            # Prepare blocks dictionary (inject cache wrapper if site-scoped blocks exist)
            blocks_arg = None
            if render_ctx.cached_blocks:
                cached_block_names = render_ctx.cached_block_names
                if cached_block_names:
                    blocks_arg = CachedBlocksDict(
                        None,
                        render_ctx.cached_blocks,
                        cached_block_names,
                        stats=render_ctx.cache_stats,
                    )

            # Render with error enhancement
            try:
                result: str = render_func(ctx, blocks_arg)
                return result
            except TemplateRuntimeError:
                raise
            except Exception as e:
                from kida.environment.exceptions import TemplateNotFoundError, UndefinedError

                if isinstance(e, (UndefinedError, TemplateNotFoundError)):
                    raise
                raise self._enhance_error(e, render_ctx) from e

    def render_block(self, block_name: str, *args: Any, **kwargs: Any) -> str:
        """Render a single block from the template.

        Renders just the named block, useful for caching blocks that
        only depend on site-wide context (e.g., navigation, footer).

        Args:
            block_name: Name of the block to render (e.g., "nav", "footer")
            *args: Single dict of context variables
            **kwargs: Context variables as keyword arguments

        Returns:
            Rendered block HTML as string

        Raises:
            KeyError: If block doesn't exist in template
            RuntimeError: If template not properly compiled
        """
        from kida.environment.exceptions import TemplateRuntimeError
        from kida.render_context import render_context

        # Look up block function
        func_name = f"_block_{block_name}"
        block_func = self._namespace.get(func_name)

        if block_func is None:
            available = [
                k[7:]
                for k in self._namespace
                if k.startswith("_block_") and callable(self._namespace[k])
            ]
            raise KeyError(
                f"Block '{block_name}' not found in template '{self._name}'. "
                f"Available blocks: {available}"
            )

        # Build clean user context
        ctx: dict[str, Any] = {}
        ctx.update(self._env.globals)

        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                ctx.update(args[0])
            else:
                raise TypeError(
                    f"render_block() takes at most 1 positional argument (a dict), "
                    f"got {len(args)}"
                )

        ctx.update(kwargs)

        with render_context(
            template_name=self._name,
            filename=self._filename,
            source=self._source,
        ) as render_ctx:
            try:
                # Run {% globals %} setup if present — injects macros/variables into ctx
                globals_setup = self._namespace.get("_globals_setup")
                if globals_setup is not None:
                    globals_setup(ctx)

                result: str = block_func(ctx, {})
                return result
            except TemplateRuntimeError:
                raise
            except Exception as e:
                from kida.environment.exceptions import TemplateNotFoundError, UndefinedError

                if isinstance(e, (UndefinedError, TemplateNotFoundError)):
                    raise
                raise self._enhance_error(e, render_ctx) from e

    def render_with_blocks(
        self,
        block_overrides: dict[str, str],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Render this template with pre-rendered HTML injected into blocks.

        Enables programmatic layout composition: render a page's content,
        then inject it as the ``content`` block of a parent layout template,
        without needing ``{% extends %}`` in the template source.

        Each key in *block_overrides* names a block; the value is a
        pre-rendered HTML string that replaces that block's default content.

        Args:
            block_overrides: Mapping of block name → pre-rendered HTML string.
            *args: Single dict of context variables.
            **kwargs: Context variables as keyword arguments.

        Returns:
            Rendered template as string with block overrides applied.

        Raises:
            RuntimeError: If template not properly compiled.

        Example:
            >>> layout = env.get_template("_layout.html")
            >>> inner = "<h1>Hello</h1>"
            >>> layout.render_with_blocks({"content": inner}, title="Home")
        """
        from kida.environment.exceptions import TemplateRuntimeError
        from kida.render_context import render_context

        # Build context
        ctx: dict[str, Any] = {}
        ctx.update(self._env.globals)

        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                ctx.update(args[0])
            else:
                raise TypeError(
                    f"render_with_blocks() takes at most 1 positional argument "
                    f"(a dict), got {len(args)}"
                )

        ctx.update(kwargs)

        render_func = self._render_func
        if render_func is None:
            raise RuntimeError(
                f"Template '{self._name or '(inline)'}' not properly compiled"
            )

        # Build _blocks dict with callables matching the compiled signature:
        # block_func(ctx, _blocks) -> str
        _blocks: dict[str, Any] = {}
        for name, html in block_overrides.items():
            # Use default arg to capture html by value (avoid closure over loop var)
            _blocks[name] = lambda ctx, _blocks, _html=html: _html

        with render_context(
            template_name=self._name,
            filename=self._filename,
            source=self._source,
        ) as render_ctx:
            try:
                # Run {% globals %} setup if present
                globals_setup = self._namespace.get("_globals_setup")
                if globals_setup is not None:
                    globals_setup(ctx)

                result: str = render_func(ctx, _blocks)
                return result
            except TemplateRuntimeError:
                raise
            except Exception as e:
                from kida.environment.exceptions import TemplateNotFoundError, UndefinedError

                if isinstance(e, (UndefinedError, TemplateNotFoundError)):
                    raise
                raise self._enhance_error(e, render_ctx) from e

    def render_stream(self, *args: Any, **kwargs: Any):
        """Render template as a generator of HTML chunks.

        Yields chunks at every statement boundary, enabling progressive
        delivery via chunked transfer encoding.

        Args:
            *args: Single dict of context variables
            **kwargs: Context variables as keyword arguments

        Yields:
            str: HTML chunks as they are produced

        Example:
            >>> for chunk in t.render_stream(name="World"):
            ...     send(chunk)
        """
        from kida.environment.exceptions import TemplateRuntimeError
        from kida.render_context import render_context

        # Guard: async templates must use render_stream_async()
        if self.is_async:
            raise TemplateRuntimeError(
                f"Template '{self._name or '(inline)'}' uses async constructs "
                f"(async for / await). Use render_stream_async() instead of "
                f"render_stream().",
                template_name=self._name,
            )

        ctx: dict[str, Any] = {}
        ctx.update(self._env.globals)

        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                ctx.update(args[0])
            else:
                raise TypeError(
                    f"render_stream() takes at most 1 positional argument (a dict), "
                    f"got {len(args)}"
                )
        ctx.update(kwargs)

        cached_blocks = ctx.pop("_cached_blocks", {})
        cache_stats = ctx.pop("_cached_stats", None)

        stream_func = self._render_stream_func
        if stream_func is None:
            raise RuntimeError(
                f"Template '{self._name or '(inline)'}' has no render_stream function"
            )

        with render_context(
            template_name=self._name,
            filename=self._filename,
            source=self._source,
            cached_blocks=cached_blocks,
            cache_stats=cache_stats,
        ) as render_ctx:
            blocks_arg = None
            if render_ctx.cached_blocks:
                cached_block_names = render_ctx.cached_block_names
                if cached_block_names:
                    blocks_arg = CachedBlocksDict(
                        None,
                        render_ctx.cached_blocks,
                        cached_block_names,
                        stats=render_ctx.cache_stats,
                    )

            # Yield non-None chunks from the generator
            for chunk in stream_func(ctx, blocks_arg):
                if chunk is not None:
                    yield chunk

    def list_blocks(self) -> list[str]:
        """List all blocks defined in this template.

        Returns:
            List of block names available for render_block()
        """
        return [
            k[7:]
            for k in self._namespace
            if k.startswith("_block_") and callable(self._namespace[k])
        ]

    def _enhance_error(
        self,
        error: Exception,
        render_ctx: RenderContext,
    ) -> Exception:
        """Enhance a generic exception with template context from RenderContext.

        Converts generic Python exceptions into TemplateRuntimeError with
        template name, line number, and source snippet context.
        """
        from kida.environment.exceptions import (
            NoneComparisonError,
            TemplateRuntimeError,
            build_source_snippet,
        )

        template_name = render_ctx.template_name
        lineno = render_ctx.line
        error_str = str(error).strip()

        # Handle empty error messages (e.g., StopIteration, bare exceptions)
        if not error_str:
            error_type = type(error).__name__
            if hasattr(error, "args") and error.args:
                non_empty = [str(a) for a in error.args if str(a).strip()]
                if non_empty:
                    error_str = f"{error_type}: {', '.join(non_empty)}"
                else:
                    error_str = f"{error_type} (no details available)"
            else:
                error_str = f"{error_type} (no details available)"

        # Build source snippet from template source
        snippet = None
        source = self._source
        if source and lineno:
            snippet = build_source_snippet(source, lineno)

        # Handle None comparison errors specially
        if isinstance(error, TypeError) and "NoneType" in error_str:
            return NoneComparisonError(
                None,
                None,
                template_name=template_name,
                lineno=lineno,
                expression="<see stack trace>",
                source_snippet=snippet,
            )

        return TemplateRuntimeError(
            error_str,
            template_name=template_name,
            lineno=lineno,
            source_snippet=snippet,
        )

    async def render_async(self, *args: Any, **kwargs: Any) -> str:
        """Async wrapper for synchronous render.

        Runs the synchronous ``render()`` method in a thread pool to avoid
        blocking the event loop.
        """
        import asyncio

        return await asyncio.to_thread(self.render, *args, **kwargs)

    @property
    def is_async(self) -> bool:
        """True if this template uses async constructs (async for / await).

        Part of RFC: rfc-async-rendering.
        """
        return self._namespace.get("_is_async", False)

    async def render_stream_async(self, *args: Any, **kwargs: Any):
        """Render template as an async generator of HTML chunks.

        For templates with async constructs ({% async for %}, {{ await }}),
        this calls the native async render function. For sync templates,
        it wraps the sync render_stream() in an async generator.

        Args:
            *args: Single dict of context variables
            **kwargs: Context variables as keyword arguments

        Yields:
            str: HTML chunks as they are produced

        Example:
            >>> async for chunk in t.render_stream_async(tokens=llm_stream):
            ...     await send(chunk)

        Part of RFC: rfc-async-rendering.
        """
        from kida.render_context import async_render_context

        ctx: dict[str, Any] = {}
        ctx.update(self._env.globals)

        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                ctx.update(args[0])
            else:
                raise TypeError(
                    f"render_stream_async() takes at most 1 positional argument (a dict), "
                    f"got {len(args)}"
                )
        ctx.update(kwargs)

        cached_blocks = ctx.pop("_cached_blocks", {})
        cache_stats = ctx.pop("_cached_stats", None)

        # Use native async stream if available, else wrap sync stream
        async_func = self._render_stream_async_func
        sync_func = self._render_stream_func

        async with async_render_context(
            template_name=self._name,
            filename=self._filename,
            source=self._source,
            cached_blocks=cached_blocks,
            cache_stats=cache_stats,
        ) as render_ctx:
            blocks_arg = None
            if render_ctx.cached_blocks:
                cached_block_names = render_ctx.cached_block_names
                if cached_block_names:
                    blocks_arg = CachedBlocksDict(
                        None,
                        render_ctx.cached_blocks,
                        cached_block_names,
                        stats=render_ctx.cache_stats,
                    )

            if async_func is not None:
                async for chunk in async_func(ctx, blocks_arg):
                    if chunk is not None:
                        yield chunk
            elif sync_func is not None:
                # Wrap sync stream for API compatibility
                for chunk in sync_func(ctx, blocks_arg):
                    if chunk is not None:
                        yield chunk
            else:
                raise RuntimeError(
                    f"Template '{self._name or '(inline)'}' has no render_stream function"
                )

    async def render_block_stream_async(
        self, block_name: str, *args: Any, **kwargs: Any
    ):
        """Render a single block as an async stream.

        Looks up the async streaming block function first, falls back to
        the sync streaming block function wrapped in an async generator.

        Args:
            block_name: Name of the block to render
            *args: Single dict of context variables
            **kwargs: Context variables as keyword arguments

        Yields:
            str: HTML chunks as they are produced

        Part of RFC: rfc-async-rendering.
        """
        from kida.render_context import async_render_context

        # Try async variant first, fall back to sync
        async_func_name = f"_block_{block_name}_stream_async"
        sync_func_name = f"_block_{block_name}_stream"

        async_func = self._namespace.get(async_func_name)
        sync_func = self._namespace.get(sync_func_name)

        if async_func is None and sync_func is None:
            available = [
                k[7:]
                for k in self._namespace
                if k.startswith("_block_") and callable(self._namespace[k])
            ]
            raise KeyError(
                f"Block '{block_name}' not found in template '{self._name}'. "
                f"Available blocks: {available}"
            )

        ctx: dict[str, Any] = {}
        ctx.update(self._env.globals)

        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                ctx.update(args[0])
            else:
                raise TypeError(
                    f"render_block_stream_async() takes at most 1 positional argument "
                    f"(a dict), got {len(args)}"
                )
        ctx.update(kwargs)

        async with async_render_context(
            template_name=self._name,
            filename=self._filename,
            source=self._source,
        ):
            if async_func is not None:
                async for chunk in async_func(ctx, {}):
                    if chunk is not None:
                        yield chunk
            else:
                # Wrap sync block stream (sync_func guaranteed non-None by check above)
                assert sync_func is not None
                for chunk in sync_func(ctx, {}):
                    if chunk is not None:
                        yield chunk

    @staticmethod
    def _escape(value: Any) -> str:
        """HTML-escape a value.

        Uses optimized html_escape from utils.html module.
        Complexity: O(n) single-pass using str.translate().
        """
        return html_escape(value)

    @staticmethod
    def _safe_getattr(obj: Any, name: str) -> Any:
        """Get attribute with dict fallback and None-safe handling.

        Resolution order:
        - Dicts: subscript first (user data), getattr fallback (methods).
          This prevents dict method names like ``items``, ``keys``,
          ``values``, ``get`` from shadowing user data keys.
        - Objects: getattr first, subscript fallback.

        None Handling (like Hugo/Go templates):
        - If obj is None, returns UNDEFINED (prevents crashes)
        - If attribute value is None, returns "" (normalizes output)

        Not-Found Handling:
        - Returns the ``UNDEFINED`` sentinel when the attribute/key is
          not found.  ``UNDEFINED`` stringifies as ``""`` (so template
          output is unchanged) but ``is_defined()`` recognises it as
          *not defined*, fixing ``x.missing is defined`` → False.

        Complexity: O(1)
        """
        if obj is None:
            return UNDEFINED
        # Dicts: subscript first so keys like "items" resolve to user data,
        # not the dict.items method
        if isinstance(obj, dict):
            try:
                val = obj[name]
                return "" if val is None else val
            except KeyError:
                try:
                    val = getattr(obj, name)
                    return "" if val is None else val
                except AttributeError:
                    return UNDEFINED
        # Objects: getattr first, subscript fallback
        try:
            val = getattr(obj, name)
            return "" if val is None else val
        except AttributeError:
            try:
                val = obj[name]
                return "" if val is None else val
            except (KeyError, TypeError):
                return UNDEFINED

    @staticmethod
    def _getattr_preserve_none(obj: Any, name: str) -> Any:
        """Get attribute with dict fallback, preserving None values.

        Like _safe_getattr but preserves None values instead of converting
        to empty string. Used for optional chaining (?.) so that null
        coalescing (??) can work correctly.

        Resolution order matches _safe_getattr: dicts try subscript first.

        Complexity: O(1)
        """
        if isinstance(obj, dict):
            try:
                return obj[name]
            except KeyError:
                try:
                    return getattr(obj, name)
                except AttributeError:
                    return None
        try:
            return getattr(obj, name)
        except AttributeError:
            try:
                return obj[name]
            except (KeyError, TypeError):
                return None

    def __repr__(self) -> str:
        return f"<Template {self._name or '(inline)'}>"


class RenderedTemplate:
    """Lazy rendered template with streaming support.

    Wraps a Template + context pair. Supports both full rendering
    via ``str()`` and chunk-by-chunk iteration via ``for chunk in rt``.

    Example:
        >>> rt = RenderedTemplate(template, {"name": "World"})
        >>> print(str(rt))          # Full render
        'Hello, World!'
        >>> for chunk in rt:        # Streaming render
        ...     send(chunk)
    """

    __slots__ = ("_context", "_template")

    def __init__(self, template: Template, context: dict[str, Any]):
        self._template = template
        self._context = context

    def __str__(self) -> str:
        """Render and return full string."""
        return self._template.render(self._context)

    def __iter__(self):
        """Iterate over rendered HTML chunks via render_stream()."""
        yield from self._template.render_stream(self._context)
