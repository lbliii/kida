---
title: Includes
description: Include partial templates and components
draft: false
weight: 60
lang: en
type: doc
tags:
- syntax
- includes
keywords:
- include
- partials
- components
icon: file-plus
---

# Includes

Include reusable template fragments (partials) in your templates.

## Basic Include

```kida
{% include "partials/header.html" %}

<main>
    Content here
</main>

{% include "partials/footer.html" %}
```

## Context Inheritance

Included templates have access to the current context:

```kida
{# page.html #}
{% set user = get_current_user() %}
{% include "partials/user-card.html" %}
```

```kida
{# partials/user-card.html #}
<div class="user-card">
    <h3>{{ user.name }}</h3>
    <p>{{ user.email }}</p>
</div>
```

## Passing Variables

Pass specific variables with `with`:

```kida
{% include "components/button.html" with text="Click Me", url="/action" %}
```

```kida
{# components/button.html #}
<a href="{{ url }}" class="button">{{ text }}</a>
```

## Isolated Context

Use `only` to include with an empty context:

```kida
{% include "components/widget.html" with title="Widget" only %}
```

The included template only sees `title`, not the parent context.

## Ignore Missing

Skip if the template doesn't exist:

```kida
{% include "optional/sidebar.html" ignore missing %}
```

With fallback:

```kida
{% include ["theme/header.html", "default/header.html"] %}
```

Kida tries each template in order, using the first one found.

## Dynamic Includes

Include based on a variable:

```kida
{% include component_name %}

{# Or with string concatenation #}
{% include "components/" + widget_type + ".html" %}
```

## Include vs Extends

| Aspect | `{% include %}` | `{% extends %}` |
|--------|-----------------|-----------------|
| Purpose | Embed a fragment | Inherit structure |
| Context | Shares parent context | Isolated |
| Blocks | Cannot override blocks | Overrides blocks |
| Use case | Components, partials | Page layouts |

## Common Patterns

### Component Library

```
templates/
├── components/
│   ├── button.html
│   ├── card.html
│   ├── modal.html
│   └── nav.html
└── pages/
    └── home.html
```

```kida
{# pages/home.html #}
{% include "components/nav.html" %}

<main>
    {% for item in items %}
        {% include "components/card.html" with item=item %}
    {% end %}
</main>
```

### Conditional Includes

```kida
{% if user.is_admin %}
    {% include "admin/toolbar.html" %}
{% end %}

{% if show_sidebar %}
    {% include "partials/sidebar.html" %}
{% end %}
```

### Loop Includes

```kida
{% for post in posts %}
    {% include "partials/post-card.html" with post=post %}
{% end %}
```

## Performance

Included templates are cached just like regular templates. The compilation cost is paid once, then reused.

```python
# Templates are compiled once and cached
env = Environment(loader=FileSystemLoader("templates/"))
env.cache_info()  # Shows template cache stats
```

## See Also

- [[docs/syntax/inheritance|Inheritance]] — Template inheritance
- [[docs/syntax/functions|Functions]] — Reusable functions
- [[docs/usage/loading-templates|Loading Templates]] — Template loaders
