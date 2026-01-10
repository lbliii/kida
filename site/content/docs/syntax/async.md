---
title: Async
description: Async iteration and await in templates
draft: false
weight: 80
lang: en
type: doc
tags:
- syntax
- async
keywords:
- async
- await
- async for
- asyncio
icon: refresh-cw
---

# Async

Kida supports native async/await syntax for async template rendering.

## Async For

Iterate over async iterables:

```kida
{% async for user in fetch_users() %}
    <li>{{ user.name }}</li>
{% end %}
```

The template must be rendered with `render_async()`:

```python
import asyncio
from kida import Environment

async def main():
    env = Environment()
    template = env.from_string("""
        {% async for item in items %}
            {{ item }}
        {% end %}
    """)

    async def items():
        for i in range(3):
            yield i

    result = await template.render_async(items=items())
    print(result)

asyncio.run(main())
```

## Await Expressions

Await async functions in expressions:

```kida
{{ await fetch_data(user_id) }}
```

## Async Context

When using `render_async()`, the template runs in an async context:

```python
async def render_page():
    template = env.get_template("page.html")
    return await template.render_async(
        user=await get_user(),
        posts=await get_posts(),
    )
```

## Sync vs Async Rendering

| Method | Use Case |
|--------|----------|
| `render()` | Sync code, no async operations |
| `render_async()` | Async code, async for/await |

```python
# Sync rendering (blocks)
html = template.render(name="World")

# Async rendering (non-blocking)
html = await template.render_async(items=async_generator())
```

## Async Patterns

### Parallel Fetching

Fetch data concurrently before rendering:

```python
import asyncio

async def render_dashboard():
    # Parallel fetching
    user, posts, stats = await asyncio.gather(
        fetch_user(),
        fetch_posts(),
        fetch_stats(),
    )

    template = env.get_template("dashboard.html")
    return await template.render_async(
        user=user,
        posts=posts,
        stats=stats,
    )
```

### Streaming Iteration

Process large async iterables without buffering:

```kida
{% async for record in database_cursor() %}
    {{ record.name }}
{% end %}
```

## Free-Threading

Kida is designed for Python 3.14t free-threading (PEP 703). Combined with async, you can achieve high concurrency:

```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

async def render_many(templates):
    """Render multiple templates concurrently."""
    return await asyncio.gather(*[
        t.render_async(data=data)
        for t, data in templates
    ])
```

## Error Handling

Async errors propagate normally:

```python
async def main():
    try:
        result = await template.render_async(items=failing_generator())
    except TemplateError as e:
        print(f"Render failed: {e}")
```

## Best Practices

### Use Async Sparingly

Not everything needs async:

```kida
{# ✅ Async for I/O-bound operations #}
{% async for user in fetch_users_from_api() %}

{# ❌ Sync iteration is fine for in-memory data #}
{% for item in items %}
```

### Pre-Fetch When Possible

```python
# ✅ Better: Parallel fetch, then sync render
users = await fetch_users()
posts = await fetch_posts()
html = template.render(users=users, posts=posts)

# Slower: Sequential async in template
# {% async for user in fetch_users() %}
```

## See Also

- [[docs/about/thread-safety|Thread Safety]] — Free-threading support
- [[docs/about/performance|Performance]] — Performance optimization
- [[docs/reference/api|API Reference]] — Template.render_async()
