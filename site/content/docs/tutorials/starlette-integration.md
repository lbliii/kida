---
title: Starlette & FastAPI Integration
description: Use Kida with Starlette and FastAPI via kida.contrib.starlette
draft: false
weight: 22
lang: en
type: doc
tags:
  - tutorials
  - starlette
  - fastapi
  - framework
keywords:
  - Starlette
  - FastAPI
  - contrib
  - integration
  - async
icon: zap
---

# Starlette & FastAPI Integration

Use Kida with Starlette and FastAPI through `kida.contrib.starlette`. The integration provides `KidaTemplates` -- a drop-in replacement for Starlette's `Jinja2Templates` that supports context processors, HTMX metadata, and async rendering.

## Installation

```bash
pip install starlette kida
# or for FastAPI:
pip install fastapi uvicorn kida
```

## Starlette Setup

```python
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route
from kida.contrib.starlette import KidaTemplates

templates = KidaTemplates(directory="templates")

async def homepage(request: Request):
    return templates.TemplateResponse(
        request, "home.html", {"title": "Home"}
    )

app = Starlette(routes=[
    Route("/", homepage),
])
```

The `KidaTemplates` constructor accepts:

| Parameter | Description |
|-----------|-------------|
| `directory` | Path to template directory |
| `env` | Pre-configured Kida `Environment` (use instead of `directory`) |
| `context_processors` | List of callables that take a request and return a dict |
| `**env_kwargs` | Extra keyword arguments passed to `Environment()` |

You must provide either `directory` or `env`, but not both.

### Using a Pre-configured Environment

```python
from kida import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=True,
)

# Register custom filters/globals on env first
@env.filter()
def currency(value):
    return f"${value:,.2f}"

templates = KidaTemplates(env=env)
```

### Context Processors

Context processors run on every `TemplateResponse` and inject additional variables into the template context:

```python
def user_context(request):
    return {"current_user": request.state.user}

def site_context(request):
    return {"site_name": "My App"}

templates = KidaTemplates(
    directory="templates",
    context_processors=[user_context, site_context],
)
```

Every template rendered through `TemplateResponse` will have access to `current_user` and `site_name` without passing them explicitly.

## FastAPI Setup

The same `KidaTemplates` class works with FastAPI:

```python
from fastapi import FastAPI, Request
from kida.contrib.starlette import KidaTemplates

app = FastAPI()
templates = KidaTemplates(directory="templates")

@app.get("/")
async def homepage(request: Request):
    return templates.TemplateResponse(
        request, "home.html", {"title": "Home"}
    )

@app.get("/users/{username}")
async def user_profile(request: Request, username: str):
    user = await get_user(username)
    return templates.TemplateResponse(
        request, "profile.html", {"user": user}
    )
```

### `TemplateResponse` Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `request` | (required) | Starlette/FastAPI `Request` object |
| `name` | (required) | Template name to render |
| `context` | `None` | Dict of template variables |
| `status_code` | `200` | HTTP response status code |
| `headers` | `None` | Additional response headers |
| `media_type` | `None` | Response media type |

The `request` object is automatically added to the template context, so you can access it in templates as `{{ request }}`.

## Streaming Responses

For large pages or real-time content, use Kida's async streaming with Starlette's `StreamingResponse`:

```python
from starlette.responses import StreamingResponse

@app.get("/feed")
async def feed(request: Request):
    template = templates.get_template("feed.html")

    async def generate():
        async for chunk in template.render_stream_async(
            items=await get_items(),
            request=request,
        ):
            yield chunk

    return StreamingResponse(generate(), media_type="text/html")
```

Templates can use `{% flush %}` to control chunk boundaries, sending content to the client as soon as key sections are ready.

## Block Rendering for HTMX

The `KidaTemplates` integration automatically detects HTMX requests and sets RenderContext metadata. When an HTMX request comes in, the following metadata keys are set:

- `hx_request` -- `True` if `HX-Request` header is present
- `hx_target` -- Value of `HX-Target` header
- `hx_trigger` -- Value of `HX-Trigger` header
- `hx_boosted` -- `True` if `HX-Boosted` header is `"true"`

Combine this with `render_block()` to return only the part of the page that HTMX needs:

```python
from fastapi.responses import HTMLResponse

@app.get("/items")
async def items_list(request: Request):
    items = await get_items()
    template = templates.get_template("items.html")

    # If HTMX request, render just the items block
    if request.headers.get("HX-Request"):
        html = template.render_block("items_list", items=items)
    else:
        html = template.render(items=items, request=request)

    return HTMLResponse(html)
```

```kida
{# templates/items.html #}
{% extends "base.html" %}

{% block content %}
    <h1>Items</h1>
    {% block items_list %}
    <ul id="items">
        {% for item in items %}
            <li>{{ item.name }}</li>
        {% end %}
    </ul>
    {% end %}
{% end %}
```

For async streaming of a single block:

```python
from starlette.responses import StreamingResponse

@app.get("/items")
async def items_list(request: Request):
    template = templates.get_template("items.html")

    async def generate():
        async for chunk in template.render_block_stream_async(
            "items_list", items=await get_items()
        ):
            yield chunk

    return StreamingResponse(generate(), media_type="text/html")
```

## Async Templates

Kida supports native async constructs in templates. Use `render_stream_async()` for templates that contain `{% async for %}` or `{{ await }}` expressions:

```python
@app.get("/dashboard")
async def dashboard(request: Request):
    template = templates.get_template("dashboard.html")

    # For templates with async constructs, use render_stream_async
    chunks = []
    async for chunk in template.render_stream_async(request=request):
        chunks.append(chunk)

    return HTMLResponse("".join(chunks))
```

For templates without async constructs, `render_async()` runs the synchronous render in a thread pool so it won't block the event loop:

```python
@app.get("/about")
async def about(request: Request):
    template = templates.get_template("about.html")
    html = await template.render_async(title="About", request=request)
    return HTMLResponse(html)
```

## Complete Example

```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from kida import Environment, FileSystemLoader
from kida.contrib.starlette import KidaTemplates

# Configure environment
env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=True,
)

@env.filter()
def format_datetime(value, fmt="%Y-%m-%d"):
    return value.strftime(fmt)

# Context processor
def common_context(request):
    return {"site_name": "My App"}

# Set up templates
app = FastAPI()
templates = KidaTemplates(env=env, context_processors=[common_context])

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse(
        request, "home.html", {"title": "Home"}
    )

@app.get("/items", response_class=HTMLResponse)
async def items_list(request: Request):
    items = await get_items()
    template = templates.get_template("items.html")

    if request.headers.get("HX-Request"):
        html = template.render_block("items_list", items=items)
        return HTMLResponse(html)

    return templates.TemplateResponse(
        request, "items.html", {"items": items}
    )
```

```kida
{# templates/home.html #}
{% extends "base.html" %}

{% block title %}{{ title }}{% end %}

{% block content %}
    <h1>{{ title }}</h1>
    <p>Welcome to {{ site_name }}!</p>
{% end %}
```

## See Also

- [[docs/tutorials/flask-integration|Flask Integration]] -- Flask setup guide
- [[docs/tutorials/django-integration|Django Integration]] -- Django setup guide
- [[docs/advanced/csp|Content Security Policy]] -- CSP nonce injection
- [[docs/about/performance|Performance]] -- Production optimization
