# RFC: Performance Optimization Opportunities

**Status**: Draft  
**Created**: 2026-01-11  
**Based On**: Benchmark analysis from `benchmarks/`

---

## Executive Summary

Benchmark analysis reveals several optimization opportunities:

| Priority | Issue | Confidence | Risk | Expected Gain |
|----------|-------|------------|------|---------------|
| 1 | HTML escape fast-path overhead | 🟢 High | Low | 2-3x escape speed |
| 2 | Shared base namespace | 🟡 Medium | Low | 20-30% init speed |
| 3 | Lazy module imports | 🟡 Medium | Medium | 50-70% cold-start |
| 4 | Buffer pre-allocation | 🟠 Low | Low | TBD (needs profiling) |
| 5 | LRU cache concurrency | 🔴 Needs rework | High | Minimal in practice |

**Key finding**: The documented "90%+ bytecode cache improvement" claim needs investigation—actual measurement shows only 7% improvement. Root cause appears to be module import time, not template compilation.

---

## Prerequisites: Validation Before Implementation

Before implementing optimizations, gather baseline data:

```bash
# 1. Profile import time breakdown (Issue 1)
python -X importtime -c "from kida import Environment" 2>&1 | head -30

# 2. Measure Template.__init__ cost (Issue 3)
python -c "
import timeit
from kida import Environment
env = Environment()
code = env._compile('{{ x }}', 'test')
print('Template.__init__:', timeit.timeit(
    lambda: env._make_template(code, 'test', None), number=10000
) / 10000 * 1e6, 'μs')
"

# 3. Find escape threshold crossover point (Issue 2)
uv run pytest benchmarks/benchmark_escape.py -k threshold -v

# 4. Memory allocation profiling (Issue 5)
python -c "
import tracemalloc
from kida import Environment
env = Environment()
tpl = env.from_string('{% for i in items %}{{ i }}{% endfor %}')
tracemalloc.start()
tpl.render({'items': range(1000)})
current, peak = tracemalloc.get_traced_memory()
print(f'Current: {current/1024:.1f}KB, Peak: {peak/1024:.1f}KB')
"
```

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

⚠️ Only 7.2% improvement — investigate root cause (see Issue 1)
```

---

## Issue 1: Cold-Start Bytecode Cache Ineffective

### Open Question

**Where does the "90%+ improvement" claim originate?**

- [ ] Documentation (which page?)
- [ ] Previous benchmark (which commit?)
- [ ] Assumption based on Jinja2 behavior?

This needs verification before proceeding. The claim may refer to a different metric (e.g., template parse time only, not total cold-start).

### Hypothesis: Import Time Dominates

The bytecode cache accelerates **template compilation**, not **module import**.

**Current import chain** (all imported eagerly in `__init__.py`):
```python
from kida import Environment
  → kida.environment (core.py, filters.py, loaders.py, tests.py, etc.)
  → kida.template (Template, LoopContext, CachedBlocksDict)
  → kida.utils.html (Markup, html_escape, etc.)
  → kida.lexer (Lexer, LexerConfig)
  → kida._types
```

**To validate**: Run import profiling to confirm time distribution:
```bash
python -X importtime -c "from kida import Environment" 2>&1 | head -30
```

If import time is >80% of cold-start, lazy imports will help. If not, the bottleneck is elsewhere.

### Proposed Solutions

#### Option A: PEP 690 Lazy Imports (Recommended)

Python 3.14 supports native lazy imports via `-X lazy_imports` or `PYTHONLAZYIMPORTS=1`.

```bash
PYTHONLAZYIMPORTS=1 python my_script.py
```

**Pros**: Zero code changes, handles all imports automatically.
**Cons**: Explicit opt-in, may cause issues with modules that have import-time side effects.

**Decision criteria**: Validate Kida has no import-time side effects, then document as recommended approach.

#### Option B: Lazy Imports via `__getattr__`

If PEP 690 has issues, use deferred imports via module-level `__getattr__`:

```python
# kida/__init__.py
_LAZY_IMPORTS = {
    "Environment": "kida.environment",
    "Template": "kida.template",
    "Markup": "kida.utils.html",
}

def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module = __import__(_LAZY_IMPORTS[name], fromlist=[name])
        return getattr(module, name)
    raise AttributeError(f"module 'kida' has no attribute {name!r}")

def __dir__():
    return list(_LAZY_IMPORTS.keys()) + [...]  # For IDE autocomplete
```

**Expected improvement**: 50-70% cold-start reduction for scripts that only use `from_string()`.

**Decision criteria**: Implement only if PEP 690 has compatibility issues with Kida.

#### Option C: Pre-compiled Templates

For production, provide a CLI to pre-compile templates to standalone Python modules:

```bash
kida compile templates/ --output .kida_compiled/
```

Generated code:
```python
# .kida_compiled/index.py
def render(context: dict) -> str:
    # Direct Python code, no Kida import needed at runtime
    return f"<h1>{context['title']}</h1>..."
```

**Expected improvement**: 90%+ cold-start reduction (eliminates Kida import entirely).

**Caveats**:
- Requires build step in deployment pipeline
- Loses dynamic template reloading
- Filter/test customization must be compile-time

**Decision criteria**: Implement for serverless/Lambda deployments where cold-start is critical.

### Implementation Priority

| Option | When to Use | Effort | User Impact |
|--------|-------------|--------|-------------|
| A (PEP 690) | Default recommendation | None | Opt-in flag |
| B (`__getattr__`) | PEP 690 incompatible | Low | None |
| C (pre-compiled) | Serverless/cold-start critical | Medium | Build step required |

---

## Issue 2: HTML Escape Fast Path Slower Than Expected

**Confidence**: 🟢 High — clear benchmark data, well-understood root cause.

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

The frozenset intersection:
1. Creates a temporary set object
2. Iterates the entire string to build the set
3. Only then checks for intersection

For strings that need escaping (common case), this is pure overhead.

### Proposed Fix

Remove the fast-path check for typical strings:

```python
def _escape_str(s: str) -> str:
    # For strings below threshold, just translate
    # (fast path check overhead > translate cost for small strings)
    if len(s) < _ESCAPE_THRESHOLD:
        return s.translate(_ESCAPE_TABLE)
    # For large strings, check first (avoids full allocation if no escapes needed)
    if not _ESCAPE_CHARS.intersection(s):
        return s
    return s.translate(_ESCAPE_TABLE)

_ESCAPE_THRESHOLD = 1024  # Validate with benchmark
```

### Validation Required

The 1KB threshold is a hypothesis. Validate with crossover benchmark:

```python
# benchmarks/benchmark_escape.py
@pytest.mark.parametrize("size", [64, 128, 256, 512, 1024, 2048, 4096])
def test_escape_threshold_crossover(benchmark, size):
    """Find where intersection check becomes faster than blind translate."""
    s = "x" * size  # No escapes needed
    # Compare: blind translate vs check-then-translate
```

**Expected result**: Crossover around 512-2048 bytes depending on CPU cache.

### Decision Criteria

| Approach | Use When |
|----------|----------|
| Always translate | Threshold benchmark shows crossover >2KB |
| Length check + translate | Crossover in 256-2KB range |
| Keep current | Crossover <256 bytes (unlikely) |

### Alternative: Pure C Extension

For maximum performance, a C extension for escape could achieve 10-20x speedup.

**Trade-off**: Conflicts with Kida's "zero dependencies, pure Python" goal.

**Recommendation**: Offer as optional `kida[fast]` extra:
```bash
pip install kida[fast]  # Installs kida-speedups C extension
```

---

## Issue 3: Template.__init__ Overhead

**Confidence**: 🟡 Medium — overhead identified but baseline not measured.

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

### Baseline Measurement Required

Before optimizing, measure current `__init__` cost:

```bash
python -c "
import timeit
from kida import Environment
env = Environment()
code = env._compile('{{ x }}', 'test')

init_time = timeit.timeit(
    lambda: env._make_template(code, 'test', None),
    number=10000
) / 10000

render_time = timeit.timeit(
    lambda: env.from_string('{{ x }}').render({'x': 1}),
    number=10000
) / 10000

print(f'Template.__init__: {init_time * 1e6:.2f}μs')
print(f'Full render:       {render_time * 1e6:.2f}μs')
print(f'Init % of render:  {init_time / render_time * 100:.1f}%')
"
```

**Decision criteria**:
- If init is >30% of render time → optimize (high impact)
- If init is 10-30% of render time → optimize (medium impact)
- If init is <10% of render time → defer (low impact)

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

**Confidence**: 🔴 Needs rework — original proposal has thread-safety issues.

### Observation

The LRU cache uses `threading.RLock()` for all operations, including reads:

```python
def get(self, key: K) -> V | None:
    with self._lock:  # <-- Lock acquired even for simple reads
        ...
```

For high-concurrency scenarios, this could become a bottleneck.

### ⚠️ Original Proposal (Unsafe)

The original proposal to remove locks from reads is **not thread-safe**:

```python
# ❌ UNSAFE: dict access during concurrent mutation can crash
def get(self, key):
    try:
        value = self._cache[key]  # ← Crash if another thread is mutating
        return value
    except KeyError:
        return None
```

Even in Python 3.13+ free-threaded mode, dict reads during writes are undefined behavior.

### Safe Alternatives

#### Option A: Accept Current Lock Overhead (Recommended)

The lock overhead is typically <100ns per operation. For most use cases, this is negligible compared to template compilation (milliseconds).

**Benchmark first**:
```python
# Measure actual lock contention under load
import threading, timeit
from kida._cache import LRUCache

cache = LRUCache(100)
cache.set("key", "value")

def reader():
    for _ in range(10000):
        cache.get("key")

threads = [threading.Thread(target=reader) for _ in range(8)]
# Measure time with varying thread counts
```

**Decision criteria**: Only optimize if contention causes >10% throughput reduction under realistic load.

#### Option B: Use `functools.lru_cache`

For simple key→value lookups, Python's built-in is already optimized:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_template(name: str) -> Template:
    return env._load_template(name)
```

**Trade-off**: Less control over eviction, no manual invalidation.

#### Option C: Copy-on-Read Pattern

For read-heavy workloads, snapshot the cache dict:

```python
class LRUCache:
    def __init__(self):
        self._cache = {}
        self._snapshot = {}
        self._lock = RLock()
    
    def get(self, key):
        # Read from snapshot (no lock needed)
        return self._snapshot.get(key)
    
    def set(self, key, value):
        with self._lock:
            self._cache[key] = value
            self._snapshot = self._cache.copy()  # Atomic reference swap
```

**Trade-off**: Higher memory usage, write overhead.

### Recommendation

**Defer this optimization.** The current locking is safe and the overhead is likely negligible for typical template caching workloads. Profile under production load before investing in complex concurrent data structures.

---

## Issue 5: Large Template Memory Allocation

**Confidence**: 🟠 Low — measurement unclear, needs profiling before optimization.

### Observation

```
test_memory_render_large: 18.7ms (memory measurement)
test_render_large_kida:    3.0ms (render only)
```

The 6x difference between memory measurement and render-only suggests either:
1. High allocation overhead during render
2. `tracemalloc` instrumentation overhead
3. GC pressure from temporary objects

### Profiling Required

Before optimizing, identify allocation hotspots:

```python
import tracemalloc
from kida import Environment

env = Environment()
tpl = env.from_string('{% for i in items %}{{ i }}{% endfor %}')
context = {'items': range(10000)}

tracemalloc.start()
result = tpl.render(context)
snapshot = tracemalloc.take_snapshot()

# Top allocation sites
for stat in snapshot.statistics('lineno')[:10]:
    print(stat)
```

**Questions to answer**:
1. What % of allocations are in Kida code vs Python builtins?
2. Are string concatenations the dominant cost?
3. How many LoopContext objects are created per render?

### Proposed Optimizations (Conditional)

Only implement after profiling confirms the bottleneck:

#### If string building dominates:

```python
# Buffer pre-allocation with size hint
def _render(context):
    buf = []
    buf_append = buf.append  # Avoid method lookup in loop
    # ... render logic using buf_append() ...
    return ''.join(buf)
```

#### If object creation dominates:

```python
# LoopContext pooling
_loop_pool: list[LoopContext] = []

def _get_loop_context(items):
    if _loop_pool:
        loop = _loop_pool.pop()
        loop._reset(items)
        return loop
    return LoopContext(items)

def _release_loop_context(loop):
    _loop_pool.append(loop)
```

**Caveat**: Object pooling adds complexity and can cause subtle bugs with retained references.

#### If GC pauses dominate:

```python
import gc

def render_batch(templates, contexts):
    gc.disable()
    try:
        return [t.render(c) for t, c in zip(templates, contexts)]
    finally:
        gc.enable()
```

**Caveat**: Only for batch rendering; not suitable for interactive use.

### Decision Criteria

| Finding | Action |
|---------|--------|
| String building >50% of allocs | Implement buffer optimization |
| Object creation >30% of allocs | Consider pooling |
| tracemalloc overhead is the cause | No action needed |
| GC pauses >10% of time | Document batch rendering pattern |

---

## Implementation Roadmap

### Phase 0: Validation (Required First)

Before implementing any optimizations:

- [ ] Run import profiling: `python -X importtime -c "from kida import Environment"`
- [ ] Measure Template.__init__ baseline (see Issue 3)
- [ ] Find escape threshold crossover point (see Issue 2)
- [ ] Profile memory allocation hotspots (see Issue 5)
- [ ] Locate source of "90%+ cache improvement" claim

### Phase 1: Quick Wins (Low Risk, High Confidence)

| Task | Issue | Prerequisite | Effort |
|------|-------|--------------|--------|
| Fix HTML escape threshold | #2 | Threshold benchmark | 1 hour |
| Shared base namespace | #3 | Init baseline shows >10% | 2 hours |
| Validate & document PEP 690 | #1 | Confirm no side effects | 1 hour |

### Phase 2: Conditional Improvements (Medium Risk)

| Task | Issue | Prerequisite | Effort |
|------|-------|--------------|--------|
| Lazy imports via `__getattr__` | #1 | PEP 690 has issues | 2 hours |
| Lazy closure creation | #3 | Init baseline shows >30% | 8 hours |
| Buffer pre-allocation | #5 | Memory profiling shows string alloc dominates | 4 hours |

### Phase 3: Advanced Optimizations (High Effort)

| Task | Issue | Prerequisite | Effort |
|------|-------|--------------|--------|
| Pre-compiled template CLI | #1 | User demand for serverless | 16+ hours |
| Object pooling | #5 | Memory profiling shows object alloc dominates | 8 hours |
| Optional C extension (`kida[fast]`) | #2 | User demand for extreme perf | 16+ hours |

### Deferred / Not Recommended

| Task | Issue | Reason |
|------|-------|--------|
| Lock-free LRU cache | #4 | Thread-safety risks, likely negligible gain |

---

## Success Metrics

### Current Baseline (Measured)

| Metric | Current | Source |
|--------|---------|--------|
| `html_escape` (typical) | 750ns | `benchmark_escape.py` |
| `render_minimal_kida` | 1.13μs | `benchmark_render.py` |
| `render_complex_kida` | 17.9μs | `benchmark_render.py` |
| `render_large_kida` | 3.05ms | `benchmark_render.py` |
| Cold-start (no cache) | 22.84ms | `benchmark_cold_start.py` |
| Cold-start (warm cache) | 21.20ms | `benchmark_cold_start.py` |

### Projected Improvements (Require Validation)

| Metric | Current | Target | Improvement | Confidence |
|--------|---------|--------|-------------|------------|
| `html_escape` (typical) | 750ns | ~300ns | ~60% faster | 🟢 High |
| Template.__init__ | TBD | TBD | 20-30% | 🟡 Medium |
| `render_minimal_kida` | 1.13μs | <1.0μs | ~12% | 🟡 Medium |
| Cold-start (lazy imports) | 22ms | <10ms | ~55% | 🟡 Medium |
| Cold-start (pre-compiled) | 22ms | <3ms | ~85% | 🟢 High |

### Targets NOT Pursued

| Metric | Why Not |
|--------|---------|
| LRU cache throughput | Thread-safety risks outweigh likely-negligible gains |
| Memory allocation | Requires profiling first; may be tracemalloc overhead |

---

## Appendix A: Benchmark Commands

### Standard Benchmarks

```bash
# Run all benchmarks
uv run pytest benchmarks/benchmark_render.py benchmarks/benchmark_scaling.py \
  benchmarks/benchmark_escape.py --benchmark-only -v

# Run cold-start suite
uv run python benchmarks/benchmark_cold_start.py

# Compare to saved baseline
uv run pytest benchmarks/benchmark_render.py --benchmark-compare=baseline.json

# Save new baseline
uv run pytest benchmarks/benchmark_render.py --benchmark-save=baseline
```

### Validation Commands (Run Before Implementing)

```bash
# Issue 1: Import time breakdown
python -X importtime -c "from kida import Environment" 2>&1 | head -30

# Issue 2: Escape threshold crossover
uv run pytest benchmarks/benchmark_escape.py -k threshold -v

# Issue 3: Template.__init__ cost
python -c "
import timeit
from kida import Environment
env = Environment()
code = env._compile('{{ x }}', 'test')
t = timeit.timeit(lambda: env._make_template(code, 'test', None), number=10000)
print(f'Template.__init__: {t/10000*1e6:.2f}μs')
"

# Issue 5: Memory allocation hotspots
python -c "
import tracemalloc
from kida import Environment
env = Environment()
tpl = env.from_string('{% for i in items %}{{ i }}{% endfor %}')
tracemalloc.start()
tpl.render({'items': range(10000)})
for s in tracemalloc.take_snapshot().statistics('lineno')[:10]:
    print(s)
"
```

---

## Appendix B: Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-11 | Draft RFC created | Benchmark analysis complete |
| | LRU cache optimization deferred | Thread-safety risks, likely negligible gain |
| | Phase 0 validation added | Several proposals lack baseline data |

---

## Appendix C: Related Work

- **Jinja2 bytecode cache**: Uses `marshal` for template caching; similar approach to Kida
- **Mako compiled templates**: Pre-compiles to Python modules (similar to Option C)
- **PEP 690**: Python 3.14 lazy imports specification
- **markupsafe**: C extension for HTML escape (reference for `kida[fast]`)
