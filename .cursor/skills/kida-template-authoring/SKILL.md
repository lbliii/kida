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

| Keyword | Scope |
|---------|-------|
| `{% set x = ... %}` | Current scope |
| `{% let x = ... %}` | Block-local, does not leak |
| `{% export x = ... %}` | Exports to parent scope |

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

All blocks use unified `{% end %}` — no `{% endif %}`, `{% endfor %}`, `{% endblock %}`.

## Best Practices

- Use descriptive block names: `page_title`, `sidebar_navigation`
- Provide defaults in base templates
- Use `| default()` for optional variables
- Use `~` for dynamic URL/path building: `hx-post="{{ '/chains/' ~ chain_id ~ '/add-step' }}"`
- Blocks cannot be defined inside loops — use `{% def %}` functions instead
- **Macro vs context variable naming**: Use verb-prefixed names for imported macros (`render_route_tabs`, `format_date`) and noun-like names for context variables (`route_tabs`, `items`). Same-name collisions cause the macro to shadow the variable, leading to "Cannot iterate over macro" when the variable is missing.
