---
title: Syntax
description: Kida template language syntax and features
draft: false
weight: 20
lang: en
type: doc
tags:
- syntax
- templates
keywords:
- syntax
- variables
- control flow
- filters
category: syntax
cascade:
  type: doc
icon: code
---

# Syntax

Kida's template syntax for expressions, control flow, and composition.

## Quick Reference

| Element | Syntax | Example |
|---------|--------|---------|
| Output | `{{ expr }}` | `{{ user.name }}` |
| Tags | `{% tag %}` | `{% if %}`, `{% for %}` |
| Block end | `{% end %}` | Unified ending |
| Comments | `{# text #}` | `{# TODO #}` |
| Filters | `\| filter` | `{{ name \| upper }}` |
| Pipeline | `\|> filter` | `{{ x \|> a \|> b }}` |

## Syntax Guide

:::{cards}
:columns: 2
:gap: medium

:::{card} Variables
:icon: variable
:link: /docs/syntax/variables/
:description: Output expressions and access patterns
`{{ name }}`, `{{ user.email }}`, `{{ items[0] }}`
:::{/card}

:::{card} Control Flow
:icon: git-branch
:link: /docs/syntax/control-flow/
:description: Conditionals, loops, and pattern matching
`{% if %}`, `{% for %}`, `{% match %}`
:::{/card}

:::{card} Filters
:icon: filter
:link: /docs/syntax/filters/
:description: Transform values in expressions
`{{ name | upper }}`, `{{ items | join(', ') }}`
:::{/card}

:::{card} Functions
:icon: function
:link: /docs/syntax/functions/
:description: Define reusable template functions
`{% def greet(name) %}`, `{% macro %}`
:::{/card}

:::{card} Inheritance
:icon: layers
:link: /docs/syntax/inheritance/
:description: Extend and override base templates
`{% extends %}`, `{% block %}`
:::{/card}

:::{card} Includes
:icon: file-plus
:link: /docs/syntax/includes/
:description: Include partials and components
`{% include %}`, context passing
:::{/card}

:::{card} Caching
:icon: database
:link: /docs/syntax/caching/
:description: Block-level output caching
`{% cache key %}...{% end %}`
:::{/card}

:::{card} Async
:icon: refresh-cw
:link: /docs/syntax/async/
:description: Async iteration and await
`async for`, `await`, async templates
:::{/card}

:::{/cards}

## Key Features

- **Unified `{% end %}`** — Clean, consistent block endings
- **Pattern matching** — `{% match status %}{% case "active" %}...{% end %}`
- **Pipeline operator** — `{{ title |> escape |> upper |> truncate(50) }}`
- **Built-in caching** — `{% cache "sidebar" %}...{% end %}`
