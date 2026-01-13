# RFC: ContextVar Patterns for Kida

**Status**: Draft  
**Created**: 2026-01-13  
**Updated**: 2026-01-13  
**Related**: Bengal `rfc-contextvar-downstream-patterns.md` (✅ Implemented), Patitas `rfc-contextvar-config.md`  
**Priority**: P2 (code cleanliness, not performance-critical)

---

## Executive Summary

Apply ContextVar patterns to Kida for cleaner code architecture and better observability. Unlike Patitas (where ContextVar provides ~50% performance improvement), Kida's benefit is primarily **code cleanliness** since templates are cached and reused.

| Pattern | Value | Effort | Priority |
|---------|-------|--------|----------|
| **RenderContext** | Clean ctx dict, better errors | Medium | P1 |
| **Render Accumulator** | Block profiling, debugging | Low | P2 |

**Note**: CompilationContext (previously P3) is deferred to Future Opportunities—current compiler architecture is already scoped correctly per-compilation.

---

## Motivation

### Current State: Context Dict Pollution

Kida passes render-time state through the `ctx` dictionary in multiple locations:

**`template.py:800-808` — render() method:**
```python
# Inject template metadata for error context
ctx["_template"] = self._name
ctx["_line"] = 0

# Automatic cached block optimization
cached_blocks = ctx.get("_cached_blocks", {})
cached_stats = ctx.get("_cached_stats")
```

**`template.py:897-900` — render_block() method:**
```python
ctx.update(kwargs)
ctx["_template"] = self._name
ctx["_line"] = 0
```

**`template.py:418-434` — _include() helper:**
```python
depth = context.get("_include_depth", 0)
max_include_depth = 50
if depth >= max_include_depth:
    raise TemplateRuntimeError(...)
# ...
new_context = {**context, "_include_depth": depth + 1}
```

**`template.py:461-462` — _extends() helper:**
```python
cached_blocks = context.get("_cached_blocks", {})
cached_stats = context.get("_cached_stats")
```

### Complete List of Internal Keys

| Key | Location | Purpose |
|-----|----------|---------|
| `_template` | `template.py:801, 899` | Current template name for errors |
| `_line` | `template.py:802, 900` | Current line number for errors |
| `_include_depth` | `template.py:418, 434` | DoS protection for circular includes |
| `_cached_blocks` | `template.py:807, 461` | Site-scoped block cache |
| `_cached_stats` | `template.py:808, 462` | Block cache hit/miss stats |

**Problems:**
1. **Mixes user context with internal state** — 5 internal keys injected
2. **Key collision risk** — User cannot use `_template` as a variable name
3. **Scattered state** — Internal keys managed in 4+ locations
4. **Error-prone** — Easy to forget updating all locations

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
    
    Replaces the _template, _line, _include_depth, _cached_blocks, and
    _cached_stats keys that were previously injected into the user's ctx dict.
    
    Thread Safety:
        ContextVars are thread-local by design. Each thread/async task
        has its own RenderContext instance.
    
    Async Safety:
        ContextVars propagate correctly to asyncio.to_thread() in Python 3.14,
        so render_async() works without special handling.
    """
    # Template identification (for error messages)
    template_name: str | None = None
    filename: str | None = None
    
    # Current source position (updated during render by generated code)
    line: int = 0
    
    # Include/embed tracking (DoS protection)
    include_depth: int = 0
    max_include_depth: int = 50
    
    # Block caching (RFC: kida-template-introspection)
    cached_blocks: dict[str, str] = field(default_factory=dict)
    cached_block_names: frozenset[str] = field(default_factory=frozenset)
    cache_stats: dict[str, int] | None = None
    
    def check_include_depth(self, template_name: str) -> None:
        """Check if include depth limit exceeded.
        
        Raises:
            TemplateRuntimeError: If depth >= max_include_depth
        """
        if self.include_depth >= self.max_include_depth:
            from kida.environment.exceptions import TemplateRuntimeError
            raise TemplateRuntimeError(
                f"Maximum include depth exceeded ({self.max_include_depth}) "
                f"when including '{template_name}'",
                template_name=self.template_name,
                suggestion="Check for circular includes: A → B → A",
            )
    
    def child_context(self, template_name: str | None = None) -> RenderContext:
        """Create child context for include/embed with incremented depth.
        
        Shares cached_blocks and cache_stats with parent (they're document-wide).
        """
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
    """Get current render context, raise if not in render.
    
    Used by generated code for line tracking.
    """
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

### Integration: Template.render()

```python
# kida/template.py - Updated render() method
def render(self, *args: Any, **kwargs: Any) -> str:
    """Render template with given context.
    
    User context is now CLEAN - no internal keys injected.
    """
    from kida.render_context import render_context
    
    # Build user context (clean - no internal keys!)
    ctx: dict[str, Any] = {}
    ctx.update(self._env.globals)
    if args:
        if len(args) == 1 and isinstance(args[0], dict):
            ctx.update(args[0])
        else:
            raise TypeError(...)
    ctx.update(kwargs)
    
    # Extract internal state from kwargs (backward compat for Bengal)
    # These are removed from user ctx and moved to RenderContext
    cached_blocks = kwargs.pop("_cached_blocks", {})
    cache_stats = kwargs.pop("_cached_stats", None)
    
    with render_context(
        template_name=self._name,
        filename=self._filename,
        cached_blocks=cached_blocks,
        cache_stats=cache_stats,
    ) as render_ctx:
        # Prepare blocks dictionary
        blocks_arg = None
        if render_ctx.cached_blocks:
            cached_block_names = render_ctx.cached_block_names
            if cached_block_names:
                blocks_arg = CachedBlocksDict(
                    None, render_ctx.cached_blocks, cached_block_names, 
                    stats=render_ctx.cache_stats
                )
        
        try:
            return self._render_func(ctx, blocks_arg)
        except TemplateRuntimeError:
            raise
        except Exception as e:
            from kida.environment.exceptions import TemplateNotFoundError, UndefinedError
            if isinstance(e, (UndefinedError, TemplateNotFoundError)):
                raise
            # Error context available via render_ctx
            raise self._enhance_error(e, render_ctx) from e
```

### Integration: Template.render_block()

```python
# kida/template.py - Updated render_block() method
def render_block(self, block_name: str, *args: Any, **kwargs: Any) -> str:
    """Render a single block from the template."""
    from kida.render_context import render_context
    
    func_name = f"_block_{block_name}"
    block_func = self._namespace.get(func_name)
    if block_func is None:
        available = [k[7:] for k in self._namespace if k.startswith("_block_")]
        raise KeyError(f"Block '{block_name}' not found. Available: {available}")
    
    # Build clean user context
    ctx: dict[str, Any] = {}
    ctx.update(self._env.globals)
    if args:
        if len(args) == 1 and isinstance(args[0], dict):
            ctx.update(args[0])
        else:
            raise TypeError(...)
    ctx.update(kwargs)
    
    # NO internal keys injected - use RenderContext
    with render_context(
        template_name=self._name,
        filename=self._filename,
    ) as render_ctx:
        try:
            return block_func(ctx, {})
        except TemplateRuntimeError:
            raise
        except Exception as e:
            from kida.environment.exceptions import TemplateNotFoundError, UndefinedError
            if isinstance(e, (UndefinedError, TemplateNotFoundError)):
                raise
            raise self._enhance_error(e, render_ctx) from e
```

### Integration: _include() Helper

```python
# kida/template.py - Updated _include() helper (inside Template.__init__)
def _include(
    template_name: str,
    context: dict[str, Any],
    ignore_missing: bool = False,
    *,
    blocks: dict[str, Any] | None = None,
) -> str:
    from kida.render_context import get_render_context_required
    
    render_ctx = get_render_context_required()
    
    # Check include depth (DoS protection)
    render_ctx.check_include_depth(template_name)
    
    _env = env_ref()
    if _env is None:
        raise RuntimeError("Environment has been garbage collected")
    
    try:
        included = _env.get_template(template_name)
        
        # Create child context with incremented depth
        child_ctx = render_ctx.child_context(template_name)
        
        # Set child context for the included template's render
        from kida.render_context import _render_context
        token = _render_context.set(child_ctx)
        try:
            if blocks is not None and included._render_func is not None:
                return included._render_func(context, blocks)
            return str(included.render(**context))
        finally:
            _render_context.reset(token)
    except Exception:
        if ignore_missing:
            return ""
        raise
```

### Integration: _extends() Helper

```python
# kida/template.py - Updated _extends() helper
def _extends(template_name: str, context: dict[str, Any], blocks: dict[str, Any]) -> str:
    from kida.render_context import get_render_context_required
    
    render_ctx = get_render_context_required()
    
    _env = env_ref()
    if _env is None:
        raise RuntimeError("Environment has been garbage collected")
    
    parent = _env.get_template(template_name)
    if parent._render_func is None:
        raise RuntimeError(f"Template '{template_name}' not properly compiled")
    
    # Apply cached blocks wrapper from RenderContext
    blocks_to_use: dict[str, Any] | CachedBlocksDict = blocks
    if render_ctx.cached_blocks and not isinstance(blocks, CachedBlocksDict):
        if render_ctx.cached_block_names:
            blocks_to_use = CachedBlocksDict(
                blocks, render_ctx.cached_blocks, 
                render_ctx.cached_block_names, 
                stats=render_ctx.cache_stats
            )
    
    return parent._render_func(context, blocks_to_use)
```

### Integration: _enhance_error()

```python
# kida/template.py - Updated error enhancement
def _enhance_error(self, error: Exception, render_ctx: RenderContext) -> Exception:
    """Enhance a generic exception with template context from RenderContext."""
    from kida.environment.exceptions import NoneComparisonError, TemplateRuntimeError
    
    # Read from RenderContext instead of ctx dict
    template_name = render_ctx.template_name
    lineno = render_ctx.line
    error_str = str(error)
    
    if isinstance(error, TypeError) and "NoneType" in error_str:
        return NoneComparisonError(
            None, None,
            template_name=template_name,
            lineno=lineno,
            expression="<see stack trace>",
        )
    
    return TemplateRuntimeError(
        error_str,
        template_name=template_name,
        lineno=lineno,
    )
```

### Integration: Compiler Line Marker Generation

**Current** (`compiler/core.py:470-481`):
```python
def _make_line_marker(self, lineno: int) -> ast.stmt:
    """Generate ctx['_line'] = lineno statement for error tracking."""
    return ast.Assign(
        targets=[
            ast.Subscript(
                value=ast.Name(id="ctx", ctx=ast.Load()),
                slice=ast.Constant(value="_line"),
                ctx=ast.Store(),
            )
        ],
        value=ast.Constant(value=lineno),
    )
```

**After**:
```python
def _make_line_marker(self, lineno: int) -> ast.stmt:
    """Generate RenderContext line update for error tracking.
    
    Generates: get_render_context_required().line = lineno
    
    This updates the ContextVar-stored RenderContext instead of
    polluting the user's ctx dict.
    """
    return ast.Assign(
        targets=[
            ast.Attribute(
                value=ast.Call(
                    func=ast.Name(id="_get_render_ctx", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                ),
                attr="line",
                ctx=ast.Store(),
            )
        ],
        value=ast.Constant(value=lineno),
    )
```

**Namespace Addition** (in `Template.__init__`):
```python
from kida.render_context import get_render_context_required

namespace.update({
    # ... existing entries ...
    "_get_render_ctx": get_render_context_required,
})
```

### Benefits

1. **Clean user context**: No `_template`, `_line`, `_include_depth`, `_cached_blocks`, `_cached_stats` pollution
2. **No key collisions**: User can safely use `_template` as a variable name
3. **Centralized state**: All render state in `RenderContext` dataclass
4. **Better errors**: Error enhancement reads from structured context
5. **Thread-safe**: ContextVars provide automatic thread isolation

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
from typing import Any, Iterator


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
    Zero overhead when disabled (get_accumulator() returns None).
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
    
    def summary(self) -> dict[str, Any]:
        """Get summary of render metrics."""
        return {
            "total_ms": round(self.total_duration_ms, 2),
            "blocks": {
                name: {"ms": round(t.duration_ms, 2), "calls": t.call_count}
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

## Implementation Phases

### Phase 1: RenderContext (Priority)

**Steps:**
1. Create `kida/render_context.py` with `RenderContext` dataclass and ContextVar
2. Update `Template.render()` to use context manager
3. Update `Template.render_block()` to use context manager
4. Refactor `_include()` helper to use `get_render_context_required()` and `child_context()`
5. Refactor `_extends()` helper to read cached blocks from RenderContext
6. Update `_enhance_error()` to accept `RenderContext` instead of ctx dict
7. Update `Compiler._make_line_marker()` to generate RenderContext updates
8. Add `_get_render_ctx` to template namespace

**Files Modified:**
- `kida/render_context.py` (new)
- `kida/template.py` (render, render_block, _include, _extends, _enhance_error, namespace)
- `kida/compiler/core.py` (_make_line_marker)

**Estimated Effort**: 6-8 hours

**Backward Compatibility:**
- `_cached_blocks` and `_cached_stats` kwargs still accepted (extracted and moved to RenderContext)
- No public API changes

### Phase 2: Render Accumulator

**Steps:**
1. Create `kida/render_accumulator.py`
2. Add optional instrumentation to `_include()` helper (`record_include`)
3. Add optional instrumentation to block functions (generated code)
4. Add optional instrumentation to macro calls (generated code)
5. Document profiling API
6. Add Bengal integration example

**Files Modified:**
- `kida/render_accumulator.py` (new)
- `kida/template.py` (_include helper)
- `kida/compiler/statements/template_structure.py` (optional block timing)
- `kida/compiler/statements/functions.py` (optional macro tracking)

**Estimated Effort**: 4-6 hours

---

## Test Strategy

### Phase 1 Tests

```python
# tests/test_render_context.py

def test_render_context_isolation():
    """User context is clean after render."""
    env = Environment()
    template = env.from_string("{{ name }}")
    ctx = {"name": "World"}
    template.render(ctx)
    
    # No internal keys in user context
    assert "_template" not in ctx
    assert "_line" not in ctx
    assert "_include_depth" not in ctx


def test_render_context_thread_safety():
    """Concurrent renders have isolated RenderContext."""
    import threading
    from kida.render_context import get_render_context
    
    results = {}
    
    def render_worker(thread_id: int, template_name: str):
        with render_context(template_name=template_name):
            ctx = get_render_context()
            results[thread_id] = ctx.template_name
    
    threads = [
        threading.Thread(target=render_worker, args=(i, f"template_{i}.html"))
        for i in range(4)
    ]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # Each thread saw its own template name
    assert results[0] == "template_0.html"
    assert results[1] == "template_1.html"


def test_include_depth_tracking():
    """Include depth tracked via RenderContext, not ctx dict."""
    env = Environment()
    # Create templates that include each other
    env._cache["a.html"] = env.from_string("{% include 'b.html' %}")
    env._cache["b.html"] = env.from_string("depth: {{ _include_depth | default('N/A') }}")
    
    template = env.get_template("a.html")
    html = template.render()
    
    # _include_depth should NOT be in user context (shows 'N/A')
    assert "N/A" in html


def test_user_can_use_underscore_template():
    """User can now use _template as a variable name."""
    env = Environment()
    template = env.from_string("{{ _template }}")
    html = template.render(_template="my_value")
    assert html == "my_value"


def test_error_messages_include_line():
    """Runtime errors still include line numbers from RenderContext."""
    env = Environment()
    template = env.from_string("line1\n{{ undefined.attr }}\nline3")
    
    with pytest.raises(TemplateRuntimeError) as exc_info:
        template.render()
    
    assert "line" in str(exc_info.value).lower() or exc_info.value.lineno == 2
```

### Phase 2 Tests

```python
# tests/test_render_accumulator.py

def test_profiled_render_no_overhead_when_disabled():
    """Normal render has no profiling overhead."""
    from kida.render_accumulator import get_accumulator
    
    env = Environment()
    template = env.from_string("Hello")
    template.render()
    
    assert get_accumulator() is None


def test_profiled_render_captures_metrics():
    """Profiled render captures block timings."""
    from kida.render_accumulator import profiled_render
    
    env = Environment()
    template = env.from_string("{% block content %}Hello{% endblock %}")
    
    with profiled_render() as metrics:
        template.render()
    
    summary = metrics.summary()
    assert "total_ms" in summary
    assert summary["total_ms"] >= 0
```

---

## Risk Assessment

| Pattern | Risk | Mitigation |
|---------|------|------------|
| RenderContext | Medium (generated code changes) | Comprehensive tests, backward-compat kwargs |
| Render Accumulator | Low (opt-in only) | No-op when disabled, zero overhead |

---

## Performance Considerations

Unlike Patitas, Kida won't see significant performance improvements from ContextVar because:

1. **Templates are cached**: Compilation happens once, not per-page
2. **Rendering is already fast**: Local state only (buf list)
3. **No high-frequency instantiation**: Template objects are reused

**Expected Impact:**
- RenderContext: Negligible (one ContextVar lookup per render, one per line marker)
- Render Accumulator: Zero when disabled, ~5% overhead when enabled

**ContextVar vs Dict Lookup:**
- `ContextVar.get()`: ~30ns (C implementation)
- `dict['key']`: ~20ns
- Difference is negligible for render() call overhead

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Internal ctx keys injected | 5 (`_template`, `_line`, `_include_depth`, `_cached_blocks`, `_cached_stats`) | 0 |
| User key collision risk | Possible | Impossible |
| Block profiling available | No | Yes (opt-in) |
| Include depth tracked via | ctx dict | RenderContext |
| Error context source | ctx dict | RenderContext |

---

## Future Opportunities

### CompilationContext (Deferred)

Originally proposed as P3, but the current Compiler architecture is already correctly scoped:
- `_name` and `_filename` are set once per `compile()` call
- They're only used during that compilation
- No benefit to moving to ContextVar

**If needed later**, the pattern would be:
```python
@dataclass(frozen=True, slots=True)
class CompilationContext:
    env: Environment
    name: str | None
    filename: str | None
    autoescape: bool
```

### Other Opportunities

1. **Bengal Integration**: Use Render Accumulator for build performance reports
2. **Dev Server**: Show slow blocks in dev overlay
3. **Template Debugging**: Track variable access patterns via RenderContext extension
4. **Async Rendering**: ContextVar is async-safe for future async templates

---

## References

- Bengal `plan/rfc-contextvar-downstream-patterns.md`
- Patitas `plan/rfc-contextvar-config.md` (implemented, validated 1.4x speedup)
- Python PEP 567 - Context Variables
- Kida `template.py:800-808, 897-900, 418-434, 461-462` (current pollution sites)
- Kida `compiler/core.py:470-481` (line marker generation)
