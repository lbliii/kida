---
title: Starlette & FastAPI Integration
description: Add a typed Kida component and fragment endpoint to FastAPI in ten minutes
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
  - typed components
  - fragment rendering
icon: zap
---

# Starlette & FastAPI Integration

Use Kida's Starlette adapter from FastAPI to render a typed component, a form,
and a named fragment. Kida requires **Python 3.14 or newer**.

> Coming from Jinja2? Read [[docs/get-started/coming-from-jinja2|Coming from
> Jinja2]]. Kida's `{% set %}` is block-scoped and does not leak values out of
> loops or other blocks.

## FastAPI in ten minutes

### 1. Install

```bash
uv add fastapi uvicorn kida-templates
```

### 2. Configure Kida and add two endpoints

```python
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from kida.contrib.starlette import KidaTemplates

app = FastAPI()
templates = KidaTemplates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "components.html",
        {"title": "First component", "summary": "Edit me"},
    )


@app.post("/preview", response_class=HTMLResponse)
async def preview(request: Request) -> HTMLResponse:
    form = parse_qs((await request.body()).decode())
    template = templates.get_template("components.html")
    html = template.render_block(
        "preview",
        title=form.get("title", [""])[0],
        summary=form.get("summary", [""])[0],
    )
    return HTMLResponse(html)
```

Parsing this small URL-encoded form directly keeps `python-multipart` out of
the example. Applications that already use FastAPI's form dependency can use
`Form()` parameters instead.

### 3. Create the typed component

Save this as `templates/components.html`:

```kida
{% def panel(title: str) %}
<section class="panel">
  <h1>{{ title }}</h1>
  {% slot %}
</section>
{% enddef %}

{% def text_field(name: str, label: str, value: str = "") %}
<label>
  {{ label }}
  <input name="{{ name }}" value="{{ value }}">
</label>
{% enddef %}

{% block form %}
{% call panel("Component form") %}
<form method="post" action="/preview">
  {{ text_field("title", "Title", title) }}
  {{ text_field("summary", "Summary", summary) }}
  <button type="submit">Preview</button>
</form>
{% endcall %}
{% endblock %}

{% block preview %}
<article id="preview">
  <h2>{{ title }}</h2>
  <p>{{ summary }}</p>
</article>
{% endblock %}
```

Kida checks each component call against its typed `def` signature. The full
endpoint and fragment endpoint share compilation and autoescaping; the latter
returns only `preview` for HTMX, Turbo, or another HTML-over-the-wire client.

### 4. Run it

```bash
uv run uvicorn app:app --reload
```

The repository includes a runnable, smoke-tested version at
[`examples/fastapi_components`](https://github.com/lbliii/kida/tree/main/examples/fastapi_components).

## Use the adapter with Starlette

The same adapter works directly with Starlette:

```python
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route

from kida.contrib.starlette import KidaTemplates

templates = KidaTemplates(directory="templates")


async def home(request: Request):
    return templates.TemplateResponse(
        request,
        "components.html",
        {"title": "First component", "summary": "Edit me"},
    )


app = Starlette(routes=[Route("/", home)])
```

`KidaTemplates` accepts either `directory=`, or a preconfigured `env=`. It can
also accept `context_processors`, whose callables receive the request and
return context mappings. `TemplateResponse()` adds the request to context and
supports `status_code`, `headers`, and `media_type`.

## Async and streaming templates

`TemplateResponse()` renders ordinary templates synchronously. For templates
that contain `{% async for %}` or `{{ await }}`, use Kida's async stream API:

```python
from starlette.responses import StreamingResponse


@app.get("/feed")
async def feed(request: Request):
    template = templates.get_template("feed.html")

    async def chunks():
        async for chunk in template.render_stream_async(
            items=await get_items(),
            request=request,
        ):
            yield chunk

    return StreamingResponse(chunks(), media_type="text/html")
```

Templates can use `{% flush %}` to choose stream boundaries. For a single
async block, use `render_block_stream_async()`.

## HTMX request metadata

`TemplateResponse()` records `HX-Request`, `HX-Target`, `HX-Trigger`, and
`HX-Boosted` in Kida's render context as `hx_request`, `hx_target`,
`hx_trigger`, and `hx_boosted`. Framework code can combine that metadata with
`render_block()` while keeping render state request-local.

## Next steps

- [[docs/tutorials/flask-integration|Flask Integration]]
- [[docs/tutorials/django-integration|Django Integration]]
- [[docs/usage/framework-integration|Framework Integration APIs]]
- [[docs/usage/escaping|Escaping]]
