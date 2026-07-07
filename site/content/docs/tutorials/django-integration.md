---
title: Django Integration
description: Add a typed Kida component and fragment view to Django in ten minutes
draft: false
weight: 25
lang: en
type: doc
tags:
  - tutorials
  - django
  - framework
keywords:
  - Django
  - typed components
  - fragment rendering
  - template backend
icon: globe
---

# Django Integration

Use Kida through Django's standard template-backend contract, then render a
named fragment from the same template. Kida requires **Python 3.14 or newer**.

> Migrating Jinja templates? Read [[docs/get-started/coming-from-jinja2|Coming
> from Jinja2]]. Kida's `{% set %}` is block-scoped, so values do not leak out
> of loops or other blocks.

## 1. Install

```bash
uv add django kida-templates
```

## 2. Configure the backend

Add Kida to `TEMPLATES` in `settings.py`:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES = [
    {
        "NAME": "kida",
        "BACKEND": "kida.contrib.django.KidaTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {"autoescape": True},
    },
]
```

`NAME` makes the backend easy to select explicitly when an application uses
more than one template engine.

## 3. Add full-page and fragment views

```python
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.template import engines


def home(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "components.html",
        {
            "title": "First component",
            "summary": "Edit me",
            "csrf_token": get_token(request),
        },
        using="kida",
    )


def preview(request: HttpRequest) -> HttpResponse:
    template = engines["kida"].env.get_template("components.html")
    html = template.render_block(
        "preview",
        title=request.POST.get("title", ""),
        summary=request.POST.get("summary", ""),
    )
    return HttpResponse(html)
```

Wire the views normally:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home),
    path("preview", views.preview),
]
```

The backend wrapper supports Django's normal `render()` path and supplies the
request in template context. Accessing `backend.env` is the supported route to
Kida-specific APIs such as `render_block()`.

## 4. Create the typed component

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
  <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
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

Kida validates component calls against their typed signatures. The full view
and fragment view share compilation and escaping behavior; the fragment route
returns only `preview` for HTMX, Turbo, or a similar client.

## 5. Run it

```bash
uv run python manage.py runserver
```

The repository includes a minimal, smoke-tested Django configuration at
[`examples/django_components`](https://github.com/lbliii/kida/tree/main/examples/django_components).

## Register filters and globals

Use the named backend from application startup code:

```python
from django.template import engines

env = engines["kida"].env


@env.filter()
def currency(value: float) -> str:
    return f"${value:,.2f}"


env.add_global("SITE_NAME", "My Django Site")
```

## Next steps

- [[docs/tutorials/flask-integration|Flask Integration]]
- [[docs/tutorials/starlette-integration|Starlette & FastAPI Integration]]
- [[docs/usage/escaping|Escaping]]
- [[docs/extending/custom-filters|Custom Filters]]
