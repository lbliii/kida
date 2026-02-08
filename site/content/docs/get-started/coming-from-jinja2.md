---
title: Coming from Jinja2
description: Quick cheat sheet for Jinja2 users switching to Kida
draft: false
weight: 40
lang: en
type: doc
tags:
- migration
- jinja2
keywords:
- jinja2
- migration
- differences
- cheat sheet
icon: arrow-right
---

# Coming from Jinja2

A quick reference for Jinja2 users. For a full migration guide, see [[docs/tutorials/migrate-from-jinja2|Migrate from Jinja2]].

## What Stays the Same

Most Jinja2 syntax works in Kida unchanged:

```html
{{ variable }}
{{ user.name }}
{{ items | join(", ") }}
{% if condition %}...{% end %}
{% for item in items %}...{% end %}
{% extends "base.html" %}
{% block content %}...{% end %}
{% include "partial.html" %}
{# comments #}
```

## What's Different

### Block Endings

Jinja2 uses tag-specific endings. Kida uses a unified `{% end %}`:

```html
{# Jinja2 #}
{% if user %}...{% endif %}
{% for x in items %}...{% endfor %}
{% block nav %}...{% endblock %}

{# Kida #}
{% if user %}...{% end %}
{% for x in items %}...{% end %}
{% block nav %}...{% end %}
```

### Pipeline Operator

Kida adds `|>` for readable, left-to-right filter chains:

```html
{# Jinja2 — filters read right-to-left #}
{{ title | truncate(50) | upper | escape }}

{# Kida — pipeline reads left-to-right #}
{{ title |> escape |> upper |> truncate(50) }}
```

Both `|` and `|>` work in Kida. Use whichever you prefer.

### Pattern Matching

Kida adds `{% match %}` for cleaner branching (like Python's `match`):

```html
{# Jinja2 — chained if/elif #}
{% if status == "active" %}
    <span class="green">Active</span>
{% elif status == "pending" %}
    <span class="yellow">Pending</span>
{% elif status == "inactive" %}
    <span class="red">Inactive</span>
{% else %}
    <span>Unknown</span>
{% endif %}

{# Kida — pattern matching #}
{% match status %}
    {% case "active" %}<span class="green">Active</span>
    {% case "pending" %}<span class="yellow">Pending</span>
    {% case "inactive" %}<span class="red">Inactive</span>
    {% case _ %}<span>Unknown</span>
{% end %}
```

### Scoping Keywords

Kida provides explicit scoping for variable assignment:

```html
{# Jinja2 #}
{% set name = "Alice" %}

{# Kida — three scoping options #}
{% set name = "Alice" %}      {# Same as Jinja2: current scope #}
{% let name = "Alice" %}      {# Block-local: doesn't leak out #}
{% export name = "Alice" %}   {# Exports to parent scope #}
```

### Built-in Caching

Kida has native block-level caching (no extensions needed):

```html
{% cache "sidebar" %}
    {# Expensive rendering cached automatically #}
    {% for item in nav_items %}
        <a href="{{ item.url }}">{{ item.title }}</a>
    {% end %}
{% end %}
```

## API Comparison

| Operation | Jinja2 | Kida |
|-----------|--------|------|
| Create env | `jinja2.Environment()` | `kida.Environment()` |
| File loader | `jinja2.FileSystemLoader(...)` | `kida.FileSystemLoader(...)` |
| Dict loader | `jinja2.DictLoader(...)` | `kida.DictLoader(...)` |
| Load template | `env.get_template(name)` | `env.get_template(name)` |
| From string | `env.from_string(src)` | `env.from_string(src)` |
| Render | `template.render(**ctx)` | `template.render(**ctx)` |
| Add filter | `env.filters["name"] = fn` | `env.add_filter("name", fn)` |
| Add test | `env.tests["name"] = fn` | `env.add_test("name", fn)` |
| Stream render | `template.generate(**ctx)` | `template.render_stream(**ctx)` |
| Async render | N/A | `template.render_stream_async(**ctx)` |

## What Kida Adds

| Feature | Description |
|---------|-------------|
| Pipeline `\|>` | Left-to-right filter chains |
| `{% match %}` | Pattern matching for cleaner branching |
| `{% cache %}` | Built-in block-level output caching |
| `{% let %}` / `{% export %}` | Explicit variable scoping |
| Native async | `{% async for %}`, `{{ await expr }}` |
| Streaming | `render_stream()` yields chunks for HTMX/SSE |
| Free-threading | True parallelism on Python 3.14t |
| T-string tag | `k(t"Hello {name}!")` for inline templates |

## See Also

- [[docs/tutorials/migrate-from-jinja2|Full Migration Guide]] — Step-by-step with verification
- [[docs/about/comparison|Feature Comparison]] — Detailed feature matrix
- [[docs/about/thread-safety|Thread Safety]] — Free-threading deep dive
