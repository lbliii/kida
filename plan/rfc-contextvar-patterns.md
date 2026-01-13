# RFC: ContextVar Patterns for Kida

**Status**: Draft  
**Created**: 2026-01-13  
**Related**: Bengal `rfc-contextvar-downstream-patterns.md`, Patitas `rfc-contextvar-config.md`  
**Priority**: P2 (code cleanliness, not performance-critical)

---

## Executive Summary

Apply ContextVar patterns to Kida for cleaner code architecture and better observability. Unlike Patitas (where ContextVar provides ~50% performance improvement), Kida's benefit is primarily **code cleanliness** since templates are cached and reused.

| Pattern | Value | Effort | Priority |
|---------|-------|--------|----------|
| **RenderContext** | Clean ctx dict, better errors | Medium | P1 |
| **Render Accumulator** | Block profiling, debugging | Low | P2 |
| **CompilationContext** | Cleaner compiler code | Medium | P3 |

---

## Motivation

### Current State: Context Dict Pollution

Kida passes render-time state through the `ctx` dictionary:

```python
# template.py - render() method
ctx["_template"] = self._name
ctx["_line"] = 0
ctx["_include_depth"] = depth + 1
ctx["_cached_blocks"] = cached_blocks
ctx["_cached_stats"] = cached_stats
```

**Problems:**
1. Mixes user context with internal state
2. Internal keys can collide with user variables
3. Hard to track what internal state exists
4. Scattered throughout codebase

### Current State: Compiler Parameter Drilling

Compiler passes state through parameters and instance attributes:

```python
class Compiler:
    def __init__(self, env: Environment):
        self._env = env
        self._name = None
        self._filename = None
        # ...
    
    def compile(self, ast, name, filename):
        self._name = name
        self._filename = filename
        # Used throughout compilation
```

---

## Pattern 1: RenderContext

### Problem

Internal render state pollutes the user's context dictionary:

```python
# User context
ctx = {"page": page, "site": site}

# After render() mangles it
ctx = {
    "page": page,
    "site": site,
    "_template": "base.html",     # Internal
    "_line": 45,                   # Internal
    "_include_depth": 2,           # Internal
    "_cached_blocks": {...},       # Internal
    "_cached_stats": {...},        # Internal
}
```

### Solution

```python
# kida/render_context.py
from __future__ import annotations

from contextvars import ContextVar, Token
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from kida.template import CachedBlocksDict


@dataclass
class RenderContext:
    """Per-render state isolated from user context.
    
    Replaces the _template, _line, _include_depth, etc. keys
    that were previously injected into the user's ctx dict.
    """
    # Template identification (for error messages)
    template_name: str | None = None
    filename: str | None = None
    
    # Current source position (updated during render)
    line: int = 0
    
    # Include/embed tracking (DoS protection)
    include_depth: int = 0
    max_include_depth: int = 50
    
    # Block caching (RFC: kida-template-introspection)
    cached_blocks: dict[str, str] = field(default_factory=dict)
    cached_block_names: frozenset[str] = field(default_factory=frozenset)
    cache_stats: dict[str, int] | None = None
    
    def check_include_depth(self, template_name: str) -> None:
        """Check if include depth limit exceeded."""
        if self.include_depth >= self.max_include_depth:
            from kida.environment.exceptions import TemplateRuntimeError
            raise TemplateRuntimeError(
                f"Maximum include depth exceeded ({self.max_include_depth}) "
                f"when including '{template_name}'",
                template_name=self.template_name,
                suggestion="Check for circular includes: A → B → A",
            )
    
    def child_context(self, template_name: str | None = None) -> RenderContext:
        """Create child context for include/embed with incremented depth."""
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
    'render_context',
    default=None
)


def get_render_context() -> RenderContext | None:
    """Get current render context (None if not in render)."""
    return _render_context.get()


def get_render_context_required() -> RenderContext:
    """Get current render context, raise if not in render."""
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
    
    Usage:
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
    token = _render_context.set(ctx)
    try:
        yield ctx
    finally:
        _render_context.reset(token)
```

### Integration

```python
# kida/template.py - Updated render() method
def render(self, *args: Any, **kwargs: Any) -> str:
    from kida.render_context import render_context, get_render_context
    
    # Build user context (clean - no internal keys!)
    ctx: dict[str, Any] = {}
    ctx.update(self._env.globals)
    if args and isinstance(args[0], dict):
        ctx.update(args[0])
    ctx.update(kwargs)
    
    # Use ContextVar for internal state
    cached_blocks = kwargs.pop("_cached_blocks", {})
    cache_stats = kwargs.pop("_cached_stats", None)
    
    with render_context(
        template_name=self._name,
        filename=self._filename,
        cached_blocks=cached_blocks,
        cache_stats=cache_stats,
    ) as render_ctx:
        try:
            return self._render_func(ctx, None)
        except Exception as e:
            # Error context available via get_render_context()
            raise self._enhance_error(e, render_ctx) from e
```

```python
# Generated code reads from ContextVar instead of ctx dict
# Before:
ctx['_line'] = 45

# After:
from kida.render_context import get_render_context_required
get_render_context_required().line = 45
```

### Benefits

1. **Clean user context**: No `_template`, `_line`, etc. pollution
2. **No key collisions**: User can use `_template` as a variable name
3. **Centralized state**: All render state in one place
4. **Better errors**: Error enhancement reads from ContextVar

---

## Pattern 2: Render Accumulator

### Problem

No visibility into template rendering performance:
- Which blocks are slow?
- How many times is each macro called?
- What's the actual render time breakdown?

### Solution

```python
# kida/render_accumulator.py
from __future__ import annotations

from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Iterator


@dataclass
class BlockTiming:
    """Timing data for a single block render."""
    name: str
    duration_ms: float
    call_count: int = 1


@dataclass
class RenderAccumulator:
    """Accumulated metrics during template rendering.
    
    Opt-in profiling for debugging slow templates.
    """
    # Block render times
    block_timings: dict[str, BlockTiming] = field(default_factory=dict)
    
    # Macro call counts
    macro_calls: dict[str, int] = field(default_factory=dict)
    
    # Include/embed counts
    include_counts: dict[str, int] = field(default_factory=dict)
    
    # Filter usage
    filter_calls: dict[str, int] = field(default_factory=dict)
    
    # Total render time
    start_time: float = field(default_factory=perf_counter)
    
    def record_block(self, name: str, duration_ms: float) -> None:
        """Record a block render."""
        if name in self.block_timings:
            existing = self.block_timings[name]
            self.block_timings[name] = BlockTiming(
                name=name,
                duration_ms=existing.duration_ms + duration_ms,
                call_count=existing.call_count + 1,
            )
        else:
            self.block_timings[name] = BlockTiming(name=name, duration_ms=duration_ms)
    
    def record_macro(self, name: str) -> None:
        """Record a macro invocation."""
        self.macro_calls[name] = self.macro_calls.get(name, 0) + 1
    
    def record_include(self, template_name: str) -> None:
        """Record an include/embed."""
        self.include_counts[template_name] = self.include_counts.get(template_name, 0) + 1
    
    def record_filter(self, name: str) -> None:
        """Record a filter usage."""
        self.filter_calls[name] = self.filter_calls.get(name, 0) + 1
    
    @property
    def total_duration_ms(self) -> float:
        """Total render duration in milliseconds."""
        return (perf_counter() - self.start_time) * 1000
    
    def summary(self) -> dict[str, any]:
        """Get summary of render metrics."""
        return {
            "total_ms": self.total_duration_ms,
            "blocks": {
                name: {"ms": t.duration_ms, "calls": t.call_count}
                for name, t in sorted(
                    self.block_timings.items(),
                    key=lambda x: x[1].duration_ms,
                    reverse=True,
                )
            },
            "macros": dict(sorted(self.macro_calls.items(), key=lambda x: x[1], reverse=True)),
            "includes": dict(sorted(self.include_counts.items(), key=lambda x: x[1], reverse=True)),
            "filters": dict(sorted(self.filter_calls.items(), key=lambda x: x[1], reverse=True)),
        }


# Module-level ContextVar
_accumulator: ContextVar[RenderAccumulator | None] = ContextVar(
    'render_accumulator',
    default=None
)


def get_accumulator() -> RenderAccumulator | None:
    """Get current accumulator (None if profiling disabled)."""
    return _accumulator.get()


@contextmanager
def profiled_render() -> Iterator[RenderAccumulator]:
    """Context manager for profiled rendering.
    
    Usage:
        with profiled_render() as metrics:
            html = template.render(ctx)
            print(metrics.summary())
    """
    acc = RenderAccumulator()
    token = _accumulator.set(acc)
    try:
        yield acc
    finally:
        _accumulator.reset(token)


@contextmanager
def timed_block(name: str) -> Iterator[None]:
    """Time a block render (no-op if profiling disabled)."""
    acc = get_accumulator()
    if acc is None:
        yield
        return
    
    start = perf_counter()
    try:
        yield
    finally:
        duration_ms = (perf_counter() - start) * 1000
        acc.record_block(name, duration_ms)
```

### Usage

```python
from kida import Environment
from kida.render_accumulator import profiled_render

env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("page.html")

# Normal render (no overhead)
html = template.render(page=page)

# Profiled render (opt-in)
with profiled_render() as metrics:
    html = template.render(page=page)
    
print(metrics.summary())
# {
#   "total_ms": 12.5,
#   "blocks": {
#     "content": {"ms": 8.2, "calls": 1},
#     "nav": {"ms": 2.1, "calls": 1},
#     "footer": {"ms": 1.5, "calls": 1},
#   },
#   "macros": {"render_card": 15, "format_date": 8},
#   "includes": {"partials/sidebar.html": 1},
#   "filters": {"escape": 45, "truncate": 12},
# }
```

### Bengal Integration

```python
# Bengal could use this for template performance reporting
from kida.render_accumulator import profiled_render

def render_page_profiled(page: Page) -> tuple[str, dict]:
    with profiled_render() as metrics:
        html = template.render(page=page, site=site)
    return html, metrics.summary()

# Build report could show:
# "Slowest templates: base.html (content block: 45ms avg)"
```

---

## Pattern 3: CompilationContext

### Problem

Compiler state is split between parameters and instance attributes:

```python
class Compiler:
    def __init__(self, env: Environment):
        self._env = env
        self._name = None      # Set later in compile()
        self._filename = None  # Set later in compile()
        
    def compile(self, ast, name, filename):
        self._name = name
        self._filename = filename
        # ...
```

### Solution

```python
# kida/compilation_context.py
from __future__ import annotations

from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from kida.environment import Environment


@dataclass(frozen=True, slots=True)
class CompilationContext:
    """Per-compilation state for template compilation.
    
    Immutable context available throughout AST compilation.
    """
    env: Environment
    name: str | None
    filename: str | None
    autoescape: bool
    
    # F-string coalescing settings
    fstring_coalescing: bool = True
    pure_filters: frozenset[str] = frozenset()


_compilation_context: ContextVar[CompilationContext | None] = ContextVar(
    'compilation_context',
    default=None
)


def get_compilation_context() -> CompilationContext:
    """Get current compilation context."""
    ctx = _compilation_context.get()
    if ctx is None:
        raise RuntimeError("Not in a compilation context")
    return ctx


@contextmanager
def compilation_context(
    env: Environment,
    name: str | None = None,
    filename: str | None = None,
    autoescape: bool = True,
) -> Iterator[CompilationContext]:
    """Context manager for compilation-scoped state."""
    ctx = CompilationContext(
        env=env,
        name=name,
        filename=filename,
        autoescape=autoescape,
        fstring_coalescing=env.fstring_coalescing,
        pure_filters=frozenset(env.pure_filters),
    )
    token = _compilation_context.set(ctx)
    try:
        yield ctx
    finally:
        _compilation_context.reset(token)
```

### Benefits

1. **Immutable context**: Can't accidentally mutate during compilation
2. **No parameter drilling**: Mixins access via `get_compilation_context()`
3. **Cleaner Compiler class**: Fewer instance attributes

---

## Implementation Phases

### Phase 1: RenderContext (Priority)

1. Create `kida/render_context.py`
2. Update `Template.render()` to use context manager
3. Update `_include()`, `_extends()` to use ContextVar
4. Update error enhancement to read from ContextVar
5. Update generated code to set `line` via ContextVar

**Files Modified**:
- `kida/render_context.py` (new)
- `kida/template.py`
- `kida/compiler/statements/template_structure.py` (code generation)

**Estimated Effort**: 4-6 hours

### Phase 2: Render Accumulator

1. Create `kida/render_accumulator.py`
2. Add optional instrumentation to block rendering
3. Add optional instrumentation to macro calls
4. Document profiling API

**Files Modified**:
- `kida/render_accumulator.py` (new)
- `kida/template.py` (optional integration)
- `kida/compiler/statements/` (optional instrumentation)

**Estimated Effort**: 3-4 hours

### Phase 3: CompilationContext

1. Create `kida/compilation_context.py`
2. Refactor Compiler to use ContextVar
3. Update all mixins to read from ContextVar

**Files Modified**:
- `kida/compilation_context.py` (new)
- `kida/compiler/core.py`
- `kida/compiler/expressions.py`
- `kida/compiler/statements/*.py`

**Estimated Effort**: 4-6 hours

---

## Risk Assessment

| Pattern | Risk | Mitigation |
|---------|------|------------|
| RenderContext | Medium (generated code changes) | Incremental migration, extensive tests |
| Render Accumulator | Low (opt-in only) | No-op when disabled |
| CompilationContext | Low (internal refactor) | No API changes |

---

## Performance Considerations

Unlike Patitas, Kida won't see significant performance improvements from ContextVar because:

1. **Templates are cached**: Compilation happens once, not per-page
2. **Rendering is already fast**: Local state only (buf list)
3. **No high-frequency instantiation**: Template objects are reused

**Expected Impact**:
- RenderContext: Negligible (one ContextVar lookup per render)
- Render Accumulator: Zero when disabled, ~5% overhead when enabled
- CompilationContext: Negligible (compilation is not hot path)

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Internal ctx keys | 5+ (`_template`, `_line`, etc.) | 0 |
| User key collision risk | Possible | Impossible |
| Block profiling available | No | Yes (opt-in) |
| Compiler instance attributes | 6 | 2 |

---

## Future Opportunities

1. **Bengal Integration**: Use Render Accumulator for build performance reports
2. **Dev Server**: Show slow blocks in dev overlay
3. **Template Debugging**: Track variable access patterns
4. **Async Rendering**: ContextVar is async-safe for future async templates

---

## References

- Bengal `plan/rfc-contextvar-downstream-patterns.md`
- Patitas `plan/rfc-contextvar-config.md`
- Python PEP 567 - Context Variables
- Kida `plan/rfc-performance-optimization.md`
