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

The template must be rendered with an async method — either `render_stream_async()` for streaming or `render_async()` for buffered output:

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

    # Streaming (preferred for large output)
    async for chunk in template.render_stream_async(items=items()):
        print(chunk, end="")

    # Buffered
    result = await template.render_async(items=items())
    print(result)

asyncio.run(main())
```

## Await Expressions

Await async functions in expressions:

```kida
{{ await fetch_data(user_id) }}
```

## Async Loop Variables

Inside `{% async for %}`, the `loop` variable provides index-forward properties. Properties that require knowing total size are **not available** (async iterables have no known length):

| Property | Available | Description |
|----------|-----------|-------------|
| `loop.index` | Yes | 1-based index |
| `loop.index0` | Yes | 0-based index |
| `loop.first` | Yes | True on first iteration |
| `loop.previtem` | Yes | Previous item |
| `loop.cycle(...)` | Yes | Cycle through values |
| `loop.last` | No | Raises error |
| `loop.length` | No | Raises error |
| `loop.revindex` | No | Raises error |

```kida
{% async for user in fetch_users() %}
    {{ loop.index }}: {{ user.name }}
    <tr class="{{ loop.cycle('odd', 'even') }}">
{% end %}
```

## Inline Filtering

Filter items as they arrive with inline `if`:

```kida
{% async for user in fetch_users() if user.active %}
    {{ user.name }}
{% end %}
```

## Empty Clause

Render fallback content when the async iterable yields nothing:

```kida
{% async for notification in get_notifications() %}
    {{ notification.message }}
{% empty %}
    <p>No notifications.</p>
{% end %}
```

## Async Streaming

`render_stream_async()` is the primary way to render async templates. It returns an async generator that yields chunks as they are produced — ideal for HTTP streaming responses:

```python
async def render_page():
    template = env.get_template("page.html")
    async for chunk in template.render_stream_async(items=async_data()):
        yield chunk  # send to client immediately
```

You can also stream individual blocks:

```python
async for chunk in template.render_block_stream_async("content", items=data):
    yield chunk
```

## Detecting Async Templates

Check `template.is_async` to determine whether a template uses async constructs:

```python
template = env.get_template("page.html")
if template.is_async:
    async for chunk in template.render_stream_async(**ctx):
        send(chunk)
else:
    html = template.render(**ctx)
```

> **Important**: Calling `render()` or `render_stream()` on an async template raises `TemplateRuntimeError`. Always use the async methods for async templates.

## Sync vs Async Rendering

| Method | Use Case |
|--------|----------|
| `render()` | Sync code, no async operations |
| `render_stream()` | Sync streaming |
| `render_async()` | Async code, buffered output |
| `render_stream_async()` | Async streaming (preferred for async templates) |
| `render_block_stream_async()` | Async streaming of a single block |

```python
# Sync rendering (blocks)
html = template.render(name="World")

# Async streaming (non-blocking, chunked)
async for chunk in template.render_stream_async(items=async_generator()):
    send_to_client(chunk)

# Async buffered (non-blocking, full string)
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

Process large async iterables without buffering — use `render_stream_async()` to stream output directly to the client:

```python
template = env.from_string("""
    {% async for record in database_cursor() %}
        {{ record.name }}
    {% end %}
""")

async for chunk in template.render_stream_async(
    database_cursor=get_cursor,
):
    response.write(chunk)
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
- [[docs/reference/api|API Reference]] — Template methods, AsyncLoopContext
