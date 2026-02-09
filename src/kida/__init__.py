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
Undefined variables raise `UndefinedError` instead of silently returning
empty string. Use `| default(fallback)` for optional variables:

    >>> env.from_string("{{ missing }}").render()  # Raises UndefinedError
    >>> env.from_string("{{ missing | default('N/A') }}").render()
    'N/A'

"""

from collections.abc import Callable

from kida._types import Token, TokenType
from kida.environment import (
    ChoiceLoader,
    DictLoader,
    Environment,
    ErrorCode,
    FileSystemLoader,
    FunctionLoader,
    PackageLoader,
    PrefixLoader,
    SourceSnippet,
    TemplateError,
    TemplateNotFoundError,
    TemplateRuntimeError,
    TemplateSyntaxError,
    UndefinedError,
    build_source_snippet,
)
from kida.render_accumulator import (
    RenderAccumulator,
    get_accumulator,
    profiled_render,
    timed_block,
)
from kida.render_context import (
    RenderContext,
    async_render_context,
    get_render_context,
    get_render_context_required,
    render_context,
)
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
try:
    from kida.tstring import k
except ImportError:
    # Pre-3.14 Python - t-strings not available
    k = None  # type: ignore[assignment]

__version__ = "0.2.0"

__all__ = [
    "AnalysisConfig",
    "AsyncLoopContext",
    "BlockMetadata",
    "ChoiceLoader",
    "DictLoader",
    "Environment",
    "ErrorCode",
    "FileSystemLoader",
    "FunctionLoader",
    "LoopContext",
    "Markup",
    "PackageLoader",
    "PrefixLoader",
    "RenderAccumulator",
    "RenderContext",
    "RenderedTemplate",
    "SourceSnippet",
    "Template",
    "TemplateError",
    "TemplateMetadata",
    "TemplateNotFoundError",
    "TemplateRuntimeError",
    "TemplateSyntaxError",
    "Token",
    "TokenType",
    "UndefinedError",
    "WorkerEnvironment",
    "WorkloadProfile",
    "WorkloadType",
    "__version__",
    "build_source_snippet",
    "async_render_context",
    "get_accumulator",
    "get_optimal_workers",
    "get_profile",
    "get_render_context",
    "get_render_context_required",
    "html_escape",
    "is_free_threading_enabled",
    "k",
    "profiled_render",
    "render_context",
    "should_parallelize",
    "timed_block",
]


# Lazy-loaded analysis symbols (avoids eagerly importing kida.nodes — 974 lines
# of frozen dataclass AST definitions — on every `from kida import Environment`).
_LAZY_ANALYSIS = frozenset({"AnalysisConfig", "BlockMetadata", "TemplateMetadata"})


# Free-threading declaration (PEP 703) + lazy analysis imports
def __getattr__(name: str) -> object:
    """Module-level getattr for free-threading declaration and lazy imports."""
    if name == "_Py_mod_gil":
        # Signal: this module is safe for free-threading
        # 0 = Py_MOD_GIL_NOT_USED
        return 0
    if name in _LAZY_ANALYSIS:
        from kida.analysis import AnalysisConfig, BlockMetadata, TemplateMetadata

        # Populate globals so subsequent access is direct (no __getattr__)
        globals().update(
            AnalysisConfig=AnalysisConfig,
            BlockMetadata=BlockMetadata,
            TemplateMetadata=TemplateMetadata,
        )
        return globals()[name]
    raise AttributeError(f"module 'kida' has no attribute {name!r}")
