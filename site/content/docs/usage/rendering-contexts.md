---
title: Rendering Contexts
description: Passing variables and context to templates
draft: false
weight: 20
lang: en
type: doc
tags:
- usage
- contexts
keywords:
- context
- variables
- globals
- render
icon: settings
---

# Rendering Contexts

Pass data to templates through the rendering context.

## Basic Rendering

Pass variables as keyword arguments:

```python
template = env.get_template("page.html")
html = template.render(
    title="My Page",
    user=current_user,
    items=item_list,
)
```

Or as a dictionary:

```python
context = {
    "title": "My Page",
    "user": current_user,
    "items": item_list,
}
html = template.render(context)
```

## Convenience Methods

Environment provides shortcuts:

```python
# Combines get_template() + render()
html = env.render("page.html", title="Hello")

# Combines from_string() + render()
html = env.render_string("{{ x * 2 }}", x=21)
```

## Global Variables

Variables available in all templates:

```python
env = Environment(loader=FileSystemLoader("templates/"))

# Add globals
env.add_global("site_name", "My Site")
env.add_global("current_year", 2024)
env.add_global("format_date", format_date_func)
```

Access in templates:

```kida
<title>{{ site_name }}</title>
<footer>&copy; {{ current_year }}</footer>
{{ format_date(post.date) }}
```

### Built-in Globals

Kida includes common Python builtins:

```kida
{{ range(10) }}
{{ len(items) }}
{{ dict(a=1, b=2) }}
{{ max(scores) }}
```

Available: `range`, `dict`, `list`, `set`, `tuple`, `len`, `str`, `int`, `float`, `bool`, `abs`, `min`, `max`, `sum`, `sorted`, `reversed`, `enumerate`, `zip`, `map`, `filter`.

## Object Access

Templates access object attributes:

```python
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email

template.render(user=User("Alice", "alice@example.com"))
```

```kida
{{ user.name }}
{{ user.email }}
```

### Dictionary Access

```python
template.render(config={"timeout": 30, "retries": 3})
```

```kida
{{ config.timeout }}
{{ config["timeout"] }}
```

## Nested Contexts

Build complex nested data:

```python
template.render(
    site={
        "title": "My Site",
        "nav": [
            {"title": "Home", "url": "/"},
            {"title": "About", "url": "/about"},
        ],
    },
    page={
        "title": "Welcome",
        "content": "Hello, world!",
    },
)
```

```kida
<title>{{ page.title }} - {{ site.title }}</title>

<nav>
{% for item in site.nav %}
    <a href="{{ item.url }}">{{ item.title }}</a>
{% end %}
</nav>
```

## Undefined Variables

By default, undefined variables raise errors:

```python
template = env.from_string("{{ missing }}")
template.render()  # Raises UndefinedError
```

Use `default` filter for optional values:

```kida
{{ user.nickname | default("Anonymous") }}
{{ config.timeout | default(30) }}
```

## Context Isolation

Each `render()` call starts with a fresh context:

```python
# These don't affect each other
html1 = template.render(x=1)
html2 = template.render(x=2)
```

Globals are shared but render context is isolated.

## Best Practices

### Keep Context Flat

```python
# ✅ Flat, easy to access
template.render(
    title=page.title,
    user=current_user,
    items=items,
)

# ❌ Deeply nested
template.render(
    data={
        "page": {"meta": {"title": ...}},
        ...
    }
)
```

### Use Typed Objects

```python
# ✅ IDE support, validation
@dataclass
class PageContext:
    title: str
    user: User
    items: list[Item]

template.render(**asdict(PageContext(...)))
```

### Precompute in Python

```python
# ✅ Python handles complexity
template.render(
    formatted_items=[format_item(i) for i in items],
    total=sum(i.price for i in items),
)

# ❌ Complex logic in template
# {% set total = 0 %}
# {% for item in items %}{% set total = total + item.price %}{% end %}
```

## See Also

- [[docs/usage/escaping|Escaping]] — HTML escaping
- [[docs/extending/custom-globals|Custom Globals]] — Add global functions
- [[docs/reference/api|API Reference]] — Environment.render()

