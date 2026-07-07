---
title: Get Started
description: Install Kida and render your first typed server-side component in pure Python
draft: false
weight: 10
lang: en
type: doc
tags:
- onboarding
- quickstart
keywords:
- getting started
- installation
- quickstart
- server-side components
- python components
- typed props
- named slots
- jinja2 alternative
category: onboarding
cascade:
  type: doc
icon: arrow-clockwise
---

# Get Started

## Install

```bash
pip install kida-templates
```

Requires Python 3.14 or later. See [[docs/get-started/installation|installation]] for alternative methods.

## Render a Typed Component

```python
from kida import Environment

env = Environment()
template = env.from_string("""
{% def badge(label: str) %}<strong>{{ label }}</strong>{% enddef %}
{{ badge("Ready") }}
""")
print(template.render().strip())
# Output: <strong>Ready</strong>
```

## What's Next?

:::{cards}
:columns: 1-2-3
:gap: medium

:::{card} Build Typed Components
:icon: layers
:link: /docs/usage/components/
:description: Defs, slots, and static validation
:badge: Start Here
Catch bad component props before rendering with `kida check --validate-calls`.
:::{/card}

:::{card} Component Comparison
:icon: sidebar
:link: /docs/tutorials/component-comparison/
:description: Kida components vs Jinja2 macros
See how typed props, named slots, and validation change composition.
:::{/card}

:::{card} Quickstart
:icon: zap
:link: /docs/get-started/quickstart/
:description: Complete walkthrough in 2 minutes
Build and render your first file-based template.
:::{/card}

:::{card} First Project
:icon: package
:link: /docs/get-started/first-project/
:description: Inheritance, filters, and multi-page rendering
Build a mini email template system with shared layouts.
:::{/card}

:::{card} Coming from Jinja2
:icon: arrow-right
:link: /docs/get-started/coming-from-jinja2/
:description: Quick syntax cheat sheet
See what's familiar, what changes, and what Kida adds beyond Jinja2.
:::{/card}

:::{card} T-String Templates
:icon: code
:link: /docs/get-started/tstring-templates/
:description: PEP 750 inline templates
Use Python 3.14 t-strings for auto-escaped HTML snippets.
:::{/card}

:::{card} Syntax Guide
:icon: code
:link: /docs/syntax/
:description: Variables, control flow, filters
Learn the template language from basics to advanced.
:::{/card}

:::{card} Tutorials
:icon: book-open
:link: /docs/tutorials/
:description: Step-by-step guides
Flask, Django, Starlette integration and more.
:::{/card}

:::{/cards}

## Quick Links

- [[docs/reference/api|API Reference]] — Environment, Template, Loaders
- [[docs/usage/components|Components]] — Typed props, slots, and validation
- [[docs/syntax/filters|Filters]] — All built-in filters
- [[docs/about/comparison|vs Jinja2]] — Feature comparison
- [[docs/tutorials/migrate-from-jinja2|Full Migration Guide]] — Step-by-step with verification
