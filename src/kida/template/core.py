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
from typing import TYPE_CHECKING, Any, cast

from kida.template.cached_blocks import CachedBlocksDict
from kida.template.error_enhancement import enhance_template_error
from kida.template.helpers import (
    STATIC_NAMESPACE,
    add_polymorphic,
    coerce_numeric,
    default_safe,
    getattr_preserve_none,
    is_defined,
    lookup,
    lookup_scope,
    null_coalesce,
    optional_call,
    safe_getattr,
    spaceless,
    str_safe,
)
from kida.template.inheritance import TemplateInheritanceMixin
from kida.template.introspection import TemplateIntrospectionMixin
from kida.template.loop_context import AsyncLoopContext, LoopContext
from kida.template.render_helpers import make_render_helpers
from kida.utils.html import html_escape


def _make_error_dict(exc: BaseException) -> dict[str, Any]:
    """Build error dict for {% try %}...{% fallback name %} error binding."""
    return {
        "message": str(exc),
        "type": type(exc).__name__,
        "template": getattr(exc, "template_name", getattr(exc, "template", None)),
        "line": getattr(exc, "lineno", None),
    }


if TYPE_CHECKING:
    import types
    from collections.abc import AsyncIterator, Callable, Iterator

    from kida.analysis import DefMetadata, TemplateMetadata
    from kida.environment import Environment
    from kida.nodes import Template as TemplateNode


class Template(TemplateInheritanceMixin, TemplateIntrospectionMixin):
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
        "_block_names",  # Local block names for CachedBlocksDict / render_with_blocks
        "_code",
        "_def_metadata_cache",  # Cached def introspection results
        "_effective_blocks_cache",  # kind -> effective inherited block map
        "_env_ref",
        "_extends_target",  # Literal parent name for inherited block lookup (or None)
        "_filename",
        "_inheritance_chain_cache",  # Cached [self, parent, ...] resolution
        "_local_blocks_async_stream",  # Local async stream block funcs
        "_local_blocks_stream",  # Local stream block funcs
        "_local_blocks_sync",  # Local sync block funcs
        "_metadata_cache",  # Cached analysis results
        "_name",
        "_namespace",  # Compiled namespace with block functions
        "_optimized_ast",  # Preserved AST for introspection (or None)
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
        precomputed: list[Any] | None = None,
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
                Stored for use by enhance_template_error() to provide source
                context in TemplateRuntimeError exceptions.
            precomputed: Values that the partial evaluator folded but that
                cannot be stored in ``ast.Constant`` nodes (dict, list, etc.).
                Injected into the exec namespace as ``_pc_0``, ``_pc_1``, ...
        """
        # Use weakref to prevent circular reference: Template <-> Environment
        self._env_ref: weakref.ref[Environment] = weakref.ref(env)
        self._code = code
        self._name = name
        self._filename = filename
        self._optimized_ast = optimized_ast
        self._source = source
        self._compile_warnings: list = []  # TemplateWarning instances
        self._def_metadata_cache: dict[str, DefMetadata] | None = None
        self._metadata_cache: TemplateMetadata | None = None
        self._inheritance_chain_cache: tuple[Template, ...] | None = None
        self._effective_blocks_cache: dict[str, dict[str, Any]] = {}

        # Build render helpers from factory (extracted to render_helpers.py)
        env_ref = self._env_ref
        helpers = make_render_helpers(env_ref)

        # Execute the code to get the render function
        # Start with shared static namespace (copied once, not constructed)
        namespace: dict[str, Any] = STATIC_NAMESPACE.copy()

        # Import RenderContext getter for generated code
        # Import exception types for {% try %}...{% fallback %} error boundaries
        from kida.exceptions import TemplateRuntimeError, UndefinedError
        from kida.render_context import NULL_RENDER_CONTEXT, get_render_context

        # Select escape function based on autoescape mode
        _autoescape = env.autoescape
        if _autoescape == "terminal":
            from kida.utils.terminal_escape import ansi_sanitize

            escape_func = ansi_sanitize
        elif _autoescape == "markdown":
            from kida.utils.markdown_escape import Marked, markdown_escape

            escape_func = markdown_escape
            namespace["_Markup"] = Marked
        elif callable(_autoescape):
            # Per-template callable — resolve for this template name
            _autoescape_fn = cast("Callable[[str | None], bool]", _autoescape)
            escape_func = html_escape if _autoescape_fn(name) else str
        elif _autoescape:
            escape_func = html_escape
        else:
            escape_func = str

        # Add per-template dynamic entries
        namespace.update(
            {
                "_env": env,
                "_filters": env._filters,
                "_tests": env._tests,
                "_escape": escape_func,
                "_getattr": safe_getattr,
                "_getattr_none": getattr_preserve_none,
                "_lookup": lookup,
                "_lookup_scope": lookup_scope,
                "_default_safe": default_safe,
                "_is_defined": is_defined,
                "_null_coalesce": null_coalesce,
                "_optional_call": optional_call,
                "_add_polymorphic": add_polymorphic,
                "_coerce_numeric": coerce_numeric,
                "_spaceless": spaceless,
                "_str_safe": str_safe,
                "_include": helpers["_include"],
                "_extends": helpers["_extends"],
                "_include_stream": helpers["_include_stream"],
                "_extends_stream": helpers["_extends_stream"],
                "_include_stream_async": helpers["_include_stream_async"],
                "_extends_stream_async": helpers["_extends_stream_async"],
                "_import_macros": helpers["_import_macros"],
                "_cache_get": helpers["_cache_get"],
                "_cache_set": helpers["_cache_set"],
                "_LoopContext": LoopContext,
                "_AsyncLoopContext": AsyncLoopContext,
                # RFC: kida-contextvar-patterns - for generated code line tracking
                "_get_render_ctx": get_render_context,
                "_null_rc": NULL_RENDER_CONTEXT,
                # Error boundary exception types for {% try %}...{% fallback %}
                "_TemplateRuntimeError": TemplateRuntimeError,
                "_UndefinedError": UndefinedError,
                "_TypeError": TypeError,
                "_ValueError": ValueError,
                "_make_error_dict": _make_error_dict,
                # i18n: gettext/ngettext for {% trans %} blocks
                # Use lambdas to read env._gettext/_ngettext at render time,
                # not compile time — allows install_translations() after compilation.
                "_gettext": lambda s, _env=env: _env._gettext(s),
                "_ngettext": lambda s, p, n, _env=env: _env._ngettext(s, p, n),
            }
        )
        # Inject precomputed constants (non-constant-safe values from partial eval).
        # All block functions live in this same namespace, so _pc_N bindings are
        # visible to blocks and render_block() without additional injection.
        if precomputed is not None:
            for idx, value in enumerate(precomputed):
                namespace[f"_pc_{idx}"] = value

        # Apply sandbox restrictions if environment is sandboxed
        from kida.sandbox import SandboxedEnvironment, patch_template_namespace

        if isinstance(env, SandboxedEnvironment):
            patch_template_namespace(namespace, env._get_sandbox_policy())

        exec(code, namespace)
        self._render_func = namespace.get("render")
        self._render_stream_func = namespace.get("render_stream")
        self._render_stream_async_func = namespace.get("render_stream_async")
        self._namespace = namespace  # Keep for render_block()
        self._extends_target = namespace.get("_extends_target")
        (
            self._local_blocks_sync,
            self._local_blocks_stream,
            self._local_blocks_async_stream,
        ) = self._build_local_block_maps(namespace)
        self._block_names = tuple(self._local_blocks_sync.keys())

    @property
    def _env(self) -> Environment:
        """Get the Environment (dereferences weak reference)."""
        env = self._env_ref()
        if env is None:
            from kida.exceptions import ErrorCode, TemplateRuntimeError

            raise TemplateRuntimeError(
                f"Environment has been garbage collected (template: {self._name or 'unknown'})",
                template_name=self._name,
                code=ErrorCode.ENV_GARBAGE_COLLECTED,
                suggestion="Keep a reference to the Environment for the lifetime of its templates.",
            )
        return env

    def _get_env_limits(self) -> tuple[int, int]:
        """Get max_extends_depth and max_include_depth from Environment (or defaults)."""
        env = self._env_ref()
        if env is None:
            return (50, 50)
        return (env.max_extends_depth, env.max_include_depth)

    def _get_max_output_size(self) -> int | None:
        """Get max_output_size from sandbox policy, if any."""
        env = self._env_ref()
        if env is None:
            return None
        from kida.sandbox import SandboxedEnvironment

        if isinstance(env, SandboxedEnvironment):
            return env._get_sandbox_policy().max_output_size
        return None

    def _check_output_size(self, output: str) -> str:
        """Enforce max_output_size if sandbox policy sets one."""
        limit = self._get_max_output_size()
        if limit is not None and len(output) > limit:
            from kida.exceptions import ErrorCode
            from kida.sandbox import SecurityError

            raise SecurityError(
                f"Render output size ({len(output)} chars) exceeds sandbox limit of {limit}",
                code=ErrorCode.OUTPUT_LIMIT,
                suggestion=f"Reduce template output, or increase "
                f"SandboxPolicy(max_output_size={limit * 2}) if this is intentional.",
            )
        return output

    def _build_context(
        self, args: tuple[Any, ...], kwargs: dict[str, Any], method_name: str
    ) -> dict[str, Any]:
        """Build render context from args and kwargs.

        Shared by render, render_block, render_with_blocks, render_stream,
        render_stream_async, render_block_stream_async.
        """
        if args:
            if len(args) != 1 or not isinstance(args[0], dict):
                raise TypeError(
                    f"{method_name}() takes at most 1 positional argument (a dict), got {len(args)}"
                )
            # Single-pass merge: globals | positional dict | keyword overrides
            return {**self._env.globals, **args[0], **kwargs}
        if kwargs:
            return {**self._env.globals, **kwargs}
        # Common case: no args, no kwargs — copy globals only
        env_globals = self._env.globals
        return dict(env_globals) if env_globals else {}

    def _run_globals_setup_chain(self, ctx: dict[str, Any]) -> None:
        """Apply ``_globals_setup`` along the ``{% extends %}`` chain.

        ``_inheritance_chain()`` is ``[leaf, parent, …, root]``. Full ``render()``
        runs each template's top-level statements (imports, defs, ``{% let %}``, …)
        before calling ``_extends``, so effective order is **leaf → root**; later
        templates win on ``ctx`` name clashes, matching full-page render.

        ``render_block`` / ``render_with_blocks`` must mirror that order so fragment
        scope matches a full page render for HTMX partials.
        """
        # Reuse ``_inheritance_chain_cache`` when populated (e.g. after
        # ``_effective_block_map`` in ``render_block``) so we do not call
        # ``_inheritance_chain()`` again per render — same cost model as before
        # globals-setup chaining.
        if not self._env.auto_reload:
            chain = self._inheritance_chain_cache
            if chain is None:
                chain = self._inheritance_chain()
        else:
            chain = self._inheritance_chain()
        for tmpl in chain:
            gs = tmpl._namespace.get("_globals_setup")
            if gs is not None:
                gs(ctx)

    # ------------------------------------------------------------------
    # Render scaffold — shared setup for all render variants
    # ------------------------------------------------------------------

    from contextlib import contextmanager as _contextmanager

    @_contextmanager
    def _render_scaffold(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        method_name: str,
        *,
        use_cached_blocks: bool = False,
        enhance_errors: bool = True,
    ) -> Iterator[tuple[dict[str, Any], Any, Any]]:
        """Common setup for sync render methods.

        Builds context, sets up RenderContext, prepares blocks arg, and
        optionally enhances exceptions.

        Yields:
            (ctx, render_ctx, blocks_arg) tuple
        """
        from kida.render_context import get_render_context, render_context

        ctx = self._build_context(args, kwargs, method_name)

        cached_blocks: dict[str, str] = {}
        cache_stats: dict[str, int] | None = None
        if use_cached_blocks:
            cached_blocks = ctx.pop("_cached_blocks", {})
            cache_stats = ctx.pop("_cached_stats", None)

        parent_ctx = get_render_context()
        parent_meta = parent_ctx._meta if parent_ctx else None
        max_extends, max_include = self._get_env_limits()

        with render_context(
            template_name=self._name,
            filename=self._filename,
            source=self._source,
            cached_blocks=cached_blocks,
            cache_stats=cache_stats,
            parent_meta=parent_meta,
            max_extends_depth=max_extends,
            max_include_depth=max_include,
        ) as render_ctx:
            blocks_arg = None
            if use_cached_blocks and render_ctx.cached_blocks:
                cached_block_names = render_ctx.cached_block_names
                if cached_block_names:
                    blocks_arg = CachedBlocksDict(
                        None,
                        render_ctx.cached_blocks,
                        cached_block_names,
                        stats=render_ctx.cache_stats,
                    )

            if not enhance_errors:
                yield ctx, render_ctx, blocks_arg
                return

            from kida.exceptions import (
                TemplateNotFoundError,
                TemplateRuntimeError,
                TemplateSyntaxError,
                UndefinedError,
            )

            try:
                yield ctx, render_ctx, blocks_arg
            except TemplateRuntimeError:
                raise
            except Exception as e:
                from kida.sandbox import SecurityError

                if isinstance(
                    e, (UndefinedError, TemplateNotFoundError, TemplateSyntaxError, SecurityError)
                ):
                    raise
                raise enhance_template_error(e, render_ctx, self._source) from e

    @property
    def warnings(self) -> list:
        """Compile-time warnings for this template."""
        return self._compile_warnings

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

        Context is passed as keyword arguments. Common keys include
        ``page``, ``site``, ``user`` — types vary by template.

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
        from kida.exceptions import TemplateRuntimeError

        # Guard: async templates must use render_stream_async()
        if self.is_async:
            raise TemplateRuntimeError(
                f"Template '{self._name or '(inline)'}' uses async constructs "
                f"(async for / await). Use render_stream_async() or "
                f"render_block_stream_async() instead of render().",
                template_name=self._name,
            )

        render_func = self._render_func
        if render_func is None:
            from kida.exceptions import ErrorCode, TemplateRuntimeError

            raise TemplateRuntimeError(
                f"Template '{self._name or '(inline)'}' not properly compiled",
                template_name=self._name,
                code=ErrorCode.NOT_COMPILED,
                suggestion="Ensure the template was compiled via env.get_template() or env.from_string().",
            )

        with self._render_scaffold(args, kwargs, "render", use_cached_blocks=True) as (
            ctx,
            _render_ctx,
            blocks_arg,
        ):
            return self._check_output_size(render_func(ctx, blocks_arg))

    def render_block(self, block_name: str, *args: Any, **kwargs: Any) -> str:
        """Render a single block from the template.

        Context is passed as keyword arguments. Common keys include
        ``page``, ``site``, ``user`` — types vary by template.

        Renders just the named block, useful for caching blocks that
        only depend on site-wide context (e.g., navigation, footer).
        Supports inherited blocks: descendant templates can render
        blocks defined only in a parent by name (e.g. render_block("sidebar")
        on a child that extends a base defining a sidebar block it does not override).

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
        effective = self._effective_block_map("sync")
        block_func = effective.get(block_name)

        if block_func is None:
            raise KeyError(
                f"Block '{block_name}' not found in template '{self._name}'. "
                f"Available blocks: {list(effective.keys())}"
            )

        with self._render_scaffold(args, kwargs, "render_block") as (
            ctx,
            _render_ctx,
            _blocks_arg,
        ):
            self._run_globals_setup_chain(ctx)
            return self._check_output_size(block_func(ctx, effective))

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
        render_func = self._render_func
        if render_func is None:
            from kida.exceptions import ErrorCode, TemplateRuntimeError

            raise TemplateRuntimeError(
                f"Template '{self._name or '(inline)'}' not properly compiled",
                template_name=self._name,
                code=ErrorCode.NOT_COMPILED,
                suggestion="Ensure the template was compiled via env.get_template() or env.from_string().",
            )

        # Build _blocks dict with callables matching the compiled signature:
        # block_func(ctx, _blocks) -> str
        _blocks: dict[str, Any] = {}
        for bname, html in block_overrides.items():
            # Use default arg to capture html by value (avoid closure over loop var)
            _blocks[bname] = lambda ctx, _blocks, _html=html: _html

        with self._render_scaffold(args, kwargs, "render_with_blocks") as (
            ctx,
            _render_ctx,
            _blocks_arg,
        ):
            self._run_globals_setup_chain(ctx)
            return self._check_output_size(render_func(ctx, _blocks))

    def render_stream(self, *args: Any, **kwargs: Any) -> Iterator[str]:
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
        from kida.exceptions import TemplateRuntimeError

        # Guard: async templates must use render_stream_async()
        if self.is_async:
            raise TemplateRuntimeError(
                f"Template '{self._name or '(inline)'}' uses async constructs "
                f"(async for / await). Use render_stream_async() instead of "
                f"render_stream().",
                template_name=self._name,
            )

        stream_func = self._render_stream_func
        if stream_func is None:
            from kida.exceptions import ErrorCode, TemplateRuntimeError

            raise TemplateRuntimeError(
                f"Template '{self._name or '(inline)'}' has no render_stream function",
                template_name=self._name,
                code=ErrorCode.NOT_COMPILED,
                suggestion="Ensure the template was compiled with streaming support.",
            )

        with self._render_scaffold(
            args, kwargs, "render_stream", use_cached_blocks=True, enhance_errors=False
        ) as (ctx, _render_ctx, blocks_arg):
            for chunk in stream_func(ctx, blocks_arg):
                if chunk is not None:
                    yield chunk

    def list_blocks(self) -> list[str]:
        """List all blocks available for render_block() (including inherited).

        Returns:
            List of block names available for render_block()
        """
        return list(self._effective_block_map("sync").keys())

    async def render_async(self, *args: Any, **kwargs: Any) -> str:
        """Async wrapper for synchronous templates.

        Runs ``render()`` in a thread pool to avoid blocking the event loop.
        Async templates (those with ``{% async for %}`` or ``{{ await ... }}``)
        are not supported by this method. Use ``render_stream_async()`` for
        native async template rendering.
        """
        import asyncio

        from kida.exceptions import TemplateRuntimeError

        if self.is_async:
            raise TemplateRuntimeError(
                f"Template '{self._name or '(inline)'}' uses async constructs "
                f"(async for / await). Use render_stream_async() instead of "
                f"render_async().",
                template_name=self._name,
            )
        return await asyncio.to_thread(self.render, *args, **kwargs)

    @property
    def is_async(self) -> bool:
        """True if this template uses async constructs (async for / await).

        Part of RFC: rfc-async-rendering.
        """
        return self._namespace.get("_is_async", False)

    async def render_stream_async(self, *args: Any, **kwargs: Any) -> AsyncIterator[str]:
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

        ctx = self._build_context(args, kwargs, "render_stream_async")
        cached_blocks = ctx.pop("_cached_blocks", {})
        cache_stats = ctx.pop("_cached_stats", None)

        # Use native async stream if available, else wrap sync stream
        async_func = self._render_stream_async_func
        sync_func = self._render_stream_func
        max_extends, max_include = self._get_env_limits()

        async with async_render_context(
            template_name=self._name,
            filename=self._filename,
            source=self._source,
            cached_blocks=cached_blocks,
            cache_stats=cache_stats,
            max_extends_depth=max_extends,
            max_include_depth=max_include,
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
                from kida.exceptions import ErrorCode, TemplateRuntimeError

                raise TemplateRuntimeError(
                    f"Template '{self._name or '(inline)'}' has no render_stream function",
                    template_name=self._name,
                    code=ErrorCode.NOT_COMPILED,
                    suggestion="Ensure the template was compiled with streaming support.",
                )

    async def render_block_stream_async(
        self, block_name: str, *args: Any, **kwargs: Any
    ) -> AsyncIterator[str]:
        """Render a single block as an async stream.

        Looks up the async streaming block function first, falls back to
        the sync streaming block function wrapped in an async generator.
        Supports inherited blocks like render_block().

        Args:
            block_name: Name of the block to render
            *args: Single dict of context variables
            **kwargs: Context variables as keyword arguments

        Yields:
            str: HTML chunks as they are produced

        Part of RFC: rfc-async-rendering.
        """
        import inspect

        from kida.render_context import async_render_context

        effective = self._effective_block_map("async_stream")
        block_func = effective.get(block_name)

        if block_func is None:
            raise KeyError(
                f"Block '{block_name}' not found in template '{self._name}'. "
                f"Available blocks: {list(effective.keys())}"
            )

        ctx = self._build_context(args, kwargs, "render_block_stream_async")
        max_extends, max_include = self._get_env_limits()

        async with async_render_context(
            template_name=self._name,
            filename=self._filename,
            source=self._source,
            max_extends_depth=max_extends,
            max_include_depth=max_include,
        ):
            if inspect.isasyncgenfunction(block_func):
                async for chunk in block_func(ctx, effective):
                    if chunk is not None:
                        yield chunk
            else:
                for chunk in block_func(ctx, effective):
                    if chunk is not None:
                        yield chunk

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
