---
title: Loading Templates
description: Template loaders and search paths
draft: false
weight: 10
lang: en
type: doc
tags:
- usage
- loaders
keywords:
- loaders
- filesystem
- dict
- loading
icon: folder
---

# Loading Templates

Kida provides several ways to load templates.

## FileSystemLoader

Load templates from filesystem directories:

```python
from kida import Environment, FileSystemLoader

# Single directory
env = Environment(loader=FileSystemLoader("templates/"))

# Multiple directories (searched in order)
env = Environment(loader=FileSystemLoader([
    "templates/",
    "shared/templates/",
]))

# Load a template
template = env.get_template("page.html")
template = env.get_template("components/button.html")
```

### Search Order

Directories are searched in order. First match wins:

```python
loader = FileSystemLoader([
    "themes/custom/",    # Checked first
    "themes/default/",   # Fallback
])
```

### List Templates

```python
loader = FileSystemLoader("templates/")
templates = loader.list_templates()
# ['base.html', 'components/card.html', 'pages/home.html']
```

## DictLoader

Load templates from an in-memory dictionary:

```python
from kida import Environment, DictLoader

loader = DictLoader({
    "base.html": "<html>{% block content %}{% end %}</html>",
    "page.html": "{% extends 'base.html' %}{% block content %}Hi{% end %}",
})

env = Environment(loader=loader)
template = env.get_template("page.html")
```

Useful for:

- Testing
- Embedded templates
- Dynamic template generation

## from_string()

Compile a template from a string (not cached):

```python
env = Environment()
template = env.from_string("Hello, {{ name }}!")
html = template.render(name="World")
```

## Custom Loaders

Implement the Loader protocol:

```python
from kida import Environment, TemplateNotFoundError

class DatabaseLoader:
    def __init__(self, connection):
        self.conn = connection

    def get_source(self, name: str) -> tuple[str, str | None]:
        """Return (source, filename) for template."""
        row = self.conn.execute(
            "SELECT source FROM templates WHERE name = ?", (name,)
        ).fetchone()

        if not row:
            raise TemplateNotFoundError(f"Template '{name}' not found")

        return row[0], f"db://{name}"

    def list_templates(self) -> list[str]:
        """Return all available template names."""
        rows = self.conn.execute("SELECT name FROM templates").fetchall()
        return sorted(row[0] for row in rows)

# Usage
env = Environment(loader=DatabaseLoader(db_connection))
```

## Template Caching

Templates are compiled once and cached:

```python
env = Environment(
    loader=FileSystemLoader("templates/"),
    cache_size=400,      # Max cached templates
    auto_reload=True,    # Check for source changes
)

# Check cache stats
info = env.cache_info()
print(info["template"])
# {'size': 5, 'max_size': 400, 'hits': 100, 'misses': 5}
```

### Auto-Reload

With `auto_reload=True` (default), Kida checks if template source changed:

```python
# Development: auto-reload enabled
env = Environment(auto_reload=True)

# Production: disable for performance
env = Environment(auto_reload=False)
```

### Clear Cache

```python
# Clear all templates
env.clear_template_cache()

# Clear specific templates
env.clear_template_cache(["base.html", "page.html"])
```

## Bytecode Cache

For cold-start performance, enable bytecode caching:

```python
from kida import Environment, FileSystemLoader
from kida.bytecode_cache import BytecodeCache

env = Environment(
    loader=FileSystemLoader("templates/"),
    bytecode_cache=BytecodeCache("__pycache__/kida/"),
)
```

Compiled bytecode is persisted to disk and loaded on subsequent runs.

## See Also

- [[docs/reference/api|API Reference]] — Environment, loaders
- [[docs/extending/custom-loaders|Custom Loaders]] — Build custom loaders
- [[docs/about/performance|Performance]] — Caching optimization
