"""Core Environment class for Kida template system.

The Environment is the central hub for template configuration, compilation,
and caching. It manages loaders, filters, tests, and global variables.

Thread-Safety:
- Immutable configuration after construction
- Copy-on-write for filters/tests/globals (no locking)
- LRU caches use RLock; _template_hashes, _analysis_cache, _structure_manifest_cache
  are protected by _cache_lock for concurrent get_template/get_template_structure
- Safe for concurrent get_template(), render(), and get_template_structure() calls

Example:
    >>> from kida import Environment, FileSystemLoader
    >>> env = Environment(
    ...     loader=FileSystemLoader("templates/"),
    ...     autoescape=True,
    ... )
    >>> env.get_template("page.html").render(page=page)

"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from kida.environment.filters import DEFAULT_FILTERS
from kida.environment.registry import FilterRegistry
from kida.environment.tests import DEFAULT_TESTS
from kida.exceptions import (
    TemplateError,
    TemplateNotFoundError,
    TemplateSyntaxError,
)
from kida.lexer import Lexer, LexerConfig
from kida.template import Template
from kida.utils.lru_cache import LRUCache
from kida.utils.template_keys import normalize_template_name, resolve_template_name


def _identity_gettext(message: str) -> str:
    """Default gettext: return message unchanged."""
    return message


def _identity_ngettext(singular: str, plural: str, n: int) -> str:
    """Default ngettext: select form by count."""
    return singular if n == 1 else plural


def _consume_global(key: str, default: Any = None) -> Any:
    """Template global: read a value from the nearest {% provide %} ancestor."""
    from kida.render_context import get_render_context

    rc = get_render_context()
    if rc is None:
        return default
    return rc.consume(key, default)


def _format_call_validation_parts(issue: Any) -> list[str]:
    """Format the individual problems in a component call validation result."""
    parts: list[str] = []
    if issue.unknown_params:
        parts.append(f"unknown params: {', '.join(issue.unknown_params)}")
    if issue.missing_required:
        parts.append(f"missing required: {', '.join(issue.missing_required)}")
    if issue.duplicate_params:
        parts.append(f"duplicate params: {', '.join(issue.duplicate_params)}")
    return parts


def _component_call_warning(issue: Any, template_name: str | None) -> Any:
    """Build a structured warning for a component call validation issue."""
    from kida.exceptions import ErrorCode, TemplateWarning

    parts = _format_call_validation_parts(issue)
    return TemplateWarning(
        code=ErrorCode.COMPONENT_CALL_SIGNATURE,
        message=f"Call to '{issue.def_name}' has invalid arguments: {'; '.join(parts)}",
        template_name=template_name,
        lineno=issue.lineno,
        suggestion="Check the component's {% def %} signature and rename, add, or remove arguments.",
    )


def _iter_nodes(root: Any) -> Any:
    """Yield AST nodes depth-first without depending on a visitor class."""
    yield root
    iter_child_nodes = getattr(root, "iter_child_nodes", None)
    if iter_child_nodes is None:
        return
    for child in iter_child_nodes():
        yield from _iter_nodes(child)


if TYPE_CHECKING:
    from collections.abc import Callable

    from kida.analysis.metadata import TemplateMetadata, TemplateStructureManifest
    from kida.bytecode_cache import BytecodeCache
    from kida.environment.protocols import Loader
    from kida.environment.terminal import TerminalCaps
    from kida.extensions import Extension
    from kida.nodes import Template as TemplateNode


# Default cache limits
#
# Rationale:
#   - TEMPLATE_CACHE: A typical site has 50-200 templates (pages, partials,
#     includes).  400 gives ~2x headroom for sites with many partials.
#   - FRAGMENT_CACHE: Fragments are smaller and more numerous (per-page
#     cached blocks).  1000 covers aggressive block-level caching.
#   - FRAGMENT_TTL: 5 minutes balances freshness against cache hit rate for
#     development hot-reload; production sites can raise this.


DEFAULT_TEMPLATE_CACHE_SIZE = 400
DEFAULT_FRAGMENT_CACHE_SIZE = 1000
DEFAULT_FRAGMENT_TTL = 300.0  # seconds
logger = logging.getLogger(__name__)


@dataclass
class Environment:
    """Central configuration and template management hub.

    The Environment holds all template engine settings and provides the primary
    API for loading and rendering templates. It manages three key concerns:

    1. **Template Loading**: Via configurable loaders (filesystem, dict, etc.)
    2. **Compilation Settings**: Autoescape, strict undefined handling
    3. **Runtime Context**: Filters, tests, and global variables

    Attributes:
        loader: Template source provider (FileSystemLoader, DictLoader, etc.)
        autoescape: HTML auto-escaping. True, False, callable(name) → bool,
            or a string: "terminal" (enable, ANSI-aware mode), "true" (enable),
            or "false" (disable). Any other string raises ValueError.
        auto_reload: Check template modification times (default: True)
        strict_none: Fail early on None comparisons during sorting (default: False)
        cache_size: Maximum compiled templates to cache (default: 400)
        fragment_cache_size: Maximum `{% cache %}` fragment entries (default: 1000)
        fragment_ttl: Fragment cache TTL in seconds (default: 300.0)
        bytecode_cache: Persistent bytecode cache configuration:
            - None (default): Auto-enabled for FileSystemLoader
            - False: Explicitly disabled
            - BytecodeCache instance: Custom cache directory
        globals: Variables available in all templates (includes Python builtins)

    Thread-Safety:
        All operations are safe for concurrent use:
        - Configuration is immutable after `__post_init__`
        - `add_filter()`, `add_test()`, `add_global()` use copy-on-write
        - `get_template()` uses lock-free LRU cache with atomic operations
        - `render()` uses only local state (StringBuilder pattern)

    Strict Mode:
        Undefined variables raise `UndefinedError` instead of returning empty
        string. Catches typos and missing context variables at render time.

            >>> env = Environment()
            >>> env.from_string("{{ typo_var }}").render()
        UndefinedError: Undefined variable 'typo_var' in <template>:1

            >>> env.from_string("{{ optional | default('N/A') }}").render()
            'N/A'

    Caching:
        Three cache layers for optimal performance:
        - **Bytecode cache** (disk): Persistent compiled bytecode via marshal.
          Auto-enabled for FileSystemLoader in `__pycache__/kida/`.
          Current cold-start gain is modest (~7-8% median in
          `benchmarks/benchmark_cold_start.py`); most startup time is import
          cost, so lazy imports or pre-compilation are required for larger
          improvements.
        - **Template cache** (memory): Compiled Template objects (keyed by name)
        - **Fragment cache** (memory): `{% cache key %}` block outputs

            >>> env.cache_info()
        {'template': {'size': 5, 'max_size': 400, 'hits': 100, 'misses': 5},
             'fragment': {'size': 12, 'max_size': 1000, 'hits': 50, 'misses': 12},
             'bytecode': {'file_count': 10, 'total_bytes': 45000}}

    Example:
            >>> from kida import Environment, FileSystemLoader
            >>> env = Environment(
            ...     loader=FileSystemLoader(["templates/", "shared/"]),
            ...     autoescape=True,
            ...     cache_size=100,
            ... )
            >>> env.add_filter("money", lambda x: f"${x:,.2f}")
            >>> env.get_template("invoice.html").render(total=1234.56)

    """

    # Configuration
    loader: Loader | None = None
    autoescape: bool | str | Callable[[str | None], bool] = True
    auto_reload: bool = True
    strict_none: bool = False  # When True, sorting with None values raises detailed errors
    strict_undefined: bool = True  # When True, missing attribute access raises UndefinedError
    jinja2_compat_warnings: bool = (
        True  # Warn when a nested {% set %} shadows an outer {% let %}/{% export %} binding
        # (the Jinja2 scoping trap). Set False to silence; or filter MigrationWarning
        # via warnings.filterwarnings.
    )

    # Template Introspection (RFC: kida-template-introspection)
    # True (default): Preserve AST, enable block_metadata()/depends_on()
    # False: Discard AST after compilation, save ~2x memory per template
    preserve_ast: bool = True

    # Cache configuration
    cache_size: int = DEFAULT_TEMPLATE_CACHE_SIZE
    fragment_cache_size: int = DEFAULT_FRAGMENT_CACHE_SIZE
    fragment_ttl: float = DEFAULT_FRAGMENT_TTL

    # Bytecode cache for persistent template caching
    # - None (default): Auto-detect from loader (enabled for FileSystemLoader)
    # - False: Explicitly disabled
    # - BytecodeCache instance: User-provided cache
    bytecode_cache: BytecodeCache | bool | None = None

    # Namespace aliases for template paths (RFC: relative-template-resolution)
    # Maps alias names to root-relative paths. References like
    # ``@components/card.html`` resolve to ``{root}/card.html`` before loader
    # lookup. Aliases resolve BEFORE relative paths — the two modes are
    # orthogonal (``@components/./foo`` is not supported).
    #
    # Example:
    #   Environment(
    #       loader=FileSystemLoader("templates/"),
    #       template_aliases={"components": "ui/components", "layouts": "ui/layouts"},
    #   )
    #   env.get_template("@components/card.html")  # → "ui/components/card.html"
    template_aliases: dict[str, str] | None = None

    # Static context for partial evaluation (RFC: partial-evaluation)
    # Values known at compile time.  When set, expressions that depend only
    # on these values are evaluated during compilation and replaced with
    # constants in the bytecode.  This enables near-``str.format()`` speed
    # for static regions (e.g. site.title, config.base_url).
    #
    # Applied automatically to all templates loaded via ``get_template()``.
    # ``from_string()`` accepts its own ``static_context`` kwarg which takes
    # precedence if provided.
    static_context: dict[str, Any] | None = None

    # Resolved bytecode cache (set in __post_init__)
    _bytecode_cache: BytecodeCache | None = field(init=False, default=None)

    # Lexer settings
    block_start: str = "{%"
    block_end: str = "%}"
    variable_start: str = "{{"
    variable_end: str = "}}"
    comment_start: str = "{#"
    comment_end: str = "#}"
    trim_blocks: bool = False
    lstrip_blocks: bool = False

    # Resource limits (DoS protection)
    # Configurable for deployments with deep template hierarchies
    max_extends_depth: int = 50  # Maximum {% extends %} chain depth
    max_include_depth: int = 50  # Maximum {% include %}/{% embed %} depth

    # Call-site validation (RFC: typed-def-parameters)
    # When True, validate {% call %} and {{ func() }} sites against {% def %}
    # signatures at compile time. Reports warnings for unknown params, missing
    # required params, and duplicate kwargs.
    validate_calls: bool = False

    # Profiling instrumentation (RFC: kida-contextvar-patterns)
    # When True, compiled templates include profiling hooks (_record_filter,
    # _record_macro, block timing) and call _get_accumulator() per function.
    # When False (default), all profiling AST is stripped at compile time —
    # zero ContextVar.get() calls, zero None checks per filter/block/macro.
    # Note: profiled_render() only collects data for templates compiled with
    # enable_profiling=True.
    enable_profiling: bool = False

    # Content capture instrumentation (RFC: render-capture)
    # When True, compiled templates include capture hooks that record block
    # content into a RenderCapture when captured_render() is active.
    # When False (default), all capture AST is stripped at compile time —
    # zero ContextVar.get() calls, zero None checks per block.
    # Note: captured_render() only collects data for templates compiled with
    # enable_capture=True.
    enable_capture: bool = False

    # F-string optimization (RFC: fstring-code-generation)
    # When True, consecutive output nodes are coalesced into single f-string appends
    fstring_coalescing: bool = True

    # User-defined pure filters (extends built-in set for f-string coalescing)
    # Filters in this set are assumed to have no side effects and can be coalesced
    pure_filters: set[str] = field(default_factory=set)

    # Component inlining (Phase 1.3: Compiler Intelligence)
    # When True, small {% def %} calls with all-constant arguments are expanded
    # inline at compile time during partial evaluation. Eliminates function call
    # overhead and enables further f-string coalescing of the inlined output.
    inline_components: bool = False

    # i18n optimization (RFC: i18n)
    # When True, {% trans %} blocks with no variables and no plural form are
    # compiled to direct string appends — but only when the identity gettext is
    # still installed at compile time. If real translations are later installed,
    # templates compiled under identity gettext keep the optimized path; re-compile
    # to pick up the new translations.
    optimize_translations: bool = False

    # HTMX integration (Feature 1.1: HTMX Context Detection)
    # When True (default), registers HTMX helper globals:
    #   - hx_request(), hx_target(), hx_trigger(), hx_boosted()
    #   - csrf_token()
    # Disable if you're not using HTMX or want to register manually
    enable_htmx_helpers: bool = True

    # Extensions (plugin architecture)
    # List of Extension subclasses (not instances) to register.
    # Each class is instantiated with this Environment on __post_init__.
    extensions: list[type] = field(default_factory=list)

    # Terminal mode overrides (only used when autoescape="terminal")
    terminal_color: str | None = None  # Override: "none", "basic", "256", "truecolor"
    terminal_width: int | None = None  # Override terminal width
    terminal_unicode: bool | None = None  # Override Unicode support
    ambiguous_width: int | None = None  # Override: 1 (narrow) or 2 (wide) for ambiguous chars

    # Globals (available in all templates)
    # Includes Python builtins commonly used in templates
    globals: dict[str, Any] = field(
        default_factory=lambda: {
            "range": range,
            "dict": dict,
            "list": list,
            "set": set,
            "tuple": tuple,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "sorted": sorted,
            "reversed": reversed,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "consume": _consume_global,
        }
    )

    # Filters and tests (copy-on-write)
    _filters: dict[str, Callable[..., Any]] = field(default_factory=lambda: DEFAULT_FILTERS.copy())
    _tests: dict[str, Callable[..., bool]] = field(default_factory=lambda: DEFAULT_TESTS.copy())

    # Template cache (LRU with size limit)
    _cache: LRUCache[str, Template] = field(init=False)
    _fragment_cache: LRUCache[str, str] = field(init=False)
    # Source hashes for cache invalidation (template_name -> source_hash)
    _template_hashes: dict[str, str] = field(init=False, default_factory=dict)
    # File mtimes for fast stale check (filename -> mtime_ns); skip hash when mtime unchanged
    _template_mtimes: dict[str, int] = field(init=False, default_factory=dict)
    # Shared analysis cache (template_name -> TemplateMetadata)
    # Prevents redundant analysis when multiple templates include the same partial
    _analysis_cache: dict[str, TemplateMetadata] = field(init=False, default_factory=dict)
    _structure_manifest_cache: dict[str, TemplateStructureManifest] = field(
        init=False,
        default_factory=dict,
    )
    _cache_lock: threading.RLock = field(init=False, default_factory=threading.RLock)
    _terminal_caps: TerminalCaps | None = field(init=False, default=None, repr=False)
    # Instantiated extensions and their tag/compiler registrations
    _extension_instances: list[Any] = field(init=False, default_factory=list)
    _extension_tags: dict[str, Any] = field(
        init=False, default_factory=dict
    )  # tag_name -> Extension
    _extension_compilers: dict[str, Any] = field(
        init=False, default_factory=dict
    )  # node_type -> Extension
    _extension_end_keywords: frozenset[str] = field(init=False, default_factory=frozenset)
    # Cached globals filtered to exclude UNDEFINED values (lazily populated)
    _filtered_globals: dict[str, Any] | None = field(init=False, default=None, repr=False)
    _filtered_globals_source: dict[str, Any] | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize derived configuration."""
        self._lexer_config = LexerConfig(
            block_start=self.block_start,
            block_end=self.block_end,
            variable_start=self.variable_start,
            variable_end=self.variable_end,
            comment_start=self.comment_start,
            comment_end=self.comment_end,
            trim_blocks=self.trim_blocks,
            lstrip_blocks=self.lstrip_blocks,
        )

        # Initialize LRU caches (uses kida.utils.lru_cache.LRUCache)
        self._cache: LRUCache[str, Template] = LRUCache(
            maxsize=self.cache_size,
            name="kida_template",
        )
        self._fragment_cache: LRUCache[str, str] = LRUCache(
            maxsize=self.fragment_cache_size,
            ttl=self.fragment_ttl,
            name="kida_fragment",
        )

        # Resolve bytecode cache
        self._bytecode_cache = self._resolve_bytecode_cache()

        # Per-source dedup for the from_string(no-name) bytecode-cache-bypass
        # warning. Keyed by bytecode_cache.hash_source(source) so the same
        # source warns once per Environment even if the caller rebuilds the
        # string each call.
        self._from_string_warned: set[str] = set()

        # Register HTMX helper globals (Feature 1.1)
        if self.enable_htmx_helpers:
            from kida.environment.globals import HTMX_GLOBALS

            self.globals.update(HTMX_GLOBALS)

        # Validate and normalize string autoescape modes eagerly (not at first compile)
        if isinstance(self.autoescape, str):
            mode = self.autoescape.strip().lower()
            if mode not in {"true", "false", "terminal", "markdown"}:
                msg = (
                    f"Unknown autoescape mode: {self.autoescape!r}. "
                    f"Valid modes: True, False, 'terminal', 'markdown', or a callable."
                )
                raise ValueError(msg)
            # Store normalized form so downstream comparisons work
            object.__setattr__(self, "autoescape", mode)

        # Terminal mode initialization
        if self.autoescape == "terminal":
            from kida.environment.terminal import _init_terminal_mode

            self._terminal_caps = _init_terminal_mode(
                self,
                self.terminal_color,
                self.terminal_width,
                self.terminal_unicode,
                self.ambiguous_width,
            )
        elif self.autoescape == "markdown":
            from kida.environment.markdown import _init_markdown_mode

            _init_markdown_mode(self)

        # Extension initialization
        if self.extensions:
            self._init_extensions()

        # i18n defaults: identity functions when no translations installed
        if "_" not in self.globals:
            self.globals["_"] = _identity_gettext
            self.globals["_n"] = _identity_ngettext
        self._gettext = self.globals.get("_", _identity_gettext)
        self._ngettext = self.globals.get("_n", _identity_ngettext)

    def _init_extensions(self) -> None:
        """Initialize registered extensions."""

        tag_map: dict[str, Extension] = {}
        compiler_map: dict[str, Extension] = {}
        end_kw: set[str] = set()

        for ext_cls in self.extensions:
            ext = ext_cls(self)
            self._extension_instances.append(ext)

            # Register filters, tests, globals
            for name, func in ext.get_filters().items():
                self._filters[name] = func
            for name, func in ext.get_tests().items():
                self._tests[name] = func
            self.globals.update(ext.get_globals())

            # Register tags (parser dispatch: tag name → extension)
            for tag in ext.tags:
                tag_map[tag] = ext
            end_kw.update(ext.end_keywords)

            # Register node types (compiler dispatch: node type name → extension)
            for node_type_name in ext.node_types:
                compiler_map[node_type_name] = ext

        self._extension_tags = tag_map
        self._extension_compilers = compiler_map
        self._extension_end_keywords = frozenset(end_kw)

    def _collect_imported_def_metadata(
        self, ast: TemplateNode, current_name: str | None
    ) -> dict[str, Any]:
        """Return visible imported component definitions for static validation.

        Only literal ``{% from "template" import name [as alias] %}`` imports
        are resolved. Dynamic imports and templates that fail to load are
        skipped so validation remains conservative.
        """
        from kida.nodes import Const, FromImport

        imported: dict[str, Any] = {}
        for node in _iter_nodes(ast):
            if not isinstance(node, FromImport):
                continue
            if not isinstance(node.template, Const) or not isinstance(node.template.value, str):
                continue
            template_name = node.template.value
            if current_name is not None and template_name == current_name:
                continue
            try:
                template = self.get_template(template_name)
            except TemplateError as exc:
                logger.debug(
                    "Skipping component validation metadata for %s imported by %s: %s",
                    template_name,
                    current_name,
                    exc,
                )
                continue
            meta = template.def_metadata()
            for original, alias in node.names:
                def_meta = meta.get(original)
                if def_meta is not None:
                    imported[alias or original] = def_meta
        return imported

    def install_translations(self, translations: Any) -> None:
        """Install a gettext translations object.

        The object must have gettext() and ngettext() methods
        (standard library gettext.GNUTranslations interface).
        """
        self.install_gettext_callables(
            gettext=translations.gettext,
            ngettext=translations.ngettext,
        )

    def install_gettext_callables(
        self,
        gettext: Any,
        ngettext: Any,
    ) -> None:
        """Install gettext/ngettext functions directly.

        These are registered as template globals `_` and `_n`, and
        stored as `_gettext`/`_ngettext` for compiler namespace access.
        """
        self.globals["_"] = gettext
        self.globals["_n"] = ngettext
        self._gettext = gettext
        self._ngettext = ngettext

    def _resolve_bytecode_cache(self) -> BytecodeCache | None:
        """Resolve bytecode cache from configuration.

        Auto-detection logic:
            - If bytecode_cache is False: disabled
            - If bytecode_cache is BytecodeCache: use it
            - If bytecode_cache is None and loader is FileSystemLoader:
              auto-create cache in first search path's __pycache__/kida/

        Returns:
            Resolved BytecodeCache or None if disabled/unavailable.
        """

        from kida.bytecode_cache import BytecodeCache
        from kida.environment.loaders import FileSystemLoader

        # Explicit disable
        if self.bytecode_cache is False:
            return None

        # User-provided cache
        if isinstance(self.bytecode_cache, BytecodeCache):
            return self.bytecode_cache

        # Auto-detect from FileSystemLoader
        if isinstance(self.loader, FileSystemLoader) and self.loader._paths:
            first_path = self.loader._paths[0]
            # Only auto-create cache when the path is absolute — a relative
            # or malformed path (e.g. from str(list_of_paths)) would pollute
            # the working directory with garbage.
            if not first_path.is_absolute():
                return None
            # Use __pycache__/kida/ in first search path (follows Python convention)
            cache_dir = first_path / "__pycache__" / "kida"
            return BytecodeCache(cache_dir)

        # No auto-detection possible (DictLoader, no loader, etc.)
        return None

    @property
    def filters(self) -> FilterRegistry:
        """Get filters as dict-like registry."""
        return FilterRegistry(self, "_filters")

    @property
    def tests(self) -> FilterRegistry:
        """Get tests as dict-like registry."""
        return FilterRegistry(self, "_tests")

    def add_filter(self, name: str, func: Callable[..., Any]) -> None:
        """Add a filter (copy-on-write).

        Args:
            name: Filter name (used in templates as {{ x | name }})
            func: Filter function

        If *func* was decorated with :func:`kida.pure`, the filter is
        automatically registered as pure, enabling compile-time evaluation
        when all inputs are statically known.
        """
        new_filters = self._filters.copy()
        new_filters[name] = func
        self._filters = new_filters

        # Auto-detect @pure decorator and register for partial evaluation
        if getattr(func, "_kida_pure", False):
            self.pure_filters = self.pure_filters | {name}

    def add_test(self, name: str, func: Callable[..., Any]) -> None:
        """Add a test (copy-on-write).

        Args:
            name: Test name (used in templates as {% if x is name %})
            func: Test function returning bool
        """
        new_tests = self._tests.copy()
        new_tests[name] = func
        self._tests = new_tests

    def add_global(self, name: str, value: Any) -> None:
        """Add a global variable (copy-on-write).

        Args:
            name: Global name (used in templates as {{ name }})
            value: Any value (variable, function, etc.)
        """
        new_globals = self.globals.copy()
        new_globals[name] = value
        self.globals = new_globals
        self._filtered_globals = None  # invalidate cache
        self._filtered_globals_source: dict[str, Any] | None = None

    def get_filtered_globals(self) -> dict[str, Any]:
        """Return globals dict with UNDEFINED values removed (cached).

        The result is cached, but the cache is automatically refreshed if
        the public ``globals`` mapping has been mutated or replaced since the
        last computation.
        """
        if self._filtered_globals is None or self._filtered_globals_source != self.globals:
            from kida.template.helpers import UNDEFINED

            self._filtered_globals = {k: v for k, v in self.globals.items() if v is not UNDEFINED}
            self._filtered_globals_source = self.globals.copy()
        return self._filtered_globals

    def update_filters(self, filters: dict[str, Callable[..., Any]]) -> None:
        """Add multiple filters at once (copy-on-write).

        Args:
            filters: Dict mapping filter names to functions

        Example:
            >>> env.update_filters({"double": lambda x: x * 2, "triple": lambda x: x * 3})
        """
        new_filters = self._filters.copy()
        new_filters.update(filters)
        self._filters = new_filters

    def update_tests(self, tests: dict[str, Callable[..., Any]]) -> None:
        """Add multiple tests at once (copy-on-write).

        Args:
            tests: Dict mapping test names to functions

        Example:
            >>> env.update_tests({"positive": lambda x: x > 0, "negative": lambda x: x < 0})
        """
        new_tests = self._tests.copy()
        new_tests.update(tests)
        self._tests = new_tests

    def get_template(self, name: str, *, caller: str | None = None) -> Template:
        """Load and cache a template by name.

        Args:
            name: Template identifier (e.g., ``"index.html"``). May start
                with ``./`` or ``../`` for resolution relative to the
                calling template — see ``caller``.
            caller: Logical name of the template issuing the request.
                Required when ``name`` is a relative path. Supplied
                automatically by ``{% include %}``, ``{% extends %}``,
                ``{% embed %}``, and ``{% from ... import ... %}`` at
                render time.

        Returns:
            Compiled Template object

        Raises:
            TemplateNotFoundError: If template doesn't exist, the name is
                relative without a caller, or resolution escapes the
                template root.
            TemplateSyntaxError: If template has syntax errors

        Note:
            With auto_reload=True (default), templates are checked for source changes
            using hash comparison. If source changed, cache is invalidated and template
            is reloaded. This ensures templates reflect filesystem changes.
        """
        if self.loader is None:
            from kida.exceptions import ErrorCode, TemplateRuntimeError

            raise TemplateRuntimeError(
                "No loader configured",
                code=ErrorCode.NO_LOADER,
                suggestion="Pass a loader to Environment: "
                "Environment(loader=FileSystemLoader('templates/'))",
            )

        if name.startswith("@"):
            name = self._resolve_alias(name)

        name = resolve_template_name(name, caller=caller)

        # Fast path: cache hit when auto_reload=False (avoids _cache_lock overhead)
        if not self.auto_reload:
            cached: Template | None = self._cache.get(name)
            if cached is not None:
                return cached

        with self._cache_lock:
            # Check cache (thread-safe LRU)
            cached = self._cache.get(name)
            if cached is not None:
                # With auto_reload=True, verify source hasn't changed
                if self.auto_reload:
                    if self._is_template_stale(name):
                        # Source changed - invalidate cache and reload
                        self._cache.delete(name)
                        self._template_hashes.pop(name, None)
                        self._template_mtimes.pop(name, None)
                        self._analysis_cache.pop(name, None)  # Invalidate analysis cache
                    else:
                        # Source unchanged - return cached template
                        template: Template = cached
                        return template
                else:
                    # auto_reload=False - return cached without checking
                    template = cached
                    return template

            # Load and compile
            source, filename = self.loader.get_source(name)

            # Compute source hash for cache invalidation
            from kida.bytecode_cache import hash_source

            source_hash = hash_source(source)

            template = self._compile(
                source,
                name,
                filename,
                static_context=self.static_context,
            )

            # Update cache (LRU handles eviction)
            self._cache.set(name, template)
            self._template_hashes[name] = source_hash
            # Record mtime for fast stale checks (skip hash when mtime unchanged)
            if filename is not None:
                try:
                    self._template_mtimes[name] = Path(filename).stat().st_mtime_ns
                except OSError:
                    self._template_mtimes.pop(name, None)

            return template

    def _resolve_alias(self, name: str) -> str:
        """Substitute ``@alias/path`` with the configured alias root.

        Raises TemplateNotFoundError when the alias is unknown or when no
        aliases are configured on this Environment.
        """
        rest = name[1:]  # strip leading '@'
        if "/" in rest:
            alias_key, alias_path = rest.split("/", 1)
        else:
            alias_key, alias_path = rest, ""

        aliases = self.template_aliases or {}
        if alias_key not in aliases:
            configured = sorted(f"@{k}/" for k in aliases)
            hint = (
                f"Configured aliases: {', '.join(configured)}"
                if configured
                else "No template aliases are configured on this Environment."
            )
            raise TemplateNotFoundError(f"Unknown template alias '@{alias_key}/'. {hint}")

        root = aliases[alias_key].strip("/")
        return f"{root}/{alias_path}" if alias_path else root

    def from_string(
        self,
        source: str,
        name: str | None = None,
        *,
        static_context: dict[str, Any] | None = None,
    ) -> Template:
        """Compile a template from a string.

        Args:
            source: Template source code
            name: Template name for error messages and bytecode caching.
                When a ``bytecode_cache`` is configured, providing a name
                enables persistent caching of the compiled template.
                Without a name, the template is compiled fresh each time.
            static_context: Values known at compile time.  Expressions
                that depend only on these values are evaluated during
                compilation and replaced with constants in the bytecode.
                This enables near-``str.format()`` speed for static regions.

        Returns:
            Compiled Template object

        Note:
            String templates are NOT cached in the in-memory LRU cache.
            Use ``get_template()`` with a loader for in-memory caching.

        Example:
            >>> site = {"title": "My Blog", "nav": [...]}
            >>> tmpl = env.from_string(
            ...     "<title>{{ site.title }}</title>",
            ...     static_context={"site": site},
            ... )
            >>> tmpl.render()  # site.title is pre-baked as "My Blog"
            '<title>My Blog</title>'
        """
        # Use provided static_context, or fall back to environment-level
        resolved_static = static_context if static_context is not None else self.static_context
        return self._compile(source, name, None, static_context=resolved_static)

    def _compile(
        self,
        source: str,
        name: str | None,
        filename: str | None,
        *,
        static_context: dict[str, Any] | None = None,
    ) -> Template:
        """Compile template source to Template object.

        Uses bytecode cache when configured for fast cold-start.
        Preserves AST for introspection when self.preserve_ast=True (default).

        When ``static_context`` is provided, runs a partial evaluation pass
        before compilation to replace static expressions with constants.
        """
        # Check bytecode cache first (for fast cold-start). If static_context
        # is used for partial evaluation, include a deterministic context hash.
        source_hash = None
        context_hash = _hash_static_context(static_context)
        if self._bytecode_cache is not None and name is None:
            from kida.bytecode_cache import hash_source

            warn_key = hash_source(source)
            if warn_key not in self._from_string_warned:
                import warnings

                self._from_string_warned.add(warn_key)
                warnings.warn(
                    "from_string() without name= bypasses bytecode cache. "
                    "Pass name='my_template' to enable caching.",
                    stacklevel=3,
                )
        if self._bytecode_cache is not None and name is not None:
            from kida.bytecode_cache import hash_source

            source_hash = hash_source(source)
            cached_code, cached_ast, cached_precomputed = self._bytecode_cache.get(
                name, source_hash, context_hash=context_hash
            )
            if cached_code is not None:
                # Resolve AST for introspection when preserve_ast is enabled.
                # Prefer the cached (pickled) AST to avoid a full re-parse.
                # Fall back to re-parsing when the cached AST is absent (old
                # cache entry) or if pickle.loads raised an exception (the
                # cache's get() already handled that and returned None).
                optimized_ast = None
                if self.preserve_ast:
                    if cached_ast is not None:
                        optimized_ast = cast("TemplateNode", cached_ast)
                    else:
                        from kida.parser import Parser

                        lexer = Lexer(source, self._lexer_config)
                        tokens = list(lexer.tokenize())
                        should_escape = self.select_autoescape(name)
                        parser = Parser(
                            tokens,
                            name,
                            filename,
                            source,
                            autoescape=should_escape,
                            extension_tags=self._extension_tags or None,
                        )
                        optimized_ast = parser.parse()

                return Template(
                    self,
                    cached_code,
                    name,
                    filename,
                    optimized_ast=optimized_ast,
                    source=source,
                    precomputed=cached_precomputed,
                )

        # Tokenize
        from kida.parser import Parser

        lexer = Lexer(source, self._lexer_config)
        tokens = list(lexer.tokenize())

        # Determine autoescape setting for this template
        # Terminal mode uses its own escape function; the parser just needs a bool
        should_escape = self.select_autoescape(name)

        # Parse (pass source for rich error messages)
        parser = Parser(
            tokens,
            name,
            filename,
            source,
            autoescape=should_escape,
            extension_tags=self._extension_tags or None,
        )
        ast = parser.parse()

        # Dead code elimination: remove const-only dead branches (always runs)
        from kida.compiler.partial_eval import eliminate_dead_code

        ast = eliminate_dead_code(ast)

        # Partial evaluation: replace static expressions with constants
        if static_context:
            from kida.compiler.partial_eval import partial_evaluate

            # Provide the escape function so folded Output nodes are
            # correctly escaped at compile time (prevents XSS from
            # static_context strings bypassing runtime escaping).
            escape_fn = None
            if should_escape:
                from kida.utils.html import Markup

                escape_fn = Markup.escape

            from kida.utils.constants import PURE_FILTERS_ALL

            ast = partial_evaluate(
                ast,
                static_context,
                escape_func=escape_fn,
                pure_filters=PURE_FILTERS_ALL | frozenset(self.pure_filters),
                filter_callables=self._filters,
                inline_components=self.inline_components,
            )

        validation_warnings: list[Any] = []

        # Call-site validation (RFC: typed-def-parameters)
        if self.validate_calls:
            from kida.analysis.analyzer import BlockAnalyzer

            analyzer = BlockAnalyzer()
            imported_defs = self._collect_imported_def_metadata(ast, name)
            call_issues = analyzer.validate_calls_with_external_defs(ast, imported_defs)
            validation_warnings.extend(
                _component_call_warning(issue, name or "<string>") for issue in call_issues
            )

        # Preserve AST for introspection if enabled
        optimized_ast = ast if self.preserve_ast else None

        # Compile
        from kida.compiler import Compiler

        compiler = Compiler(self)
        code = compiler.compile(ast, name, filename)
        precomputed = compiler.precomputed or None
        # Deduplicate warnings (body is compiled multiple times for sync/stream/async)
        seen: set[tuple] = set()
        compile_warnings = []
        for w in compiler.warnings:
            key = (w.code, w.message, w.lineno)
            if key not in seen:
                seen.add(key)
                compile_warnings.append(w)

        # Cache bytecode (and AST when available) for future cold-starts.
        # Serialising the AST avoids re-lexing/re-parsing on cache hits when
        # preserve_ast=True.  optimized_ast is None when preserve_ast is False,
        # in which case the cache entry simply contains no AST section.
        if self._bytecode_cache is not None and name is not None and source_hash is not None:
            self._bytecode_cache.set(
                name,
                source_hash,
                code,
                context_hash=context_hash,
                ast=optimized_ast,
                precomputed=precomputed,
            )

        tmpl = Template(
            self,
            code,
            name,
            filename,
            optimized_ast=optimized_ast,
            source=source,
            precomputed=precomputed,
        )
        tmpl._compile_warnings = validation_warnings + compile_warnings

        # Emit Python warnings for integration with pytest and logging
        all_warnings = validation_warnings + compile_warnings
        if all_warnings:
            import warnings as _warnings_mod

            from kida.exceptions import (
                ComponentWarning,
                ErrorCode,
                MigrationWarning,
                PrecedenceWarning,
            )

            _warning_categories = {
                ErrorCode.COMPONENT_CALL_SIGNATURE: ComponentWarning,
                ErrorCode.JINJA2_SET_SCOPING: MigrationWarning,
            }
            for w in all_warnings:
                category = _warning_categories.get(w.code, PrecedenceWarning)
                _warnings_mod.warn(w.format_message(), category, stacklevel=2)

        return tmpl

    def _is_template_stale(self, name: str) -> bool:
        """Check if a cached template is stale (source changed).

        Uses a two-tier check: mtime first (cheap stat call), then hash
        comparison only if mtime changed. This avoids reading and hashing
        the entire source on every get_template() call when auto_reload=True.

        Args:
            name: Template identifier

        Returns:
            True if template source changed, False if unchanged
        """
        if name not in self._template_hashes:
            return True

        try:
            if self.loader is None:
                return True

            # Fast path: if file mtime hasn't changed, source hasn't changed
            cached_mtime = self._template_mtimes.get(name)
            if cached_mtime is not None:
                # Resolve filename from cached template
                cached_template = self._cache.get(name)
                if cached_template is not None and cached_template._filename is not None:
                    try:
                        current_mtime = Path(cached_template._filename).stat().st_mtime_ns
                        if current_mtime == cached_mtime:
                            return False  # mtime unchanged → not stale
                    except OSError:
                        pass  # Fall through to hash check

            # Slow path: read source and compare hash
            source, _ = self.loader.get_source(name)
            from kida.bytecode_cache import hash_source

            current_hash = hash_source(source)
            cached_hash = self._template_hashes[name]
            return current_hash != cached_hash
        except TemplateNotFoundError, OSError, UnicodeDecodeError:
            return True

    def clear_template_cache(self, names: list[str] | None = None) -> None:
        """Clear template cache (optional, for external invalidation).

        Useful when an external system (e.g., Bengal) detects template changes
        and wants to force cache invalidation without waiting for hash check.

        Args:
            names: Specific template names to clear, or None to clear all

        Example:
            >>> env.clear_template_cache()  # Clear all
            >>> env.clear_template_cache(["base.html", "page.html"])  # Clear specific
        """
        with self._cache_lock:
            if names is None:
                # Clear all templates
                self._cache.clear()
                self._template_hashes.clear()
                self._template_mtimes.clear()
                self._analysis_cache.clear()
                self._structure_manifest_cache.clear()
            else:
                # Clear specific templates
                for name in names:
                    self._cache.delete(name)
                    self._template_hashes.pop(name, None)
                    self._template_mtimes.pop(name, None)
                    self._analysis_cache.pop(name, None)  # Invalidate analysis cache
                    self._structure_manifest_cache.pop(name, None)

    def get_template_structure(self, name: str) -> TemplateStructureManifest | None:
        """Return lightweight manifest with extends/blocks/dependencies."""
        from kida.analysis.metadata import TemplateStructureManifest

        try:
            name = normalize_template_name(name)
        except TemplateNotFoundError:
            return None

        with self._cache_lock:
            cached = self._structure_manifest_cache.get(name)
            if cached is not None:
                return cached

            try:
                template = self.get_template(name)
                meta = template.template_metadata()
                if meta is None:
                    return None
            except TemplateNotFoundError, TemplateSyntaxError:
                return None

            manifest = TemplateStructureManifest(
                name=meta.name,
                extends=meta.extends,
                block_names=tuple(meta.blocks.keys()),
                block_hashes={
                    block_name: block_meta.block_hash
                    for block_name, block_meta in meta.blocks.items()
                },
                dependencies=meta.all_dependencies(),
            )
            self._structure_manifest_cache[name] = manifest
            return manifest

    def render(self, template_name: str, *args: Any, **kwargs: Any) -> str:
        """Render a template by name with context.

        Convenience method combining get_template() and render().

        Args:
            template_name: Template identifier (e.g., "index.html")
            *args: Single dict of context variables (optional)
            **kwargs: Context variables as keyword arguments

        Returns:
            Rendered template as string

        Example:
            >>> env.render("email.html", user=user, items=items)
            '...'
        """
        return self.get_template(template_name).render(*args, **kwargs)

    def render_string(self, source: str, *args: Any, **kwargs: Any) -> str:
        """Compile and render a template string.

        Convenience method combining from_string() and render().

        Args:
            source: Template source code
            *args: Single dict of context variables (optional)
            **kwargs: Context variables as keyword arguments

        Returns:
            Rendered template as string

        Example:
            >>> env.render_string("Hello, {{ name }}!", name="World")
            'Hello, World!'
        """
        return self.from_string(source).render(*args, **kwargs)

    def filter(self, name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a filter function.

        Args:
            name: Filter name (defaults to function name)

        Returns:
            Decorator function

        Example:
            >>> @env.filter()
            ... def double(value):
            ...     return value * 2

            >>> @env.filter("twice")
            ... def my_double(value):
            ...     return value * 2
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            filter_name = name if name is not None else getattr(func, "__name__", "<anonymous>")
            self.add_filter(filter_name, func)
            return func

        return decorator

    def test(self, name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a test function.

        Args:
            name: Test name (defaults to function name)

        Returns:
            Decorator function

        Example:
            >>> @env.test()
            ... def is_prime(value):
            ...     return value > 1 and all(value % i for i in range(2, value))
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            test_name = name if name is not None else getattr(func, "__name__", "<anonymous>")
            self.add_test(test_name, func)
            return func

        return decorator

    def select_autoescape(self, name: str | None) -> bool:
        """Determine if autoescape should be enabled for a template.

        For ``.kida`` files the inner extension drives the decision: e.g.
        ``page.html.kida`` → ``.html`` → escape, ``README.md.kida`` → ``.md``
        → no escape.  A bare ``.kida`` file (no inner extension) is treated as
        plain text (no escaping).

        Args:
            name: Template name (may be None for string templates)

        Returns:
            True if autoescape should be enabled
        """
        if isinstance(self.autoescape, str):
            mode = self.autoescape.strip().lower()
            if mode == "false":
                return False
            if mode in {"true", "terminal", "markdown"}:
                return True
            msg = f"Unknown autoescape mode: {self.autoescape!r}"
            raise ValueError(msg)
        if callable(self.autoescape):
            return self.autoescape(name)
        # For bool autoescape=True, honour .kida double-extension convention
        if self.autoescape and name is not None and name.endswith(".kida"):
            inner = name.removesuffix(".kida")
            if "." in inner.split("/")[-1]:
                # Has an inner extension — check if it's an HTML-like extension
                ext = inner.rsplit(".", 1)[-1].lower()
                return ext in {"html", "htm", "xhtml", "xml", "svg"}
            # Bare .kida — treat as plain text (no escaping)
            return False
        return self.autoescape

    def clear_cache(self, include_bytecode: bool = False) -> None:
        """Clear all cached templates and fragments.

        Call this to release memory when templates are no longer needed,
        or when template files have been modified and need reloading.

        Args:
            include_bytecode: Also clear persistent bytecode cache (default: False)

        Example:
            >>> env.clear_cache()  # Clear memory caches only
            >>> env.clear_cache(include_bytecode=True)  # Clear everything
        """
        self._cache.clear()
        self._fragment_cache.clear()
        if include_bytecode and self._bytecode_cache is not None:
            self._bytecode_cache.clear()

    def clear_fragment_cache(self) -> None:
        """Clear only the fragment cache (keep template cache)."""
        self._fragment_cache.clear()

    def clear_bytecode_cache(self) -> int:
        """Clear persistent bytecode cache.

        Returns:
            Number of cache files removed.
        """
        if self._bytecode_cache is not None:
            return self._bytecode_cache.clear()
        return 0

    def cache_info(self) -> dict[str, Any]:
        """Return cache statistics.

        Returns cache statistics for template and fragment caches.

        Returns:
            Dict with cache statistics including hit/miss rates.

        Example:
            >>> info = env.cache_info()
            >>> print(f"Templates: {info['template']['size']}/{info['template']['max_size']}")
            >>> print(f"Template hit rate: {info['template']['hit_rate']:.1%}")
            >>> if info['bytecode']:
            ...     print(f"Bytecode files: {info['bytecode']['file_count']}")
        """
        info: dict[str, Any] = {
            "template": self._cache.stats(),
            "fragment": self._fragment_cache.stats(),
        }
        if self._bytecode_cache is not None:
            info["bytecode"] = self._bytecode_cache.stats()
        else:
            info["bytecode"] = None
        return info


def _hash_static_context(static_context: dict[str, Any] | None) -> str | None:
    """Hash static context deterministically for bytecode cache keys."""
    if static_context is None:
        return None
    try:
        canonical = json.dumps(
            static_context,
            sort_keys=True,
            separators=(",", ":"),
            default=repr,
        )
    except TypeError, ValueError:
        canonical = repr(static_context)
    return sha256(canonical.encode("utf-8")).hexdigest()[:16]
