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

### CPython 3.14t (free-threaded, `PYTHON_GIL=0`)

| Template                | Kida   | Jinja2 | Speedup |
| ----------------------- | ------ | ------ | ------- |
| Minimal (hello)         | 1.13µs | 4.06µs | 3.6x    |
| Small (10 vars)         | 4.44µs | 8.03µs | 1.8x    |
| Medium (100 vars)       | 0.265ms| 0.378ms| 1.4x    |
| Large (1000 loop items) | 2.81ms | 2.73ms | ~1.0x   |
| Complex (inheritance)   | 17.2µs | 22.9µs | 1.3x    |

### Where to Improve Next

- Medium templates (GIL on): parity — target >1.2x speedup.
- Large templates (free-threaded): parity — aim for consistent win.
- Cold-start: bytecode cache delivers +13.4% (28.83ms → 24.97ms); 90% claim not yet validated.

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

Cold-start improvement (measured): ~13% with bytecode cache enabled (baseline 28.83ms → 24.97ms). Claim will be updated as further optimizations land.

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
