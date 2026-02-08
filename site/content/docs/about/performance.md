---
title: Performance
description: Benchmarks and optimization tips
draft: false
weight: 20
lang: en
type: doc
tags:
- about
- performance
keywords:
- performance
- benchmarks
- optimization
icon: zap
---

<!-- markdownlint-disable MD025 -->

# Performance

Kida is designed for high-performance template rendering.

## Benchmarks

Methodology: `pytest-benchmark`, identical templates and contexts, `auto_reload=false`, bytecode cache enabled. Units are mean times. JSON exports live in `.benchmarks/`.

> Numbers from `benchmarks/test_benchmark_render.py` (file-based templates,
> Python 3.14.2 free-threading build, Apple Silicon).

### CPython 3.14t (free-threaded, `PYTHON_GIL=0`, 3.14.2+ft)

| Template                | Kida    | Jinja2  | Speedup |
| ----------------------- | ------- | ------- | ------- |
| Minimal (hello)         | 3.48µs  | 5.44µs  | 1.56x   |
| Small (12 vars)         | 8.88µs  | 10.24µs | 1.15x   |
| Medium (~100 vars)      | 0.395ms | 0.373ms | ~1.0x   |
| Large (1000 loop items) | 1.91ms  | 4.09ms  | **2.14x** |
| Complex (inheritance)   | 21.4µs  | 29.0µs  | 1.36x   |

**Key finding**: Kida is **2.14x faster** on large templates (1000 loop items) due to the StringBuilder pattern vs Jinja2's generator protocol. Medium templates show parity because HTML escaping dominates — Jinja2 uses markupsafe's C extension while Kida uses pure Python (zero-dependency trade-off).

### Concurrent Performance (Free-Threading)

> Numbers from `benchmarks/test_benchmark_full_comparison.py` (inline medium
> template, 100 total renders distributed across workers).

**This is where Kida shines.** Under concurrent workloads, Kida's thread-safe design delivers advantages that grow with worker count:

| Workers | Kida    | Jinja2  | Speedup |
| ------- | ------- | ------- | ------- |
| 1       | 1.80ms  | 1.80ms  | ~same   |
| 2       | 1.12ms  | 1.15ms  | ~same   |
| 4       | 1.62ms  | 1.90ms  | **1.17x** |
| 8       | 1.76ms  | 1.97ms  | **1.12x** |

**Key finding**: Jinja2 shows *negative scaling* at 4+ workers (slower than 1 worker), while Kida maintains consistent performance. This reveals internal contention in Jinja2 under high concurrency.

### Lexer Optimization

The lexer uses a compiled regex for delimiter detection, achieving 5-24x faster `_find_next_construct()` compared to multiple `str.find()` calls:

| Method | Speedup |
| ------ | ------- |
| `re.search()` (current) | 5-24x |
| `str.find()` × 3 (old) | baseline |

### Render Loop Optimizations

**Type-aware escaping**: Numeric types (int, float, bool) bypass HTML escaping since they can't contain special characters:

| Value Type | Time (10k escapes) | Speedup |
| ---------- | ------------------ | ------- |
| Numeric (optimized) | 0.90ms | **1.9x** |
| String (full escape) | 1.74ms | baseline |

**Lazy LoopContext**: When `loop.*` properties aren't used, Kida iterates directly over items without creating a LoopContext wrapper:

| Loop Type | Time (10k items) | Speedup |
| --------- | ---------------- | ------- |
| Without `loop.*` | 202.7ms | **1.80x** |
| With `loop.*` | 365.7ms | baseline |

### Compilation Time

> Numbers from `benchmarks/test_benchmark_render.py` compile benchmarks.

| Template | Kida    | Jinja2  | Ratio |
| -------- | ------- | ------- | ----- |
| Small    | 4.03ms  | 1.60ms  | 2.5x slower |
| Medium   | 6.04ms  | 4.18ms  | 1.4x slower |
| Large    | 4.62ms  | 1.03ms  | 4.5x slower |
| Complex  | 5.08ms  | 1.17ms  | 4.3x slower |

Kida's compilation is slower because it builds a full AST (lexer → parser → AST → compiler → Python code → `exec()`). This cost is amortized by the bytecode cache — recompilation only happens when template source changes.

### Where to Improve Next

- Medium templates: HTML escaping overhead dominates (pure Python vs markupsafe C extension)
- Cold-start: lazy analysis imports cut import time from 60ms to 31ms (48% improvement)
- Compilation: slower than Jinja2 but amortized by bytecode cache

Run locally:

```bash
# GIL on
uv run pytest benchmarks/benchmark_render.py --benchmark-only \
  --benchmark-json .benchmarks/render_auto_reload_off.json \
  --override-ini "python_files=benchmark_*.py test_*.py"

# Free-threaded
PYTHON_GIL=0 uv run --python 3.14t pytest benchmarks/benchmark_render.py \
  --benchmark-only --benchmark-json .benchmarks/render_free_thread.json \
  --override-ini "python_files=benchmark_*.py test_*.py"
```

## Why Kida is Fast

### StringBuilder Pattern

Kida uses `list.append()` + `"".join()` for O(n) rendering:

```python
# Kida's approach
def render():
    _out = []
    _out.append("Hello, ")
    _out.append(name)
    _out.append("!")
    return "".join(_out)
```

**vs Jinja2's generator pattern**:

```python
# Jinja2's approach
def render():
    yield "Hello, "
    yield name
    yield "!"
```

The StringBuilder pattern has lower overhead:

- No generator/iterator protocol
- Single memory allocation for final string
- 25-40% faster in benchmarks

### Local Variable Caching

Frequently-used functions are bound to locals once at the top of each render function:

```python
_e = _escape   # Local alias for escape function
_s = _str      # Local alias for str()
_append = buf.append  # Local alias for list.append
# ... rest of render uses _e, _s, _append (LOAD_FAST)
```

### O(1) Operator Dispatch

Token handling uses dict-based dispatch, not if/elif chains:

```python
HANDLERS = {
    "if": handle_if,
    "for": handle_for,
    # ...
}
handler = HANDLERS.get(token.value)
```

### Type-Aware HTML Escaping

Kida skips escaping for numeric types that can't contain HTML special characters:

```python
def html_escape(value):
    # Skip numeric types - cannot contain <>&"'
    if type(value) is int or type(value) is float or type(value) is bool:
        return str(value)  # Fast path
    return str(value).translate(_ESCAPE_TABLE)
```

### Lazy LoopContext

When `loop.*` properties aren't used, Kida generates direct iteration:

```python
# When loop.index, loop.first, etc. are NOT used:
for item in _loop_items:  # Direct iteration (1.80x faster)
    ...

# When loop.* IS used:
loop = _LoopContext(_loop_items)  # Full context tracking
for item in loop:
    ...
```

### Compile-Time Optimization

Kida is AST-native and ready for more passes, but today relies on:

- Python’s optimizer for constant folding
- Planned (not yet shipped): dead code elimination and richer static eval

## Caching Strategies

### Template Cache

Compiled templates are cached in memory:

```python
env = Environment(
    cache_size=400,  # Max templates
    auto_reload=False,  # Skip mtime checks
)
```

### Bytecode Cache

Persist compiled bytecode for cold starts:

```python
from kida.bytecode_cache import BytecodeCache

env = Environment(
    bytecode_cache=BytecodeCache("__pycache__/kida/"),
)
```

Cold-start improvement: bytecode cache saves ~7-8% on first render. Lazy analysis imports (added in v0.x) reduced `from kida import Environment` from ~60ms to ~31ms (48% faster) by deferring `kida.nodes` (974 lines of AST definitions) until analysis is actually needed.

### Fragment Cache

Cache expensive template sections:

```kida
{% cache "sidebar-" + user.id %}
    {{ render_expensive_sidebar(user) }}
{% end %}
```

## Optimization Tips

### 1. Disable Auto-Reload in Production

```python
# Production
env = Environment(auto_reload=False)
```

### 2. Pre-Warm Template Cache

```python
def warmup():
    for name in ["base.html", "home.html", "post.html"]:
        env.get_template(name)

warmup()  # On startup
```

### 3. Use Bytecode Cache

```python
env = Environment(
    bytecode_cache=BytecodeCache("__pycache__/kida/"),
)
```

### 4. Precompute in Python

```python
# ✅ Python handles complexity
template.render(
    items=sorted_items,
    total=calculated_total,
    formatted_date=format_date(date),
)

# ❌ Complex logic in template
# {% set total = 0 %}{% for i in items %}...
```

### 5. Use Fragment Caching

```kida
{# Cache expensive computations #}
{% cache "recent-posts" %}
    {% for post in get_recent_posts() %}
        {{ render_post_card(post) }}
    {% end %}
{% end %}
```

### 6. Minimize Filter Chains

```kida
{# Less efficient: multiple passes #}
{{ text | lower | trim | truncate(100) }}

{# More efficient: single Python call #}
{{ preprocess(text) }}
```

## Profiling

### Render Accumulator (Opt-in)

Profile template rendering with detailed block timings:

```python
from kida.render_accumulator import profiled_render

with profiled_render() as metrics:
    html = template.render(page=page, site=site)

print(metrics.summary())
# {
#   "total_ms": 12.5,
#   "blocks": {
#     "content": {"ms": 8.2, "calls": 1},
#     "nav": {"ms": 2.1, "calls": 1},
#   },
#   "includes": {"partials/sidebar.html": 2},
#   "macros": {"render_card": 15},
#   "filters": {"escape": 45, "truncate": 12},
# }
```

**Zero overhead when disabled**—profiling only runs inside `profiled_render()`.

### Template Cache Stats

```python
info = env.cache_info()
print(f"Hit rate: {info['template']['hit_rate']:.1%}")
```

### Time Individual Renders

```python
import time

start = time.perf_counter()
html = template.render(**context)
elapsed = time.perf_counter() - start
print(f"Render: {elapsed*1000:.2f}ms")
```

### Memory Usage

```python
import sys

template = env.get_template("page.html")
print(f"Size: {sys.getsizeof(template)} bytes")
```

## See Also

- [[docs/about/architecture|Architecture]] — How Kida works
- [[docs/reference/configuration|Configuration]] — Cache options
- [[docs/syntax/caching|Caching]] — Fragment cache syntax
