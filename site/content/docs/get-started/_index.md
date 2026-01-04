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
pip install kida
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

:::{card} Syntax Guide
:icon: code
:link: ../syntax/
:description: Variables, control flow, filters
Learn the template language from basics to advanced.
:::{/card}

:::{card} Migration
:icon: arrow-right
:link: ../tutorials/migrate-from-jinja2
:description: Coming from Jinja2?
Step-by-step migration with API mapping.
:::{/card}

:::{/cards}

## Quick Links

- [[docs/reference/api|API Reference]] — Environment, Template, Loaders
- [[docs/syntax/filters|Filters]] — All built-in filters
- [[docs/about/comparison|vs Jinja2]] — Feature comparison

