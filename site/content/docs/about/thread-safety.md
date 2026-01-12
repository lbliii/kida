---
title: Thread Safety
description: Free-threading and concurrent rendering
draft: false
weight: 30
lang: en
type: doc
tags:
- about
- threading
keywords:
- thread safety
- free-threading
- pep 703
- concurrent
icon: shield
---

# Thread Safety

Kida is designed for concurrent rendering in free-threaded Python.

## Free-Threading Support

Kida declares GIL-independence via PEP 703:

```python
# In kida/__init__.py
def __getattr__(name):
    if name == "_Py_mod_gil":
        return 0  # Py_MOD_GIL_NOT_USED
```

This signals that Kida is safe for true parallel execution in Python 3.14t+.

## Thread-Safe Design

### Immutable Configuration

Environment configuration is frozen after construction:

```python
env = Environment(
    loader=FileSystemLoader("templates/"),
    autoescape=True,
)
# Configuration is now immutable
```

### Copy-on-Write Updates

Adding filters/tests creates new dictionaries:

```python
def add_filter(self, name, func):
    # Copy-on-write: no locking needed
    new_filters = self._filters.copy()
    new_filters[name] = func
    self._filters = new_filters
```

### Local Rendering State

Each `render()` call uses only local variables:

```python
def render(self, **context):
    _out = []  # Local buffer
    # ... render logic uses only local state
    return "".join(_out)
```

No shared mutable state between render calls.

### Lock-Free Caching

LRU caches use atomic operations:

```python
# Thread-safe cache access
cached = self._cache.get(name)
self._cache.set(name, template)
```

## Concurrent Rendering

### With ThreadPoolExecutor

```python
from concurrent.futures import ThreadPoolExecutor
from kida import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("page.html")

def render_page(context):
    return template.render(**context)

contexts = [{"name": f"User {i}"} for i in range(100)]

# On Python 3.14t, this runs with true parallelism
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(render_page, contexts))
```

### With asyncio

```python
import asyncio

async def render_async(env, template_name, **context):
    template = env.get_template(template_name)
    return template.render(**context)

async def render_many():
    tasks = [
        render_async(env, "page.html", user=f"User {i}")
        for i in range(100)
    ]
    return await asyncio.gather(*tasks)
```

## What's Safe

| Operation | Thread-Safe |
|-----------|-------------|
| `get_template()` | ✅ Yes |
| `from_string()` | ✅ Yes |
| `template.render()` | ✅ Yes |
| `add_filter()` | ✅ Yes (copy-on-write) |
| `add_test()` | ✅ Yes (copy-on-write) |
| `add_global()` | ✅ Yes (copy-on-write) |
| `clear_cache()` | ✅ Yes |

## Best Practices

### Create Environment Once

```python
# ✅ Create once, reuse everywhere
env = Environment(loader=FileSystemLoader("templates/"))

def handle_request(request):
    template = env.get_template(request.path)
    return template.render(**request.context)
```

### Don't Mutate During Rendering

```python
# ❌ Don't add filters during concurrent rendering
def render_with_filter(value):
    env.add_filter("custom", custom_func)  # Race condition!
    return template.render(value=value)

# ✅ Add filters at startup
env.add_filter("custom", custom_func)

def render(value):
    return template.render(value=value)
```

### Use Template Caching

```python
# Templates are compiled once, then cached
# Concurrent get_template() calls for the same name
# wait for the first compilation to complete
template = env.get_template("page.html")
```

## Performance with Free-Threading

### Kida Scaling (vs single-threaded baseline)

| Workers | Time | Speedup |
|---------|------|---------|
| 1 | 3.31ms | 1.0x |
| 2 | 2.09ms | 1.58x |
| 4 | 1.53ms | 2.16x |
| 8 | 2.06ms | 1.61x |

### Kida vs Jinja2 (Concurrent)

| Workers | Kida | Jinja2 | Kida Advantage |
|---------|------|--------|----------------|
| 1 | 3.31ms | 3.49ms | 1.05x |
| 2 | 2.09ms | 2.51ms | 1.20x |
| 4 | 1.53ms | 2.05ms | 1.34x |
| 8 | 2.06ms | 3.74ms | **1.81x** |

**Key insight**: Jinja2 shows *negative scaling* at 8 workers (slower than 4 workers), indicating internal contention. Kida's thread-safe design avoids this.

## See Also

- [[docs/about/architecture|Architecture]] — Rendering internals
- [[docs/about/performance|Performance]] — Optimization tips
- [[docs/syntax/async|Async]] — Async template rendering
