---
title: Usage
description: Loading templates, rendering contexts, and error handling
draft: false
weight: 30
lang: en
type: doc
tags:
- usage
keywords:
- usage
- loading
- rendering
- contexts
category: usage
cascade:
  type: doc
icon: terminal
---

# Usage

Practical patterns for using Kida in your applications.

:::{cards}
:columns: 2
:gap: medium

:::{card} Loading Templates
:icon: folder
:link: /docs/usage/loading-templates/
:description: FileSystemLoader, DictLoader, search paths
:::{/card}

:::{card} Rendering Contexts
:icon: settings
:link: /docs/usage/rendering-contexts/
:description: Passing variables, globals, nested contexts
:::{/card}

:::{card} Streaming
:icon: zap
:link: /docs/usage/streaming/
:description: Chunked rendering, async streaming, framework integration
:::{/card}

:::{card} Escaping
:icon: shield
:link: /docs/usage/escaping/
:description: HTML escaping, Markup class, safe filter
:::{/card}

:::{card} Error Handling
:icon: alert-triangle
:link: /docs/usage/error-handling/
:description: Template errors, debugging, stack traces
:::{/card}

:::{/cards}

## Quick Reference

```python
from kida import Environment, FileSystemLoader

# Create environment
env = Environment(
    loader=FileSystemLoader("templates/"),
    autoescape=True,
)

# Load and render
template = env.get_template("page.html")
html = template.render(title="Hello", items=[1, 2, 3])

# Compile from string (not cached)
template = env.from_string("{{ name }}")
html = template.render(name="World")
```
