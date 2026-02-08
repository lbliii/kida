---
title: Quickstart
description: Render your first Kida template in 2 minutes
draft: false
weight: 20
lang: en
type: doc
tags:
- quickstart
- tutorial
keywords:
- quickstart
- first template
- tutorial
icon: zap
---

# Quickstart

Render your first Kida template in 2 minutes.

## Prerequisites

- Python 3.14+
- Kida installed (`pip install kida-templates`)

## Step 1: Create a Template

Create `templates/hello.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
</head>
<body>
    <h1>Hello, {{ name }}!</h1>

    {% if items %}
    <ul>
        {% for item in items %}
        <li>{{ item }}</li>
        {% end %}
    </ul>
    {% end %}
</body>
</html>
```

Note: Kida uses unified `{% end %}` to close all blocks.

## Step 2: Render the Template

Create `render.py`:

```python
from kida import Environment, FileSystemLoader

# Create environment with template directory
env = Environment(loader=FileSystemLoader("templates/"))

# Load and render the template
template = env.get_template("hello.html")
html = template.render(
    title="My Page",
    name="World",
    items=["Apple", "Banana", "Cherry"]
)

print(html)
```

## Step 3: Run It

```bash
python render.py
```

Output:

```html
<!DOCTYPE html>
<html>
<head>
    <title>My Page</title>
</head>
<body>
    <h1>Hello, World!</h1>

    <ul>
        <li>Apple</li>
        <li>Banana</li>
        <li>Cherry</li>
    </ul>
</body>
</html>
```

## Key Concepts

| Concept | Syntax | Example |
|---------|--------|---------|
| Output | `{{ expr }}` | `{{ name }}` |
| Control | `{% tag %}` | `{% if %}`, `{% for %}` |
| Block end | `{% end %}` | Closes any block |
| Comments | `{# text #}` | `{# ignore me #}` |
| Filters | `\| filter` | `{{ name \| upper }}` |
| Pipeline | `\|> filter` | `{{ title \|> escape \|> upper }}` |
| Pattern match | `{% match %}` | `{% match status %}{% case "ok" %}...{% end %}` |

## Next Steps

:::{cards}
:columns: 1-2-3
:gap: medium

:::{card} First Project
:icon: package
:link: ./first-project
:description: Build something real
Template inheritance, filters, and multi-page rendering.
:::{/card}

:::{card} Syntax Guide
:icon: code
:link: ../syntax/
:description: Variables, control flow, filters
Learn the template language from basics to advanced.
:::{/card}

:::{card} Streaming
:icon: zap
:link: ../usage/streaming
:description: Chunked rendering for HTMX and SSE
Yield HTML chunks as they render for progressive delivery.
:::{/card}

:::{/cards}
