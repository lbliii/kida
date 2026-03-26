---
title: Content Security Policy
description: CSP nonce injection for inline scripts and styles in templates
draft: false
weight: 52
lang: en
type: doc
tags:
  - advanced
  - security
  - csp
keywords:
  - CSP
  - Content Security Policy
  - nonce
  - inline scripts
  - security
icon: shield
---

# Content Security Policy

Kida provides built-in CSP nonce injection for inline `<script>` and `<style>` tags. Nonces are automatically added to tags that don't already have one, keeping your templates compliant with strict Content Security Policy headers.

## Quick Start

There are three ways to inject CSP nonces into rendered HTML:

1. **Standalone function** -- post-process any HTML string
2. **Template filter** -- apply nonces inside a template
3. **RenderContext metadata** -- set a nonce once, read it anywhere during rendering

```python
from kida.utils.csp import inject_csp_nonce

html = '<script>alert("hi")</script>'
safe = inject_csp_nonce(html, "abc123")
# '<script nonce="abc123">alert("hi")</script>'
```

## `inject_csp_nonce()`

The core function. It scans HTML for opening `<script>` and `<style>` tags (case-insensitive) and inserts a `nonce="..."` attribute on every tag that doesn't already have one.

```python
from kida.utils.csp import inject_csp_nonce

inject_csp_nonce('<script>x</script>', 'r4nd0m')
# '<script nonce="r4nd0m">x</script>'

# Tags that already have a nonce are left alone
inject_csp_nonce('<script nonce="old">x</script>', 'new')
# '<script nonce="old">x</script>'

# Works on <style> tags too
inject_csp_nonce('<style>.red{color:red}</style>', 'r4nd0m')
# '<style nonce="r4nd0m">.red{color:red}</style>'
```

The nonce value is HTML-escaped before insertion. If the input is a `Markup` instance, the return value is also `Markup` so autoescaped templates won't double-escape the result.

An empty or `None` nonce is a no-op -- the HTML is returned unchanged.

## `csp_nonce` Filter

Use the `csp_nonce` filter inside templates to inject nonces into a block of HTML content.

```kida
{{ content | csp_nonce }}
{{ content | csp_nonce("explicit-nonce-value") }}
```

When called without an argument, the filter reads the nonce from the current RenderContext metadata (key `csp_nonce`). This lets you set the nonce once at the framework level and have every template pick it up automatically.

The filter always returns `Markup`, so the result is safe for autoescaped templates.

## `csp_nonce()` Global

A template global that returns the current nonce string from RenderContext metadata. Use it to manually add nonces to individual tags:

```kida
<script nonce="{{ csp_nonce() }}">
    // inline script
</script>
```

Returns an empty string if no nonce has been set.

## Framework Integration

### Setting the Nonce via RenderContext

In any framework, you can set the CSP nonce on the RenderContext so that filters and globals pick it up automatically:

```python
from kida.render_context import render_context

with render_context() as ctx:
    ctx.set_meta("csp_nonce", nonce_value)
    html = template.render(**data)
# All <script> and <style> tags now have nonce attributes
```

### Flask Example

```python
import secrets
from flask import Flask, make_response
from kida.contrib.flask import init_kida
from kida.render_context import render_context

app = Flask(__name__)
kida_env = init_kida(app)

@app.route("/")
def home():
    nonce = secrets.token_urlsafe(16)
    template = kida_env.get_template("home.html")

    with render_context() as ctx:
        ctx.set_meta("csp_nonce", nonce)
        html = template.render(title="Home")

    response = make_response(html)
    response.headers["Content-Security-Policy"] = (
        f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'"
    )
    return response
```

### Django Example

```python
import secrets
from django.http import HttpResponse
from kida.render_context import render_context

def home(request):
    nonce = secrets.token_urlsafe(16)
    from django.template import loader
    template = loader.get_template("home.html")

    with render_context() as ctx:
        ctx.set_meta("csp_nonce", nonce)
        html = template.render({"title": "Home"}, request)

    response = HttpResponse(html)
    response["Content-Security-Policy"] = (
        f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'"
    )
    return response
```

### Starlette / FastAPI Example

```python
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from kida.contrib.starlette import KidaTemplates
from kida.render_context import render_context

app = FastAPI()
templates = KidaTemplates(directory="templates")

@app.get("/")
async def home(request: Request):
    nonce = secrets.token_urlsafe(16)
    template = templates.get_template("home.html")

    with render_context() as ctx:
        ctx.set_meta("csp_nonce", nonce)
        html = template.render(title="Home", request=request)

    return HTMLResponse(
        content=html,
        headers={
            "Content-Security-Policy": (
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'"
            )
        },
    )
```

## See Also

- [[docs/advanced/security|Security]] -- Sandboxing and autoescape
- [[docs/tutorials/flask-integration|Flask Integration]] -- Full Flask setup
- [[docs/tutorials/django-integration|Django Integration]] -- Full Django setup
- [[docs/tutorials/starlette-integration|Starlette & FastAPI Integration]] -- Full Starlette/FastAPI setup
