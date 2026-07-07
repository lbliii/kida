---
title: Flask Integration
description: Add a typed Kida component and fragment route to Flask in ten minutes
draft: false
weight: 20
lang: en
type: doc
tags:
- tutorial
- flask
- web
keywords:
- flask
- typed components
- fragment rendering
- integration
icon: globe
---

# Flask Integration

Add a typed Kida component, a form, and a fragment response to an existing
Flask application. Kida requires **Python 3.14 or newer**.

> Coming from Jinja2? Read [[docs/get-started/coming-from-jinja2|Coming from
> Jinja2]] first. In particular, Kida's `{% set %}` is block-scoped rather than
> leaking into its surrounding scope.

## 1. Install

```bash
uv add flask kida-templates
```

## 2. Register Kida and add two routes

`init_kida()` leaves Flask's Jinja environment intact and adds a separate Kida
environment at `app.extensions["kida"]` and `app.kida_env`.

```python
from flask import Flask, request

from kida.contrib.flask import init_kida, render_template

app = Flask(__name__)
kida_env = init_kida(app)


@app.get("/")
def home() -> str:
    return render_template(
        "components.html",
        title="First component",
        summary="Edit me",
    )


@app.post("/preview")
def preview() -> str:
    template = kida_env.get_template("components.html")
    return template.render_block(
        "preview",
        title=request.form.get("title", ""),
        summary=request.form.get("summary", ""),
    )
```

`render_template()` reads Kida from Flask's current application context. Pass
`template_folder=` to `init_kida()` to override `app.template_folder`, or pass
normal `Environment` options such as `cache_size=400`.

## 3. Create the typed component

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

The component call is checked against the typed `def` signature. The `/`
route renders the full template; `/preview` renders only the named block for
HTMX, Turbo, or another HTML-over-the-wire client. Both paths use the same
autoescaping rules.

## 4. Run it

```bash
uv run flask --app app run --debug
```

The repository includes a runnable, smoke-tested version at
[`examples/flask_components`](https://github.com/lbliii/kida/tree/main/examples/flask_components).

## Add filters and globals

Register application helpers on the environment returned by `init_kida()`:

```python
from flask import url_for

kida_env.add_global("url_for", url_for)


@kida_env.filter()
def currency(value: float) -> str:
    return f"${value:,.2f}"
```

## Production setup

Set `auto_reload=False` outside development and size the template cache for
your application:

```python
kida_env = init_kida(app, auto_reload=False, cache_size=400)
```

## Next steps

- [[docs/tutorials/django-integration|Django Integration]]
- [[docs/tutorials/starlette-integration|Starlette & FastAPI Integration]]
- [[docs/extending/custom-filters|Custom Filters]]
- [[docs/usage/escaping|Escaping]]
