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

### CPython 3.14 (GIL on)

| Template                | Kida   | Jinja2 | Speedup |
| ----------------------- | ------ | ------ | ------- |
| Minimal (hello)         | 1.06µs | 3.72µs | 3.5x    |
| Small (10 vars)         | 4.65µs | 7.60µs | 1.6x    |
| Medium (100 vars)       | 0.260ms| 0.264ms| ~1.0x   |
| Large (1000 loop items) | 2.75ms | 3.24ms | 1.18x   |
| Complex (inheritance)   | 15.5µs | 26.7µs | 1.7x    |

### CPython 3.14t (free-threaded, `PYTHON_GIL=0`, 3.14.2+ft)

Single-threaded benchmarks re-run after pinning the repo to Python 3.14t:

| Template                | Kida    | Jinja2  | Speedup |
| ----------------------- | ------- | ------- | ------- |
| Minimal (hello)         | 0.94µs  | 3.21µs  | 3.4x    |
| Small (10 vars)         | 3.78µs  | 6.38µs  | 1.7x    |
| Medium (100 vars)       | 0.214ms | 0.229ms | 1.07x   |
| Large (1000 loop items) | 2.27ms  | 2.48ms  | 1.09x   |
| Complex (inheritance)   | 14.6µs  | 18.3µs  | 1.26x   |

### Concurrent Performance (Free-Threading)

**This is where Kida shines.** Under concurrent workloads, Kida's thread-safe design delivers significant advantages:

| Workers | Kida    | Jinja2  | Speedup |
| ------- | ------- | ------- | ------- |
| 1       | 3.31ms  | 3.49ms  | 1.05x   |
| 2       | 2.09ms  | 2.51ms  | 1.20x   |
| 4       | 1.53ms  | 2.05ms  | 1.34x   |
| 8       | 2.06ms  | 3.74ms  | **1.81x** |

**Key finding**: Jinja2 has *negative scaling* at 8 workers (slower than 4 workers), while Kida maintains gains. This reveals internal contention in Jinja2 that hurts it under high concurrency.

| Metric | Single-Threaded | 8 Workers |
| ------ | --------------- | --------- |
| Kida advantage | 5-10% | **81%** |

### Lexer Optimization

The lexer uses compiled regex for delimiter detection, achieving 49x faster `_find_next_construct()` compared to multiple `str.find()` calls:

| Method | Time | Speedup |
| ------ | ---- | ------- |
| `re.search()` (current) | 6.97µs | 49x |
| `str.find()` × 3 (old) | 343µs | baseline |

### Where to Improve Next

- Medium templates (single-threaded): marginal gains remaining
- Concurrent workloads: already optimized for free-threading
- Cold-start: bytecode cache delivers +7-8% median (42.37ms → 39.18ms in `benchmarks/benchmark_cold_start.py`); larger gains require lazy imports or precompiled templates

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

Frequently-used functions are bound once:

```python
_escape = env._filters["escape"]
_str = str
_out = []
# ... rest of render
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

Cold-start improvement (measured): ~7-8% with bytecode cache enabled (baseline 42.37ms → 39.18ms). Larger gains will come from lazy imports or precompiled templates.

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
