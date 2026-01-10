---
title: Template Not Found
description: Fix template loading errors
draft: false
weight: 20
lang: en
type: doc
tags:
- troubleshooting
- errors
keywords:
- template
- not found
- error
- loader
icon: file-x
---

# Template Not Found

Fix `TemplateNotFoundError` exceptions.

## The Error

```
TemplateNotFoundError: Template 'bsae.html' not found in: templates/
```

## Common Causes

### 1. Typo in Template Name

```python
# ❌ Typo
env.get_template("bsae.html")

# ✅ Correct
env.get_template("base.html")
```

**Fix**: Check the template filename spelling.

### 2. Wrong Path

```python
# ❌ Wrong path
env.get_template("templates/page.html")

# ✅ Relative to loader root
env.get_template("page.html")
```

**Fix**: Paths are relative to the loader's search directories.

### 3. No Loader Configured

```python
# ❌ No loader
env = Environment()
env.get_template("page.html")  # Raises RuntimeError

# ✅ Configure loader
env = Environment(loader=FileSystemLoader("templates/"))
```

**Fix**: Always configure a loader for `get_template()`.

### 4. Wrong Search Directory

```python
# ❌ Wrong directory
loader = FileSystemLoader("template/")  # Missing 's'

# ✅ Correct directory
loader = FileSystemLoader("templates/")
```

**Fix**: Verify the directory path exists.

### 5. Extends/Include Path Error

```kida
{# ❌ Wrong path #}
{% extends "../base.html" %}

{# ✅ From loader root #}
{% extends "layouts/base.html" %}
```

**Fix**: Use paths relative to loader root, not current file.

## Solutions

### List Available Templates

```python
loader = FileSystemLoader("templates/")
print(loader.list_templates())
# ['base.html', 'pages/home.html', 'components/button.html']
```

### Use Absolute Paths

```python
from pathlib import Path

templates_dir = Path(__file__).parent / "templates"
loader = FileSystemLoader(templates_dir)
```

### Multiple Search Paths

```python
loader = FileSystemLoader([
    "templates/",         # Primary
    "shared/templates/",  # Fallback
])
```

### Debug Template Loading

```python
def load_template(name):
    try:
        return env.get_template(name)
    except TemplateNotFoundError:
        print(f"Template '{name}' not found")
        print(f"Search paths: {env.loader._paths}")
        print(f"Available: {env.loader.list_templates()}")
        raise
```

## Check File System

```bash
# Verify template exists
ls -la templates/

# Find templates
find . -name "*.html" -type f
```

## Common Patterns

### Project Structure

```
myproject/
├── app.py
└── templates/
    ├── base.html
    ├── layouts/
    │   └── sidebar.html
    └── pages/
        └── home.html
```

```python
# In app.py
loader = FileSystemLoader("templates/")
env.get_template("base.html")
env.get_template("layouts/sidebar.html")
env.get_template("pages/home.html")
```

### Package Templates

```python
from pathlib import Path
import mypackage

templates = Path(mypackage.__file__).parent / "templates"
loader = FileSystemLoader(templates)
```

## Prevention

### Validate on Startup

```python
def validate_templates():
    required = ["base.html", "error.html", "home.html"]
    for name in required:
        try:
            env.get_template(name)
        except TemplateNotFoundError:
            raise RuntimeError(f"Required template missing: {name}")

validate_templates()
```

### Use Constants

```python
class Templates:
    BASE = "base.html"
    HOME = "pages/home.html"
    ERROR = "error.html"

env.get_template(Templates.HOME)
```

## See Also

- [[docs/usage/loading-templates|Loading Templates]] — Loader configuration
- [[docs/extending/custom-loaders|Custom Loaders]] — Build custom loaders
- [[docs/usage/error-handling|Error Handling]] — Exception handling
