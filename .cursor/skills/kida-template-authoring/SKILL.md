---
name: kida-template-authoring
description: Write correct Kida templates from scratch. Use when creating templates, writing views, or authoring template content.
---

# Kida Template Authoring

## Variables and Output

```kida
{{ name }}
{{ user.email }}
{{ items[0] }}
{{ user.nickname | default("Anonymous") }}
```

## Control Flow

### Conditionals

```kida
{% if user.is_admin %}
    <span class="badge">Admin</span>
{% elif user.is_moderator %}
    <span class="badge">Mod</span>
{% else %}
    <span class="badge">User</span>
{% end %}
```

Kida uses unified `{% end %}` to close all blocks. Explicit closers (`{% endif %}`, `{% endfor %}`, `{% endblock %}`) are also accepted for readability in deep nesting, but `{% end %}` is the canonical style.

### Loops

```kida
{% for item in items %}
    <li>{{ item.name }}</li>
{% else %}
    <li>No items found</li>
{% end %}
```

### Loop Context

```kida
{{ loop.index }}   {# 1-based #}
{{ loop.first }}
{{ loop.last }}
{{ loop.length }}
```

### Pattern Matching

```kida
{% match status %}
{% case "active" %}✓ Active
{% case "pending" %}⏳ Pending
{% case _ %}Unknown
{% end %}
```

## Scoping

| Keyword | Scope | Jinja2 equivalent |
|---------|-------|-------------------|
| `{% let x = ... %}` | Template-wide — visible everywhere after assignment | `{% set %}` at top level |
| `{% set x = ... %}` | Block-scoped — does NOT leak out of `{% if %}`, `{% for %}`, etc. | No equivalent |
| `{% export x = ... %}` | Promotes to template (outermost) scope from any depth | `namespace()` pattern |

> **Jinja2 trap:** In Jinja2, `{% set %}` inside a block modifies the outer variable.
> In Kida, `{% set %}` is block-scoped. Use `{% let %}` for template-wide variables.

## Inheritance

```kida
{# page.html #}
{% extends "base.html" %}

{% block title %}About - My Site{% end %}

{% block content %}
    <h2>About Us</h2>
    <p>{{ page.content }}</p>
{% end %}
```

- No `super()` — child blocks fully replace parent content
- Use explicit extension blocks: `{% block extra_head %}{% end %}` for add-to patterns

## Includes

```kida
{% include "partials/header.html" %}
{% include "partials/user-card.html" with user=current_user %}
```

## Components (def + call + slot)

Define reusable components with `{% def %}` and use them with `{% call %}`:

```kida
{% def card(title) %}
<div class="card">
    <h3>{{ title }}</h3>
    <div class="body">{{ caller() }}</div>
</div>
{% end %}

{% call card("Settings") %}
    <p>This becomes the card body (default slot).</p>
{% end %}
```

### Named Slots

Components can define multiple insertion points with named slots:

```kida
{% def modal(title) %}
<dialog>
    <h2>{{ title }}</h2>
    <div class="body">{% slot %}</div>
    <footer>{% slot footer %}<button>Close</button>{% end %}</footer>
</dialog>
{% end %}

{% call modal("Confirm") %}
    {% slot footer %}<button>Cancel</button> <button>OK</button>{% end %}
    <p>Are you sure?</p>
{% end %}
```

- `{% slot %}` in a `{% def %}` = default slot placeholder
- `{% slot name %}` in a `{% def %}` = named slot placeholder (with optional default content)
- `{% slot name %}...{% end %}` inside `{% call %}` = provides content for a named slot
- Bare content inside `{% call %}` = provides content for the default slot
- There is NO `{% fill %}` tag — always use `{% slot %}` inside `{% call %}`

### Importing Components

```kida
{% from "chirpui/modal.html" import modal %}
{% from "chirpui/button.html" import button %}

{% call modal("Delete Item") %}
    <p>This cannot be undone.</p>
    {% slot footer %}{{ button("Delete", variant="danger") }}{% end %}
{% end %}
```

### Slot Detection

Use `has_slot()` inside a def to conditionally render wrappers:

```kida
{% def card(title) %}
<div class="card">
    <h3>{{ title }}</h3>
    {% if has_slot() %}
        <div class="body">{{ caller() }}</div>
    {% end %}
</div>
{% end %}
```

## Block Rendering

```python
template.render_block("block_name", **ctx)  # Render single block for HTMX/partials
```

## Caching

```kida
{% cache "sidebar" %}
    {% for item in nav_items %}
        <a href="{{ item.url }}">{{ item.title }}</a>
    {% end %}
{% end %}

{% cache "user-" ~ user.id, ttl="5m" %}
    {{ render_profile(user) }}
{% end %}
```

## Filters

```kida
{{ title |> escape |> upper |> truncate(50) }}
{{ items | default([]) | length }}
{{ html_content | safe }}
```

## HTML Escaping

Output is escaped by default. Use `| safe` for trusted HTML.

## Block Endings

All blocks use unified `{% end %}`. Explicit closers (`{% endif %}`, `{% endfor %}`, `{% endblock %}`) are accepted but `{% end %}` is preferred.

## Best Practices

- Use descriptive block names: `page_title`, `sidebar_navigation`
- Provide defaults in base templates
- Use `| default()` for optional variables
- Use `~` for dynamic URL/path building: `hx-post="{{ '/chains/' ~ chain_id ~ '/add-step' }}"`
- Blocks cannot be defined inside loops — use `{% def %}` functions instead
- **Macro vs context variable naming**: Use verb-prefixed names for imported macros (`render_route_tabs`, `format_date`) and noun-like names for context variables (`route_tabs`, `items`). Same-name collisions cause the macro to shadow the variable, leading to "Cannot iterate over macro" when the variable is missing.
