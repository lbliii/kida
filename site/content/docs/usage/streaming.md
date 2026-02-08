---
title: Streaming
description: Stream template output as chunks for HTTP responses and large pages
draft: false
weight: 25
lang: en
type: doc
tags:
- usage
- streaming
- async
keywords:
- streaming
- render_stream
- render_stream_async
- chunked
- http
- server-sent events
icon: zap
---

# Streaming

Kida can render templates as a stream of string chunks instead of building the entire output in memory. This is useful for chunked HTTP responses, Server-Sent Events, and large pages.

## Sync Streaming

Use `render_stream()` for synchronous streaming:

```python
from kida import Environment

env = Environment()
template = env.from_string("""
<ul>
{% for item in items %}
    <li>{{ item }}</li>
{% end %}
</ul>
""")

for chunk in template.render_stream(items=["a", "b", "c"]):
    send_to_client(chunk)
```

Each statement-level boundary produces a chunk. Static content, variable output, and control flow transitions all yield independently.

## RenderedTemplate

`RenderedTemplate` is a lazy iterable wrapper around `render_stream()`:

```python
from kida import RenderedTemplate

rendered = RenderedTemplate(template, {"items": data})

# Iterate to get chunks on demand
for chunk in rendered:
    response.write(chunk)

# Or convert to string (consumes all chunks)
html = str(rendered)
```

## Async Streaming

Use `render_stream_async()` to stream templates that contain `{% async for %}` or `{{ await }}` constructs:

```python
async def stream_response():
    template = env.get_template("page.html")
    async for chunk in template.render_stream_async(items=async_data()):
        yield chunk
```

`render_stream_async()` also works on sync templates — it wraps the sync stream, so you can use a single code path:

```python
async for chunk in template.render_stream_async(**context):
    await response.write(chunk)
```

### Block Streaming

Stream a single block instead of the full template:

```python
# Sync
for chunk in template.render_block_stream("content", **context):
    send(chunk)

# Async
async for chunk in template.render_block_stream_async("content", **context):
    await send(chunk)
```

## Framework Integration

### Starlette / FastAPI

```python
from starlette.responses import StreamingResponse

async def page(request):
    template = env.get_template("page.html")

    async def generate():
        async for chunk in template.render_stream_async(items=fetch_items()):
            yield chunk.encode()

    return StreamingResponse(generate(), media_type="text/html")
```

### Flask

```python
from flask import Response

@app.route("/page")
def page():
    template = env.get_template("page.html")
    return Response(
        template.render_stream(items=get_items()),
        content_type="text/html",
    )
```

## What Streams

All template constructs work in streaming mode:

| Construct | Behavior |
|-----------|----------|
| Static text | Yielded as-is |
| `{{ expr }}` | Yielded after evaluation |
| `{% for %}` / `{% async for %}` | Each iteration yields independently |
| `{% if %}` / `{% match %}` | Chosen branch yields |
| `{% extends %}` / `{% block %}` | Parent/child blocks stream |
| `{% include %}` | Included template streams inline |
| `{% capture %}` / `{% spaceless %}` | Buffers internally, yields processed result |
| `{% cache %}` | Buffers internally, yields cached result |

## Choosing a Rendering Method

| Method | Use Case |
|--------|----------|
| `render()` | Fastest — builds full string in memory |
| `render_stream()` | Sync streaming — chunked HTTP, large pages |
| `render_stream_async()` | Async streaming — async iterables, `await` in templates |
| `render_async()` | Async buffered — `await` support, full string output |

For most pages, `render()` is the best choice. Use streaming when the output is large or you want to start sending bytes before the template finishes rendering.

## See Also

- [[docs/syntax/async|Async]] — `{% async for %}` and `{{ await }}` syntax
- [[docs/reference/api|API Reference]] — Full method signatures
- [[docs/about/performance|Performance]] — Benchmark comparisons
