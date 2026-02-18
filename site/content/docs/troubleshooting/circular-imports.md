---
title: Circular Imports
description: K-TPL-003 — Circular macro import detection
draft: false
weight: 20
lang: en
type: doc
tags:
- troubleshooting
- circular import
- macros
keywords:
- circular import
- K-TPL-003
- from import
- macros
category: troubleshooting
---

# Circular Imports

When using `{% from "template.html" import macro_name %}`, a template must not import from itself (directly or transitively). Kida detects this and raises `TemplateRuntimeError` with code `K-TPL-003` instead of hitting Python's recursion limit.

## The Error

```
TemplateRuntimeError: Circular import detected: 'showcase/_tab_content.html' imports itself (via showcase/_tab_content.html)
  Location: showcase/_tab_content.html:1
  Code: K-TPL-003
```

## Cause

A template has `{% from "X" import y %}` where X is the same template or leads back to it:

```kida
{# BAD: _tab_content.html imports from itself #}
{% from "showcase/_tab_content.html" import tab_section %}
{% def tab_section() %}content{% end %}
```

Or transitive: A imports B, B imports A.

## Fix

Split macros into a separate file and import from there:

```kida
{# _tab_section.html — macros only #}
{% def tab_section() %}content{% end %}
```

```kida
{# _tab_content.html — imports from sibling #}
{% from "showcase/_tab_section.html" import tab_section %}
{% block tab_content %}
  {{ tab_section() }}
{% end %}
```

## See Also

- [Functions and macros](../syntax/functions.md) — `{% def %}` and `{% from %}`
- [render_block and def scope](./render-block-scope.md) — Blocks do not inherit defs from the same template
