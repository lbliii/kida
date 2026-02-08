---
title: Get Started
description: Install Kida and render your first template
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

## Render a Template

```python
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")
print(template.render(name="World"))
# Output: Hello, World!
```

## What's Next?

:::{cards}
:columns: 1-2-3
:gap: medium

:::{card} Quickstart
:icon: zap
:link: ./quickstart
:description: Complete walkthrough in 2 minutes
:badge: Start Here
Build and render your first file-based template.
:::{/card}

:::{card} First Project
:icon: package
:link: ./first-project
:description: Inheritance, filters, and multi-page rendering
Build a mini email template system with shared layouts.
:::{/card}

:::{card} Coming from Jinja2
:icon: arrow-right
:link: ./coming-from-jinja2
:description: Quick syntax cheat sheet
See what's the same, what's different, and what's new.
:::{/card}

:::{card} T-String Templates
:icon: type
:link: ./tstring-templates
:description: PEP 750 inline templates
Use Python 3.14 t-strings for auto-escaped HTML snippets.
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

## Quick Links

- [[docs/reference/api|API Reference]] — Environment, Template, Loaders
- [[docs/syntax/filters|Filters]] — All built-in filters
- [[docs/about/comparison|vs Jinja2]] — Feature comparison
- [[docs/tutorials/migrate-from-jinja2|Full Migration Guide]] — Step-by-step with verification
