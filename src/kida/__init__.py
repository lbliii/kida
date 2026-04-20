"""Kida — Next-generation template engine for free-threaded Python (3.14t+).

A pure-Python template engine optimized for free-threaded Python execution.
Features AST-native compilation, StringBuilder rendering, and native async support.

Quickstart:
    >>> from kida import Environment
    >>> env = Environment()
    >>> template = env.from_string("Hello, {{ name }}!")
    >>> template.render(name="World")
    'Hello, World!'

File-based templates:
    >>> from kida import Environment, FileSystemLoader
    >>> env = Environment(loader=FileSystemLoader("templates/"))
    >>> template = env.get_template("index.html")
    >>> template.render(page=page, site=site)

Architecture:
Template Source → Lexer → Parser → Kida AST → Compiler → Python AST → exec()

Pipeline stages:
1. **Lexer**: Tokenizes template source into token stream
2. **Parser**: Builds immutable Kida AST from tokens
3. **Compiler**: Transforms Kida AST to Python AST
4. **Template**: Wraps compiled code with render() interface

Unlike Jinja2 which generates Python source strings, Kida generates
`ast.Module` objects directly, enabling structured code manipulation,
compile-time optimization, and precise error source mapping.

Thread-Safety:
All public APIs are thread-safe by design:
- Template compilation is idempotent (same input → same output)
- Rendering uses only local state (StringBuilder pattern, no shared buffers)
- Environment caching uses copy-on-write for filters/tests/globals
- LRU caches use atomic operations (no locks required)

Free-Threading (PEP 703):
Declares GIL-independence via `_Py_mod_gil = 0` attribute.
Safe for concurrent template rendering in Python 3.14t+ free-threaded builds.

Performance Optimizations:
- StringBuilder pattern: O(n) output vs O(n²) string concatenation
- Local variable caching: `_escape`, `_str` bound once per render
- O(1) operator dispatch: dict-based token → handler lookup
- Single-pass HTML escaping via `str.translate()`
- Compiled regex patterns at class level (immutable)

Key Differences from Jinja2:
- **Rendering**: StringBuilder pattern (25-40% faster than generator yields)
- **Compilation**: AST-to-AST (no string manipulation or regex)
- **Async**: Native async/await (no `auto_await()` wrappers)
- **Scoping**: Explicit `{% let %}`, `{% set %}`, `{% export %}` semantics
- **Syntax**: Unified `{% end %}` for all blocks (like Go templates)
- **Filters**: Protocol-based dispatch with compile-time binding
- **Caching**: Built-in `{% cache key %}...{% end %}` directive
- **Pipeline**: `|>` operator for readable filter chains
- **Pattern Matching**: `{% match %}...{% case %}` for cleaner branching

Strict Mode (default):
Undefined variables and undefined attribute access raise `UndefinedError`
instead of silently returning empty string. Use `| default(fallback)`,
`is defined` guards, or the `??` null-coalescing operator for optional values:

    >>> env.from_string("{{ missing }}").render()  # Raises UndefinedError
    >>> env.from_string("{{ missing | default('N/A') }}").render()
    'N/A'
    >>> env.from_string("{{ user.missing ?? '' }}").render(user={})
    ''

Opt out (per-Environment) when porting templates that rely on lenient
attribute access:

    >>> env = Environment(strict_undefined=False)

"""

from __future__ import annotations

from functools import wraps
from importlib.metadata import version
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from kida._types import Token, TokenType
from kida.coverage import CoverageCollector, CoverageResult
from kida.environment import (
    ChoiceLoader,
    CoercionWarning,
    DictLoader,
    Environment,
    ErrorCode,
    FileSystemLoader,
    FunctionLoader,
    KidaWarning,
    MigrationWarning,
    PackageLoader,
    PrecedenceWarning,
    PrefixLoader,
    SourceSnippet,
    TemplateError,
    TemplateNotFoundError,
    TemplateRuntimeError,
    TemplateSyntaxError,
    TemplateWarning,
    UndefinedError,
    build_source_snippet,
)
from kida.extensions import Extension
from kida.render_accumulator import (
    RenderAccumulator,
    get_accumulator,
    profiled_render,
    timed_block,
)
from kida.render_capture import (
    Fragment,
    RenderCapture,
    captured_render,
    get_capture,
)
from kida.render_context import (
    RenderContext,
    async_render_context,
    get_render_context,
    get_render_context_required,
    render_context,
)
from kida.render_manifest import (
    FreezeCache,
    FreezeCacheStats,
    ManifestDiff,
    RenderManifest,
    SearchEntry,
    SearchManifestBuilder,
    default_field_extractor,
)
from kida.sandbox import SandboxedEnvironment, SandboxPolicy, SecurityError
from kida.template import AsyncLoopContext, LoopContext, Markup, RenderedTemplate, Template
from kida.utils.html import html_escape
from kida.utils.workers import (
    Environment as WorkerEnvironment,
)
from kida.utils.workers import (
    WorkloadProfile,
    WorkloadType,
    get_optimal_workers,
    get_profile,
    is_free_threading_enabled,
    should_parallelize,
)

# Python 3.14+ t-string support (PEP 750)
# Only import if string.templatelib is available
k: Callable[..., str] | None
try:
    from kida.tstring import k, plain
except ImportError:
    # Pre-3.14 Python - t-strings not available
    k = None  # type: ignore[assignment]
    plain = None  # type: ignore[assignment]

__version__ = version("kida-templates")


def pure(func: Callable[..., object]) -> Callable[..., object]:
    """Mark a filter function as pure (deterministic, no side effects).

    Pure filters are eligible for compile-time evaluation by the partial
    evaluator when all inputs are statically known::

        from kida import Environment, pure

        @pure
        def clean(value: str) -> str:
            return value.strip().lower()

        env = Environment()
        env.add_filter("clean", clean)

    """

    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)

    object.__setattr__(wrapper, "_kida_pure", True)
    return wrapper


__all__ = [
    "AnalysisConfig",
    "AsyncLoopContext",
    "BlockMetadata",
    "ChoiceLoader",
    "CoercionWarning",
    "CoverageCollector",
    "CoverageResult",
    "DefMetadata",
    "DefParamInfo",
    "DictLoader",
    "Environment",
    "ErrorCode",
    "Extension",
    "FileSystemLoader",
    "Fragment",
    "FreezeCache",
    "FreezeCacheStats",
    "FunctionLoader",
    "KidaWarning",
    "LoopContext",
    "ManifestDiff",
    "Markup",
    "MigrationWarning",
    "PackageLoader",
    "PrecedenceWarning",
    "PrefixLoader",
    "RenderAccumulator",
    "RenderCapture",
    "RenderContext",
    "RenderManifest",
    "RenderedTemplate",
    "SandboxPolicy",
    "SandboxedEnvironment",
    "SearchEntry",
    "SearchManifestBuilder",
    "SecurityError",
    "SourceSnippet",
    "Template",
    "TemplateError",
    "TemplateMetadata",
    "TemplateNotFoundError",
    "TemplateRuntimeError",
    "TemplateStructureManifest",
    "TemplateSyntaxError",
    "TemplateWarning",
    "Token",
    "TokenType",
    "UndefinedError",
    "WorkerEnvironment",
    "WorkloadProfile",
    "WorkloadType",
    "__version__",
    "async_render_context",
    "build_source_snippet",
    "captured_render",
    "default_field_extractor",
    "get_accumulator",
    "get_capture",
    "get_optimal_workers",
    "get_profile",
    "get_render_context",
    "get_render_context_required",
    "html_escape",
    "is_free_threading_enabled",
    "k",
    "plain",
    "profiled_render",
    "pure",
    "render_context",
    "should_parallelize",
    "strip_colors",
    "timed_block",
]


# Lazy-loaded analysis symbols (avoids eagerly importing kida.nodes — 974 lines
# of frozen dataclass AST definitions — on every `from kida import Environment`).
_LAZY_ANALYSIS = frozenset(
    {
        "AnalysisConfig",
        "BlockMetadata",
        "DefMetadata",
        "DefParamInfo",
        "TemplateMetadata",
        "TemplateStructureManifest",
    }
)
_LAZY_EXPORTS = frozenset({"strip_colors"})


# Free-threading declaration (PEP 703) + lazy analysis imports
def __getattr__(name: str) -> object:
    """Module-level getattr for free-threading declaration and lazy imports."""
    if name == "_Py_mod_gil":
        # Signal: this module is safe for free-threading
        # 0 = Py_MOD_GIL_NOT_USED
        return 0
    if name in _LAZY_ANALYSIS:
        from kida.analysis import (
            AnalysisConfig,
            BlockMetadata,
            DefMetadata,
            DefParamInfo,
            TemplateMetadata,
            TemplateStructureManifest,
        )

        # Populate globals so subsequent access is direct (no __getattr__)
        globals().update(
            AnalysisConfig=AnalysisConfig,
            BlockMetadata=BlockMetadata,
            DefMetadata=DefMetadata,
            DefParamInfo=DefParamInfo,
            TemplateMetadata=TemplateMetadata,
            TemplateStructureManifest=TemplateStructureManifest,
        )
        return globals()[name]
    if name in _LAZY_EXPORTS:
        from kida.environment.terminal import strip_colors

        globals()["strip_colors"] = strip_colors
        return strip_colors
    raise AttributeError(f"module 'kida' has no attribute {name!r}")
