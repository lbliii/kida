---
title: Usage
description: Build typed components, render them across surfaces, and integrate Kida into Python applications
draft: false
weight: 30
lang: en
type: doc
tags:
- usage
keywords:
- usage
- components
- typed props
- named slots
- rendering
- contexts
- streaming templates
- framework integration
category: usage
cascade:
  type: doc
icon: terminal
---

# Usage

Practical patterns for building and rendering Kida components in your applications.

:::{cards}
:columns: 2
:gap: medium

:::{card} Components
:icon: blocks
:link: /docs/usage/components/
:description: Typed props, named slots, scoped state, and validation
:::{/card}

:::{card} Framework Integration
:icon: puzzle
:link: /docs/usage/framework-integration/
:description: Bring Kida components to Python frameworks and static sites
:::{/card}

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

:::{card} Agent Message Protocol (AMP)
:icon: radio
:link: /docs/usage/amp/
:description: Structured AI agent output for multi-surface rendering
:::{/card}

:::{card} Agent Templates
:icon: layout
:link: /docs/usage/agent-templates/
:description: Built-in templates for code review, PR summary, deploy preview, and more
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
