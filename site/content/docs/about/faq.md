---
title: FAQ
description: Frequently asked questions about Kida
draft: false
weight: 50
lang: en
type: doc
tags:
- about
- faq
keywords:
- faq
- questions
- answers
icon: help-circle
---

# FAQ

Frequently asked questions about Kida.

## General

### Why Kida instead of Jinja2?

Kida offers:

- **Performance**: 25-40% faster rendering (StringBuilder vs generators)
- **Free-threading**: Native PEP 703 support for Python 3.14t
- **Zero dependencies**: No external packages required
- **Modern syntax**: Unified `{% end %}`, pattern matching, pipelines
- **Built-in caching**: `{% cache %}` directive for fragment caching

### Is Kida production-ready?

Kida is in beta. It's suitable for:

- ✅ Personal projects
- ✅ Internal tools
- ⚠️ Production (test thoroughly first)

### What Python versions are supported?

**Required**: Python 3.14+

Kida uses modern Python features and is designed for the free-threaded future.

---

## Dependencies

### Do I need markupsafe?

No. Kida includes a native `Markup` class:

```python
from kida import Markup  # Built-in, not markupsafe
```

---

## Syntax

### Why unified `{% end %}`?

Unified endings are:

- **Simpler**: One syntax to remember
- **Cleaner**: Less visual noise
- **Consistent**: Same pattern for all blocks

```kida
{% if condition %}
    {% for item in items %}
        {{ item }}
    {% end %}
{% end %}
```

### What's the pipeline operator?

`|>` is a more readable way to chain filters:

```kida
{# Traditional pipe #}
{{ title | escape | upper | truncate(50) }}

{# Pipeline (same result) #}
{{ title |> escape |> upper |> truncate(50) }}
```

### How does pattern matching work?

`{% match %}` provides cleaner branching than if/elif chains:

```kida
{% match status %}
{% case "active" %}
    ✓ Active
{% case "pending" %}
    ⏳ Pending
{% case _ %}
    Unknown
{% end %}
```

---

## Performance

### How fast is Kida?

**Single-threaded** (from `benchmarks/test_benchmark_render.py`, Python 3.14.2 free-threading):

| Template | Kida | Jinja2 | Speedup |
|----------|------|--------|---------|
| Minimal | 3.48µs | 5.44µs | 1.56x |
| Small | 8.88µs | 10.24µs | 1.15x |
| Large | 1.91ms | 4.09ms | **2.14x** |

**Concurrent** (from `benchmarks/test_benchmark_full_comparison.py`):

| Workers | Kida | Jinja2 | Speedup |
|---------|------|--------|---------|
| 1 | 1.80ms | 1.80ms | ~same |
| 4 | 1.62ms | 1.90ms | 1.17x |
| 8 | 1.76ms | 1.97ms | **1.12x** |

Kida shines on large templates (2.14x faster due to StringBuilder pattern) and under concurrent workloads — Jinja2 shows negative scaling at 4+ workers while Kida maintains its performance.

### Why is Kida faster?

- **StringBuilder pattern**: O(n) vs generator overhead
- **AST-native compilation**: No string manipulation
- **Local variable caching**: Fewer attribute lookups
- **Compiled regex lexer**: 5-24x faster delimiter detection
- **Thread-safe design**: No locks, copy-on-write updates

### How do I optimize templates?

1. Disable `auto_reload` in production
2. Use bytecode cache for cold starts
3. Cache expensive fragments with `{% cache %}`
4. Precompute complex logic in Python
5. **Use concurrent rendering** on Python 3.14t for maximum throughput

See [[docs/about/performance|Performance]].

---

## Threading

### Is Kida thread-safe?

Yes. All public APIs are thread-safe:

- Configuration is immutable after creation
- Rendering uses only local variables (no shared mutable state)
- Filter/test additions use copy-on-write (no locks)
- Caches use atomic operations

### What's free-threading support?

Kida declares GIL-independence (PEP 703) via module `__getattr__`:

```python
# In kida/__init__.py
def __getattr__(name):
    if name == "_Py_mod_gil":
        return 0  # Py_MOD_GIL_NOT_USED
```

On Python 3.14t with `PYTHON_GIL=0`, templates render with true parallelism—no GIL contention.

### Can I render concurrently?

Yes, and Kida maintains consistent performance under concurrency while Jinja2 degrades:

```python
from concurrent.futures import ThreadPoolExecutor

template = env.get_template("page.html")
contexts = [{"user": f"User {i}"} for i in range(100)]

# On Python 3.14t, this runs with true parallelism
with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(lambda ctx: template.render(**ctx), contexts))
```

Jinja2 shows negative scaling at 4+ workers due to internal contention. Kida's thread-safe design avoids this.

---

## Development

### How do I debug templates?

Use the `debug` filter:

```kida
{{ posts | debug }}
{{ posts | debug("my posts") }}
```

Output goes to stderr with type info and values.

### How do I report bugs?

Open an issue: https://github.com/lbliii/kida/issues

Include:
- Kida version
- Python version
- Minimal reproduction
- Error message

### How do I contribute?

See CONTRIBUTING.md in the repository.

---

## See Also

- [[docs/about/comparison|Comparison]] — Kida vs Jinja2
- [[docs/troubleshooting/|Troubleshooting]] — Common issues
