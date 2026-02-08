---
title: Comparison
description: Kida vs Jinja2 feature comparison
draft: false
weight: 40
lang: en
type: doc
tags:
- about
- comparison
keywords:
- comparison
- jinja2
- differences
icon: arrows-angle-contract
---

# Comparison

Comprehensive comparison of Kida and Jinja2.

## Feature Matrix

| Feature | Kida | Jinja2 |
|---------|------|--------|
| **Compilation** | AST → AST | String generation |
| **Rendering** | StringBuilder O(n) | Generator yields |
| **Free-threading** | Native (PEP 703, Python 3.14t+) | N/A |
| **Dependencies** | Zero | markupsafe |
| **Block endings** | Unified `{% end %}` | `{% endif %}`, etc. |
| **Dict access** | Subscript-first (`d.items` → key) | getattr-first (`d.items` → method) |
| **Profiling** | Opt-in (`profiled_render()`) blocks/filters/macros | N/A |
| **Pattern matching** | `{% match %}` | N/A |
| **Pipeline** | `\|>` operator | N/A |
| **Block caching** | `{% cache %}` | N/A |
| **Async** | Native | `auto_await()` |

## Syntax Differences

### Block Endings

**Jinja2**:

```jinja2
{% if condition %}
    content
{% endif %}

{% for item in items %}
    {{ item }}
{% endfor %}
```

**Kida** (unified):

```kida
{% if condition %}
    content
{% end %}

{% for item in items %}
    {{ item }}
{% end %}
```

### Pipeline Operator

**Jinja2**:

```jinja2
{{ title | escape | upper | truncate(50) }}
```

**Kida**:

```kida
{{ title |> escape |> upper |> truncate(50) }}
```

### Pattern Matching

**Jinja2**:

```jinja2
{% if status == "active" %}
    Active
{% elif status == "pending" %}
    Pending
{% elif status == "error" %}
    Error
{% else %}
    Unknown
{% endif %}
```

**Kida**:

```kida
{% match status %}
{% case "active" %}
    Active
{% case "pending" %}
    Pending
{% case "error" %}
    Error
{% case _ %}
    Unknown
{% end %}
```

### Block Caching

**Jinja2**: Not built-in (requires extensions)

**Kida**:

```kida
{% cache "sidebar-" + user.id %}
    {{ render_sidebar(user) }}
{% end %}
```

## API Differences

### Filter Registration

**Jinja2**:

```python
env.filters["double"] = lambda x: x * 2
```

**Kida**:

```python
# Method style
env.add_filter("double", lambda x: x * 2)

# Decorator style
@env.filter()
def double(value):
    return value * 2
```

### Markup Class

**Jinja2**: Requires `markupsafe`:

```python
from markupsafe import Markup
```

**Kida**: Built-in:

```python
from kida import Markup
```

### Environment Options

**Jinja2**:

```python
env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(),
    extensions=["jinja2.ext.do"],
)
```

**Kida**:

```python
env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=True,
    cache_size=400,
    fragment_ttl=300.0,
)
```

## Performance

> Numbers from `benchmarks/test_benchmark_render.py` (Python 3.14.2 free-threading, Apple Silicon).

### Single-Threaded

| Template | Kida | Jinja2 | Speedup |
|----------|------|--------|---------|
| Minimal | 3.48µs | 5.44µs | **1.56x** |
| Small | 8.88µs | 10.24µs | 1.15x |
| Medium | 395µs | 373µs | ~same |
| Large | 1.91ms | 4.09ms | **2.14x** |
| Complex | 21.4µs | 29.0µs | 1.36x |

### Concurrent (Free-Threading)

> Numbers from `benchmarks/test_benchmark_full_comparison.py` (inline medium template).

**This is the real differentiator.** Under concurrent workloads on Python 3.14t:

| Workers | Kida | Jinja2 | Speedup |
|---------|------|--------|---------|
| 1 | 1.80ms | 1.80ms | ~same |
| 2 | 1.12ms | 1.15ms | ~same |
| 4 | 1.62ms | 1.90ms | **1.17x** |
| 8 | 1.76ms | 1.97ms | **1.12x** |

Kida's advantage grows with concurrency because:

1. **Thread-safe design**: Copy-on-write updates, no locks
2. **GIL independence**: Declares `_Py_mod_gil = 0`
3. **No shared mutable state**: Renders use only local variables

Jinja2 shows *negative scaling* at 4+ workers (slower than 1 worker), indicating internal contention.

See [[docs/about/performance|Performance Benchmarks]] for detailed measurements and methodology.

## When to Use Kida

Choose Kida if you:

- Need free-threading support (Python 3.14t)
- Want zero dependencies
- Prefer unified block syntax
- Need built-in caching
- Want pattern matching in templates
- Value AST-native compilation
- Work with dict-heavy contexts (API responses, JSON data)
- Need built-in render profiling (block timing, filter/macro tracking)

## When to Keep Jinja2

Keep Jinja2 if you:

- Need LaTeX/RTF output formats
- Use Jinja2-specific extensions
- Have heavy investment in Jinja2 tooling
- Need the sandboxed environment

## See Also

- [[docs/about/performance|Performance]] — Detailed benchmarks
- [[docs/about/architecture|Architecture]] — How Kida works
