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

Included templates have access to the current context, including loop variables and block-scoped `{% set %}` variables:

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

### Loop Variables in Includes

Loop variables from `{% for %}` are visible inside included templates:

```kida
{# page.html #}
{% for item in items %}
    {% include "partials/item-card.html" %}
{% end %}
```

```kida
{# partials/item-card.html — item and loop are available #}
<div class="card">
    <span>{{ loop.index }}.</span>
    <h3>{{ item.name }}</h3>
</div>
```

This works for nested loops and tuple-unpacked variables too:

```kida
{% for key, value in entries %}
    {% include "partials/entry.html" %}
{% end %}
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

## Relative Paths

Resolve includes against the current template's directory with `./` and `../`:

```kida
{# pages/about.html #}
{% include "./_hero.html" %}           {# → pages/_hero.html #}
{% include "../shared/nav.html" %}     {# → shared/nav.html #}
```

Relative paths also work inside `{% extends %}`, `{% embed %}`, and `{% from ... import ... %}`. This lets you move a folder without touching any references inside it.

Absolute (root-relative) names like `"components/card.html"` keep working unchanged — relative resolution is purely additive.

Paths that walk above every loader search root raise `TemplateNotFoundError`. Relative names passed directly to `env.get_template()` from Python also raise — relative resolution only makes sense from inside a template.

## Namespace Aliases

For cross-cutting libraries that are not locality-bound — shared components, layouts — configure `template_aliases` on the `Environment` and reference them with an `@alias/` prefix:

```python
from kida import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader("templates/"),
    template_aliases={
        "components": "ui/components",
        "layouts": "ui/layouts",
    },
)
```

```kida
{# Any template, anywhere in the tree: #}
{% extends "@layouts/base.html" %}         {# → ui/layouts/base.html #}
{% include "@components/card.html" %}       {# → ui/components/card.html #}
{% from "@components/nav.html" import nav %}
{% embed "@layouts/shell.html" %}{% end %}
```

Aliases resolve before loader lookup, so the same `@components/` prefix works from any folder without the caller knowing the physical path. Unknown aliases raise `TemplateNotFoundError` and list the configured aliases.

Aliases and relative paths are separate resolution modes — aliases always resolve to an absolute root, so `@components/./foo` is not a composition, just a no-op `./` segment after substitution.

## Dynamic Includes

Include based on a variable:

```kida
{% include component_name %}

{# Or with string concatenation (+ is supported; ~ is the explicit coercing form) #}
{% include "components/" + widget_type + ".html" %}
{% include "components/" ~ widget_type ~ ".html" %}
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
        {% include "components/card.html" %}
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
    {% include "partials/post-card.html" %}
{% end %}
```

The loop variable `post` and `loop` context are automatically visible in the included template. You can still use `with` to pass additional variables if needed:

```kida
{% for post in posts %}
    {% include "partials/post-card.html" with show_date=True %}
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

- [[docs/tutorials/refactor-safe-templates|Refactor-Safe Templates]] — Tutorial on moving folders without breaking includes, using `./` / `../` and `@alias/` prefixes.
- [[docs/syntax/inheritance|Inheritance]] — Template inheritance
- [[docs/syntax/functions|Functions]] — Reusable functions
- [[docs/usage/loading-templates|Loading Templates]] — Template loaders
