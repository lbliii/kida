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
- choice
- prefix
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

## ChoiceLoader

Try multiple loaders in order, returning the first match. Useful for theme fallback patterns:

```python
from kida import Environment, FileSystemLoader, ChoiceLoader

loader = ChoiceLoader([
    FileSystemLoader("themes/custom/"),
    FileSystemLoader("themes/default/"),
])

env = Environment(loader=loader)

# Looks in custom/ first, then falls back to default/
template = env.get_template("page.html")
```

You can mix loader types:

```python
loader = ChoiceLoader([
    DictLoader({"override.html": "<p>In-memory override</p>"}),
    FileSystemLoader("templates/"),
])
```

## PrefixLoader

Namespace templates by prefix, delegating to per-prefix loaders. Useful for plugin and multi-app architectures:

```python
from kida import Environment, FileSystemLoader, PrefixLoader

loader = PrefixLoader({
    "app": FileSystemLoader("templates/app/"),
    "admin": FileSystemLoader("templates/admin/"),
    "shared": DictLoader({"header.html": "<header>Shared</header>"}),
})

env = Environment(loader=loader)

# Routes by prefix (delimiter is "/")
env.get_template("app/index.html")      # → templates/app/index.html
env.get_template("admin/users.html")    # → templates/admin/users.html
env.get_template("shared/header.html")  # → DictLoader
```

Custom delimiter:

```python
loader = PrefixLoader({"app": loader1, "admin": loader2}, delimiter=":")
env.get_template("app:index.html")
```

## PackageLoader

Load templates from an installed Python package. Uses `importlib.resources` so templates are found regardless of installation path (pip, editable installs, zipped eggs):

```python
from kida import Environment, PackageLoader

# Package structure:
# my_app/
#   __init__.py
#   templates/
#     base.html
#     pages/
#       index.html

loader = PackageLoader("my_app", "templates")
env = Environment(loader=loader)

template = env.get_template("base.html")
template = env.get_template("pages/index.html")
```

Useful for:

- Framework default templates (admin, error pages)
- Distributable themes (`pip install my-theme`)
- Plugin templates namespaced by package

Combine with `ChoiceLoader` to allow user overrides:

```python
from kida import ChoiceLoader, FileSystemLoader, PackageLoader

loader = ChoiceLoader([
    FileSystemLoader("templates/"),           # User overrides (checked first)
    PackageLoader("my_framework", "defaults"), # Framework defaults (fallback)
])
```

## FunctionLoader

Wrap any callable as a loader. The simplest way to create a custom loading strategy:

```python
from kida import Environment, FunctionLoader

def load(name):
    if name == "greeting.html":
        return "Hello, {{ name }}!"
    return None  # Not found

env = Environment(loader=FunctionLoader(load))
template = env.get_template("greeting.html")
```

The function can return:

- `str` — Template source (filename defaults to `"<function>"`)
- `tuple[str, str | None]` — `(source, filename)` for custom error messages
- `None` — Template not found (raises `TemplateNotFoundError`)

```python
# With custom filename for better error messages
def load_from_cms(name):
    source = cms_client.get_template(name)
    if source:
        return source, f"cms://{name}"
    return None

env = Environment(loader=FunctionLoader(load_from_cms))
```

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
