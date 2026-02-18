---
title: Custom Globals
description: Add global functions and variables
draft: false
weight: 30
lang: en
type: doc
tags:
- extending
- globals
keywords:
- custom globals
- extending
- functions
icon: globe
---

# Custom Globals

Globals are available in all templates without explicit passing.

## Add Variables

```python
from kida import Environment

env = Environment()

env.add_global("site_name", "My Site")
env.add_global("current_year", 2026)
env.add_global("debug_mode", False)
```

Template usage:

```kida
<title>{{ site_name }}</title>
<footer>&copy; {{ current_year }}</footer>
```

## Add Functions

```python
from datetime import datetime

def now():
    return datetime.now()

def format_date(dt, pattern="%Y-%m-%d"):
    return dt.strftime(pattern)

env.add_global("now", now)
env.add_global("format_date", format_date)
```

Template usage:

```kida
<p>Generated: {{ format_date(now()) }}</p>
<p>Today: {{ format_date(now(), "%B %d, %Y") }}</p>
```

## Add Classes

```python
from collections import namedtuple

# Make types available
env.add_global("Counter", Counter)
env.add_global("namedtuple", namedtuple)
```

## Built-in Globals

Kida includes common Python builtins:

- `range`, `len`, `str`, `int`, `float`, `bool`
- `dict`, `list`, `set`, `tuple`
- `abs`, `min`, `max`, `sum`
- `sorted`, `reversed`, `enumerate`, `zip`
- `map`, `filter`

## HTMX Helpers

Kida includes optional HTMX helpers for partial rendering and form security. When `enable_htmx_helpers=True` (default), these functions are available in all templates:

| Function | Returns | Description |
|----------|---------|-------------|
| `hx_request()` | `bool` | True if the request is from HTMX |
| `hx_target()` | `str \| None` | HTMX target element ID from HX-Target header |
| `hx_trigger()` | `str \| None` | Element ID that triggered the request |
| `hx_boosted()` | `bool` | True if request came from hx-boost="true" |
| `csrf_token()` | `Markup` | Hidden input with CSRF token for forms |

### Framework Integration

Frameworks must set metadata via `render_context().set_meta()` before rendering:

```python
from kida import Environment, render_context

with render_context() as ctx:
    ctx.set_meta("hx_request", request.headers.get("HX-Request") == "true")
    ctx.set_meta("hx_target", request.headers.get("HX-Target"))
    ctx.set_meta("csrf_token", session.generate_csrf_token())

    html = template.render(**data)
```

### Template Usage

```kida
{% if hx_request() %}
    {# Partial render — just the updated component #}
    {% block content %}...{% end %}
{% else %}
    {# Full page render #}
    {% extends "base.html" %}
{% end %}

<form method="POST">
    {{ csrf_token() }}
    ...
</form>
```

Disable HTMX helpers with `Environment(enable_htmx_helpers=False)`.

## Islands Helper Globals

For server-rendered apps that mount isolated high-state widgets, frameworks can
register helper globals that generate safe island mount attributes.

```python
import html
import json
from kida import Environment

env = Environment()

def island_attrs(name: str, props: dict, mount_id: str) -> str:
    payload = html.escape(json.dumps(props, separators=(",", ":")), quote=True)
    return (
        f' data-island="{html.escape(name, quote=True)}"'
        f' data-island-version="1"'
        f' id="{html.escape(mount_id, quote=True)}"'
        f' data-island-props="{payload}"'
    )

env.add_global("island_attrs", island_attrs)
```

Template usage:

```kida
<div{{ island_attrs("editor", {"doc_id": doc.id}, "editor-root") }}>
    <p>Fallback editor UI (SSR) if JS is unavailable.</p>
</div>
```

## Auth Template Safety

For authentication views, keep template globals minimal and avoid exposing
raw request/session objects.

```python
from kida import render_context

with render_context() as ctx:
    ctx.set_meta("csrf_token", csrf_token_value)
    # Provide only explicit, safe values to templates.
    html = template.render(current_user=user, next_url=safe_next_url)
```

Guidelines:

- Keep `autoescape=True` (default).
- Prefer explicit values (`current_user`, IDs, flags) over full framework objects.
- Use CSRF helpers from render metadata (`csrf_token`) instead of hand-rolled fields.
- Treat `Markup` as trusted-only output.

## Common Patterns

### Site Configuration

```python
site_config = {
    "name": "My Site",
    "url": "https://example.com",
    "author": "Jane Doe",
}

env.add_global("site", site_config)
```

```kida
<a href="{{ site.url }}">{{ site.name }}</a>
<meta name="author" content="{{ site.author }}">
```

### Utility Functions

```python
import json
from urllib.parse import urlencode

env.add_global("json_encode", json.dumps)
env.add_global("urlencode", urlencode)
```

```kida
<script>const data = {{ json_encode(config) }};</script>
<a href="/search?{{ urlencode(params) }}">Search</a>
```

### Feature Flags

```python
features = {
    "dark_mode": True,
    "beta_features": False,
    "analytics": True,
}

env.add_global("features", features)
```

```kida
{% if features.dark_mode %}
    <link rel="stylesheet" href="/css/dark.css">
{% end %}

{% if features.analytics %}
    {% include "analytics.html" %}
{% end %}
```

### Request Context (Web)

```python
def get_request_context(request):
    return {
        "user": request.user,
        "path": request.path,
        "is_authenticated": request.user.is_authenticated,
    }

# Per-request globals
env.add_global("request", get_request_context(request))
```

### Translation Function

```python
import gettext

def _(text):
    return translations.gettext(text)

env.add_global("_", _)
env.add_global("gettext", _)
```

```kida
<h1>{{ _("Welcome") }}</h1>
<p>{{ _("Hello, {}!").format(user.name) }}</p>
```

## Dynamic Globals

For per-request values, update globals before rendering:

```python
def render_with_context(template_name, **context):
    # Add request-specific globals
    env.add_global("current_user", get_current_user())
    env.add_global("csrf_token", generate_csrf())

    return env.render(template_name, **context)
```

## Object as Namespace

Group related globals:

```python
class Helpers:
    @staticmethod
    def format_date(dt, pattern="%Y-%m-%d"):
        return dt.strftime(pattern)

    @staticmethod
    def truncate(text, length=100):
        if len(text) <= length:
            return text
        return text[:length] + "..."

env.add_global("helpers", Helpers)
```

```kida
{{ helpers.format_date(post.date) }}
{{ helpers.truncate(post.content, 200) }}
```

## Best Practices

### Immutable Configuration

```python
# ✅ Configuration object
env.add_global("config", frozendict(settings))

# ❌ Mutable global
env.add_global("settings", mutable_dict)
```

### Clear Naming

```python
# ✅ Descriptive names
env.add_global("site_config", config)
env.add_global("format_currency", format_money)

# ❌ Vague names
env.add_global("c", config)
env.add_global("f", format_money)
```

### Avoid Side Effects

```python
# ✅ Pure function
env.add_global("add", lambda a, b: a + b)

# ❌ Function with side effects
def log_and_add(a, b):
    print(f"Adding {a} + {b}")  # Side effect
    return a + b
```

## See Also

- [[docs/usage/rendering-contexts|Rendering Contexts]] — Pass variables to templates
- [[docs/extending/custom-filters|Custom Filters]] — Transform values
- [[docs/reference/api|API Reference]] — Environment.add_global()
