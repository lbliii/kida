---
title: render_block and Def Scope
description: Blocks do not inherit defs from the same template
draft: false
weight: 15
lang: en
type: doc
tags:
- troubleshooting
- render_block
- def
- blocks
keywords:
- render_block
- def scope
- blocks
- region
category: troubleshooting
---

# render_block and Def Scope

When you call `template.render_block("block_name", context)`, the block is rendered in isolation. It does **not** have access to `{% def %}` macros defined in the same template.

**Inherited blocks**: `render_block()` resolves blocks through the inheritance chain. You can render parent-only blocks (e.g. `sidebar` from a base template) on a descendant template. Child overrides still win. See [Inheritance — render_block](/docs/syntax/inheritance/#render_block-and-inherited-blocks).

## The Problem

```kida
{# page.html — def and block in same file #}
{% def helper() %}shared logic{% end %}

{% block content %}
  {{ helper() }}  {# NameError or UndefinedError when using render_block #}
{% end %}
```

If a framework (e.g. Chirp) calls `template.render_block("content", ...)`, the block cannot see `helper` because blocks are compiled with their own scope.

## Fix

Split defs into a separate file and import them:

```kida
{# _helpers.html #}
{% def helper() %}shared logic{% end %}
```

```kida
{# page.html #}
{% from "_helpers.html" import helper %}

{% block content %}
  {{ helper() }}
{% end %}
```

Now both full-page `render()` and `render_block("content", ...)` work, because the block imports `helper` from another template.

## Regions: An Alternative

`{% region %}` blocks are compiled as part of the template and have access to defs and imports from the same file. If you need a parameterized block that uses defs, consider a region instead of splitting into a separate template:

```kida
{% from "_helpers.html" import helper %}

{% region sidebar(current_path="/") %}
  {{ helper(current_path) }}
{% end %}
```

Both `render_block("sidebar", ...)` and `{{ sidebar(...) }}` work, and the region body can call `helper()`. See [Functions — Regions](/docs/syntax/functions/#regions).

## When This Matters

- **Fragment rendering** — Chirp and similar frameworks use `render_block()` to return HTML fragments for htmx, SSE, etc.
- **Block caching** — Site-scoped block caching renders blocks individually via `render_block()`.

## See Also

- [Framework Integration](/docs/usage/framework-integration/) — Block rendering, introspection, adapters
- [Functions and macros](/docs/syntax/functions/) — `{% def %}` and `{% from %}`
- [Block caching](../advanced/block-caching.md) — Caching individual blocks
