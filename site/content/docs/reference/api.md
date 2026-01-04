---
title: API Reference
description: Core classes and methods
draft: false
weight: 10
lang: en
type: doc
tags:
- reference
- api
keywords:
- api
- environment
- template
- loaders
icon: code
---

# API Reference

## Environment

Central configuration and template management hub.

```python
from kida import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader("templates/"),
    autoescape=True,
)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `loader` | `Loader` | `None` | Template source provider |
| `autoescape` | `bool \| Callable` | `True` | HTML auto-escaping |
| `auto_reload` | `bool` | `True` | Check for source changes |
| `cache_size` | `int` | `400` | Max cached templates |
| `fragment_cache_size` | `int` | `1000` | Max cached fragments |
| `fragment_ttl` | `float` | `300.0` | Fragment TTL (seconds) |

### Methods

#### get_template(name)

Load and cache a template by name.

```python
template = env.get_template("page.html")
```

**Raises**: `TemplateNotFoundError`, `TemplateSyntaxError`

#### from_string(source, name=None)

Compile a template from string (not cached).

```python
template = env.from_string("Hello, {{ name }}!")
```

#### render(template_name, **context)

Load and render in one step.

```python
html = env.render("page.html", title="Hello", items=items)
```

#### render_string(source, **context)

Compile and render string in one step.

```python
html = env.render_string("{{ x * 2 }}", x=21)
```

#### add_filter(name, func)

Register a custom filter.

```python
env.add_filter("double", lambda x: x * 2)
```

#### add_test(name, func)

Register a custom test.

```python
env.add_test("even", lambda x: x % 2 == 0)
```

#### add_global(name, value)

Add a global variable.

```python
env.add_global("site_name", "My Site")
```

#### filter() (decorator)

Decorator to register a filter.

```python
@env.filter()
def double(value):
    return value * 2
```

#### test() (decorator)

Decorator to register a test.

```python
@env.test()
def is_even(value):
    return value % 2 == 0
```

#### cache_info()

Get cache statistics.

```python
info = env.cache_info()
# {'template': {...}, 'fragment': {...}}
```

#### clear_cache(include_bytecode=False)

Clear all caches.

```python
env.clear_cache()
```

---

## Template

Compiled template with render interface.

### Methods

#### render(**context)

Render template with context.

```python
html = template.render(name="World", items=[1, 2, 3])
```

#### render_async(**context)

Render template asynchronously.

```python
html = await template.render_async(items=async_generator())
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str \| None` | Template name |
| `filename` | `str \| None` | Source filename |

---

## Loaders

### FileSystemLoader

Load templates from filesystem directories.

```python
from kida import FileSystemLoader

# Single directory
loader = FileSystemLoader("templates/")

# Multiple directories (searched in order)
loader = FileSystemLoader(["templates/", "shared/"])
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `paths` | `str \| Path \| list` | Required | Search paths |
| `encoding` | `str` | `"utf-8"` | File encoding |

#### Methods

- `get_source(name)` → `tuple[str, str]`
- `list_templates()` → `list[str]`

### DictLoader

Load templates from a dictionary.

```python
from kida import DictLoader

loader = DictLoader({
    "base.html": "<html>{% block content %}{% end %}</html>",
    "page.html": "{% extends 'base.html' %}...",
})
```

---

## Exceptions

### TemplateError

Base class for all template errors.

### TemplateSyntaxError

Invalid template syntax.

```python
from kida import TemplateSyntaxError

try:
    env.from_string("{% if x %}")  # Missing end
except TemplateSyntaxError as e:
    print(e)
```

### TemplateNotFoundError

Template file not found.

```python
from kida import TemplateNotFoundError

try:
    env.get_template("nonexistent.html")
except TemplateNotFoundError as e:
    print(e)
```

### UndefinedError

Accessing undefined variable.

```python
from kida import UndefinedError

try:
    env.from_string("{{ missing }}").render()
except UndefinedError as e:
    print(e)
```

---

## Markup

HTML-safe string wrapper.

```python
from kida import Markup

# Create safe HTML
safe = Markup("<b>Bold</b>")

# Escape unsafe content
escaped = Markup.escape("<script>")
# &lt;script&gt;

# Format with escaping
result = Markup("<p>{}</p>").format(user_input)
```

### Class Methods

| Method | Description |
|--------|-------------|
| `escape(s)` | Escape string and return Markup |

### Operations

| Operation | Behavior |
|-----------|----------|
| `Markup + str` | str is escaped |
| `Markup + Markup` | Concatenated as-is |
| `Markup.format(...)` | Arguments are escaped |

---

## LoopContext

Available as `loop` variable inside for loops.

| Property | Type | Description |
|----------|------|-------------|
| `index` | `int` | 1-based index |
| `index0` | `int` | 0-based index |
| `first` | `bool` | True on first iteration |
| `last` | `bool` | True on last iteration |
| `length` | `int` | Total items |
| `revindex` | `int` | Reverse 1-based index |
| `revindex0` | `int` | Reverse 0-based index |

```kida
{% for item in items %}
    {{ loop.index }}/{{ loop.length }}
{% end %}
```

## See Also

- [[docs/reference/filters|Filters Reference]] — All built-in filters
- [[docs/reference/tests|Tests Reference]] — All built-in tests
- [[docs/reference/configuration|Configuration]] — All options

