# RFC: Performance Optimization Opportunities

**Status**: Draft  
**Created**: 2026-01-11  
**Based On**: Benchmark analysis from `benchmarks/`

---

## Executive Summary

Benchmark analysis reveals several optimization opportunities, most critically:
1. **Cold-start bytecode cache ineffectiveness** — only 7% improvement vs documented 90%+
2. **HTML escape fast path is slower** than the naive approach for typical strings
3. **Template.__init__ overhead** from eager closure creation and large namespace

---

## Benchmark Results Summary

### Render Performance (Kida vs Jinja2)

| Template Size | Kida | Jinja2 | Speedup |
|--------------|------|--------|---------|
| Minimal | 1.13μs | 4.09μs | **3.6x faster** |
| Small | 4.8μs | 7.6μs | **1.6x faster** |
| Medium | 264μs | 288μs | **1.1x faster** |
| Large | 3.05ms | 3.00ms | ~equal |
| Complex | 17.9μs | 24.2μs | **1.4x faster** |

### Scaling Characteristics (Kida-only)

- **Variable scaling**: Linear O(n) ✅
- **Loop iteration**: Linear O(n) ✅
- **Filter chains**: Sub-linear (1.6x from depth 1→20) ✅
- **Inheritance**: Sub-linear (~7x from depth 1→10) ✅

### Cold-Start Performance ⚠️

```
Baseline (no cache):     22.84ms
Cache cold (first load): 21.48ms  (+6.0% improvement)
Cache warm (cache hit):  21.20ms  (+7.2% improvement)

❌ NOT VALIDATED: Only 7.2% improvement (claim is 90%+)
```

---

## Issue 1: Cold-Start Bytecode Cache Ineffective

### Root Cause

The bytecode cache only accelerates **template compilation**, not **module import**.

**Current import chain** (all imported eagerly in `__init__.py`):
```python
from kida import Environment
  → kida.environment (core.py, filters.py, loaders.py, tests.py, etc.)
  → kida.template (Template, LoopContext, CachedBlocksDict)
  → kida.utils.html (Markup, html_escape, etc.)
  → kida.lexer (Lexer, LexerConfig)
  → kida._types
```

Most of the ~22ms cold-start time is spent importing Kida itself, not compiling templates.

### Proposed Solutions

#### Option A: Lazy Imports (Recommended)

Use deferred imports so heavy modules load only when needed:

```python
# kida/__init__.py - BEFORE (eager)
from kida.environment import Environment, ...

# kida/__init__.py - AFTER (lazy via __getattr__)
def __getattr__(name: str):
    if name == "Environment":
        from kida.environment import Environment
        return Environment
    # ... etc
```

**Expected improvement**: 50-70% cold-start reduction for scripts that only use `from_string()`.

#### Option B: PEP 690 Lazy Imports (Python 3.14+)

Python 3.14 supports native lazy imports via `-X lazy_imports` or `PYTHONLAZYIMPORTS=1`.

Kida could document this as the recommended approach:
```bash
PYTHONLAZYIMPORTS=1 python my_script.py
```

**Caveat**: Requires Python 3.14+ and explicit opt-in.

#### Option C: Pre-compiled Templates

For production, provide a CLI to pre-compile templates to standalone `.pyc`:

```bash
kida compile templates/ --output .kida_compiled/
```

These can then be imported directly:
```python
from .kida_compiled import render_index
html = render_index({"page": page})
```

**Expected improvement**: 90%+ cold-start reduction (true to the claim).

### Implementation Priority

1. **Option A (lazy imports)** — Immediate, no user changes required
2. **Option C (pre-compiled)** — For production deployments with strict cold-start requirements
3. **Option B (PEP 690)** — Document as advanced optimization

---

## Issue 2: HTML Escape Fast Path Slower Than Expected

### Observation

```
test_escape_vs_naive_chain:  329ns (naive chained .replace())
test_escape_optimized:       750ns (optimized html_escape)
```

The "optimized" escape is **2.3x slower** for typical escape-heavy content.

### Root Cause

Current implementation in `utils/html.py`:

```python
def _escape_str(s: str) -> str:
    # Fast path check using frozenset intersection
    if not _ESCAPE_CHARS.intersection(s):  # <-- This is expensive!
        return s
    return s.translate(_ESCAPE_TABLE)
```

The frozenset intersection creates a temporary set and iterates the entire string even when returning early.

### Proposed Fix

Remove the fast-path check for typical strings (short to medium length):

```python
def _escape_str(s: str) -> str:
    # For strings < 1KB, just translate (fast path check overhead > translate cost)
    if len(s) < 1024:
        return s.translate(_ESCAPE_TABLE)
    # For large strings, check first (avoids full allocation)
    if not _ESCAPE_CHARS.intersection(s):
        return s
    return s.translate(_ESCAPE_TABLE)
```

**Expected improvement**: 2-3x faster escape for typical content.

### Alternative: Pure C Extension

For maximum performance, a tiny C extension for escape could achieve 10-20x speedup. However, this conflicts with Kida's "zero dependencies" goal.

---

## Issue 3: Template.__init__ Overhead

### Observation

Template construction creates many closures and a large namespace dict:

```python
def __init__(self, env, code, name, filename, optimized_ast=None):
    # Creates 10+ closures:
    def _include(...): ...
    def _extends(...): ...
    def _import_macros(...): ...
    def _cache_get(...): ...
    def _cache_set(...): ...
    def _lookup(...): ...
    def _lookup_scope(...): ...
    def _default_safe(...): ...
    def _is_defined(...): ...
    def _null_coalesce(...): ...
    def _spaceless(...): ...
    def _coerce_numeric(...): ...
    def _str_safe(...): ...

    # Then builds large namespace:
    namespace = {
        "__builtins__": {...},
        "_env": env,
        "_filters": env._filters,
        "_tests": env._tests,
        # ... 20+ entries
    }
    exec(code, namespace)
```

### Proposed Optimizations

#### Option A: Lazy Closure Creation

Only create closures when templates actually use the features:

```python
# Detect at compile-time if template uses includes
if uses_include:
    namespace["_include"] = self._make_include_closure(env_ref)
```

**Caveat**: Requires compiler to track feature usage and pass to Template.

#### Option B: Shared Base Namespace

Create a shared base namespace once per Environment, not per Template:

```python
class Environment:
    def _get_base_namespace(self):
        if not hasattr(self, "_base_namespace"):
            self._base_namespace = {
                "__builtins__": {"__import__": __import__},
                "_str": str, "_len": len, "_range": range,
                # ... static entries
            }
        return self._base_namespace
```

Then per-template:
```python
namespace = env._get_base_namespace().copy()
namespace["_env"] = env
namespace["_filters"] = env._filters
# ... only dynamic entries
```

**Expected improvement**: 20-30% faster Template construction.

#### Option C: Bound Method Caching

Instead of closures capturing `env_ref`, use bound methods:

```python
class TemplateHelpers:
    __slots__ = ("_env_ref",)

    def __init__(self, env_ref):
        self._env_ref = env_ref

    def include(self, template_name, context, ...): ...
    def extends(self, template_name, context, blocks): ...

# In Template.__init__:
helpers = TemplateHelpers(env_ref)
namespace["_include"] = helpers.include
namespace["_extends"] = helpers.extends
```

**Benefit**: Single object creation vs multiple closures.

---

## Issue 4: LRU Cache Lock Contention

### Observation

The LRU cache uses `threading.RLock()` for all operations, including reads:

```python
def get(self, key: K) -> V | None:
    with self._lock:  # <-- Lock acquired even for simple reads
        ...
```

For high-concurrency scenarios, this becomes a bottleneck.

### Proposed Fix

Use a read-write lock pattern:

```python
from threading import RLock

class LRUCache:
    def get(self, key):
        # Fast path: just read (no lock for common case)
        try:
            value = self._cache[key]
            # Note: move_to_end is NOT thread-safe, but...
            # For caches, we can accept slightly stale LRU ordering
            return value
        except KeyError:
            self._misses += 1  # atomic on free-threaded Python
            return None
```

**Alternative**: Use Python's built-in `functools.lru_cache` for simple cases, or implement a lock-free concurrent cache.

---

## Issue 5: Large Template Memory Allocation

### Observation

```
test_memory_render_large: 18.7ms (memory measurement)
test_render_large_kida:    3.0ms (render only)
```

The memory measurement shows high allocation overhead.

### Proposed Optimizations

1. **Buffer pre-allocation**: Estimate output size from template and pre-allocate:
   ```python
   buf = [None] * estimated_size  # Pre-allocate slots
   ```

2. **Buffer reuse**: Pool and reuse buffer lists across renders:
   ```python
   _buffer_pool = []
   def get_buffer():
       return _buffer_pool.pop() if _buffer_pool else []
   ```

3. **LoopContext pooling**: Reuse LoopContext objects:
   ```python
   loop = _loop_pool.pop() if _loop_pool else LoopContext.__new__(LoopContext)
   loop._init(items)  # Re-initialize existing object
   ```

---

## Implementation Roadmap

### Phase 1: Quick Wins (Low Risk)

1. ✅ Fix HTML escape fast path — remove intersection check for small strings
2. ✅ Lazy imports in `__init__.py` — reduce cold-start for partial usage
3. ✅ Shared base namespace — reduce Template construction overhead

### Phase 2: Structural Improvements

1. Lazy closure creation in Template
2. Read-optimized LRU cache
3. Buffer pre-allocation heuristics

### Phase 3: Advanced Optimizations

1. Pre-compiled template CLI tool
2. Object pooling for hot paths
3. Optional C extension for escape (as separate package)

---

## Success Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| `html_escape` (single char) | 381ns | 236ns | **38% faster** |
| `html_escape` (typical) | 750ns | 568ns | **24% faster** |
| `render_complex_kida` | 17.9μs | 14.9μs | **17% faster** |
| `render_minimal_kida` | 1.13μs | 1.00μs | **12% faster** |
| `render_large_kida` | 3.05ms | 2.61ms | **14% faster** |

### Remaining Targets

| Metric | Current | Target | Notes |
|--------|---------|--------|-------|
| Cold-start (no cache) | 22ms | <10ms | Requires lazy imports |
| Cold-start (warm cache) | 22ms | <5ms | Requires pre-compilation |

---

## Appendix: Benchmark Commands

```bash
# Run all benchmarks
uv run pytest benchmarks/benchmark_render.py benchmarks/benchmark_scaling.py \
  benchmarks/benchmark_escape.py --benchmark-only -v

# Run cold-start suite
uv run python benchmarks/benchmark_cold_start.py

# Compare to baseline
uv run pytest benchmarks/benchmark_render.py --benchmark-compare
```
