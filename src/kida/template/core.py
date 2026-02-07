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
from kida.template.loop_context import LoopContext
from kida.utils.html import Markup, html_escape

if TYPE_CHECKING:
    import ast
    import types

    from kida.analysis import TemplateMetadata
    from kida.environment import Environment
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
        "_env_ref",
        "_code",
        "_name",
        "_filename",
        "_render_func",
        "_render_async_func",
        "_optimized_ast",  # Preserved AST for introspection (or None)
        "_metadata_cache",  # Cached analysis results
        "_namespace",  # Compiled namespace with block functions
    )

    def __init__(
        self,
        env: Environment,
        code: types.CodeType,
        name: str | None,
        filename: str | None,
        optimized_ast: ast.Module | None = None,
    ):
        """Initialize template with compiled code.

        Args:
            env: Parent Environment (stored as weak reference)
            code: Compiled Python code object
            name: Template name (for error messages)
            filename: Source filename (for error messages)
            optimized_ast: Optional preserved AST for introspection.
                If None, introspection methods return empty results.
        """
        # Use weakref to prevent circular reference: Template <-> Environment
        self._env_ref: weakref.ref[Environment] = weakref.ref(env)
        self._code = code
        self._name = name
        self._filename = filename
        self._optimized_ast = optimized_ast
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
                raise RuntimeError("Environment has been garbage collected")
            try:
                included = _env.get_template(template_name)

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
                raise RuntimeError("Environment has been garbage collected")
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

        # Import macros from another template
        def _import_macros(
            template_name: str, with_context: bool, context: dict[str, Any]
        ) -> dict[str, Any]:
            _env = env_ref()
            if _env is None:
                raise RuntimeError("Environment has been garbage collected")
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
                "_import_macros": _import_macros,
                "_cache_get": _cache_get,
                "_cache_set": _cache_set,
                "_LoopContext": LoopContext,
                # RFC: kida-contextvar-patterns - for generated code line tracking
                "_get_render_ctx": get_render_context_required,
            }
        )
        exec(code, namespace)
        self._render_func = namespace.get("render")
        self._render_async_func = namespace.get("render_async")
        self._namespace = namespace  # Keep for render_block()

    @property
    def _env(self) -> Environment:
        """Get the Environment (dereferences weak reference)."""
        env = self._env_ref()
        if env is None:
            raise RuntimeError("Environment has been garbage collected")
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
            raise RuntimeError("Template not properly compiled")

        with render_context(
            template_name=self._name,
            filename=self._filename,
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
        ) as render_ctx:
            try:
                result: str = block_func(ctx, {})
                return result
            except TemplateRuntimeError:
                raise
            except Exception as e:
                from kida.environment.exceptions import TemplateNotFoundError, UndefinedError

                if isinstance(e, (UndefinedError, TemplateNotFoundError)):
                    raise
                raise self._enhance_error(e, render_ctx) from e

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
        template name and line number context read from RenderContext.
        """
        from kida.environment.exceptions import (
            NoneComparisonError,
            TemplateRuntimeError,
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

        # Handle None comparison errors specially
        if isinstance(error, TypeError) and "NoneType" in error_str:
            return NoneComparisonError(
                None,
                None,
                template_name=template_name,
                lineno=lineno,
                expression="<see stack trace>",
            )

        return TemplateRuntimeError(
            error_str,
            template_name=template_name,
            lineno=lineno,
        )

    async def render_async(self, *args: Any, **kwargs: Any) -> str:
        """Async wrapper for synchronous render.

        Runs the synchronous ``render()`` method in a thread pool to avoid
        blocking the event loop.
        """
        import asyncio

        return await asyncio.to_thread(self.render, *args, **kwargs)

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

        Handles both:
        - obj.attr for objects with attributes
        - dict['key'] for dict-like objects

        None Handling (like Hugo/Go templates):
        - If obj is None, returns "" (prevents crashes)
        - If attribute value is None, returns "" (normalizes output)

        Complexity: O(1)
        """
        if obj is None:
            return ""
        try:
            val = getattr(obj, name)
            return "" if val is None else val
        except AttributeError:
            try:
                val = obj[name]
                return "" if val is None else val
            except (KeyError, TypeError):
                return ""

    @staticmethod
    def _getattr_preserve_none(obj: Any, name: str) -> Any:
        """Get attribute with dict fallback, preserving None values.

        Like _safe_getattr but preserves None values instead of converting
        to empty string. Used for optional chaining (?.) so that null
        coalescing (??) can work correctly.

        Complexity: O(1)
        """
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
    """Lazy rendered template (for streaming).

    Allows iteration over rendered chunks for streaming output.
    Not implemented in initial version.

    """

    __slots__ = ("_template", "_context")

    def __init__(self, template: Template, context: dict[str, Any]):
        self._template = template
        self._context = context

    def __str__(self) -> str:
        """Render and return full string."""
        return self._template.render(self._context)

    def __iter__(self) -> Any:
        """Iterate over rendered chunks."""
        yield str(self)
