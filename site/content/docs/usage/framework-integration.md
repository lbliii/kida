---
title: Framework Integration
description: Block rendering, introspection, and composition APIs for Chirp, Bengal, and custom adapters
draft: false
weight: 22
lang: en
type: doc
tags:
- usage
- framework
- blocks
- introspection
keywords:
- framework
- render_block
- render_with_blocks
- template_metadata
- composition
- adapter
icon: puzzle
---

# Framework Integration

Kida provides block-level rendering, introspection, and composition helpers for frameworks that need fragments (HTMX, Turbo), layout assembly, or template validation. Use these APIs when building adapters, validating routes, or composing layouts programmatically.

## Overview

| API | Purpose |
|-----|---------|
| `render_block(name, **ctx)` | Render a single block — HTMX partials, cached nav |
| `render_with_blocks(overrides, **ctx)` | Compose layout with pre-rendered HTML in blocks |
| `list_blocks()` | Discover block names for validation |
| `template_metadata()` | Full analysis — blocks, extends, dependencies |
| `validate_block_exists()` | Check block exists before `render_block` |
| `get_structure()` | Lightweight manifest for composition planning |

## Block Rendering

### render_block

Render a single block from a template. Supports inherited blocks: when the template extends a parent, you can render parent-only blocks by name (e.g. `render_block("sidebar")` on a child that extends a base defining `sidebar`).

```python
template = env.get_template("page.html")

# Render content block (HTMX partial response)
html = template.render_block("content", title="Hello", items=items)

# Render parent-only block from descendant
html = template.render_block("sidebar", site=site)
```

**Raises** `KeyError` if the block does not exist in the template or any parent.

### render_with_blocks

Render a template with pre-rendered HTML injected into blocks. Enables programmatic layout composition without `{% extends %}` in the template source.

```python
layout = env.get_template("_layout.html")
inner_html = "<h1>Hello</h1><p>Content here.</p>"

# Inject inner_html as the "content" block
html = layout.render_with_blocks({"content": inner_html}, title="Page Title")
```

Each key in `block_overrides` names a block; the value is a pre-rendered HTML string that replaces that block's default content.

### list_blocks

List all blocks available for `render_block()`, including inherited blocks.

```python
blocks = template.list_blocks()
# ['title', 'nav', 'content', 'footer']
```

## Introspection

### template_metadata

Get full template analysis including inheritance info, block metadata, and dependencies. Returns `None` if AST was not preserved (`preserve_ast=False` or loaded from bytecode cache without source).

```python
meta = template.template_metadata()
if meta:
    print(meta.extends)              # Parent template name
    print(list(meta.blocks.keys()))  # Block names
    print(meta.all_dependencies())   # Context paths accessed
```

### block_metadata

Get per-block analysis: purity, cache scope, inferred role.

```python
blocks = template.block_metadata()
nav = blocks.get("nav")
if nav and nav.cache_scope == "site":
    # Safe to cache nav across all pages
    html = cache.get_or_render("nav", ...)
```

### validate_context

Check a context dict for missing variables before rendering.

```python
missing = template.validate_context(user_context)
if missing:
    raise ValueError(f"Missing template variables: {missing}")
```

## Composition Module

The `kida.composition` module provides validation helpers for frameworks:

```python
from kida import Environment, FileSystemLoader
from kida.composition import validate_block_exists, get_structure

env = Environment(loader=FileSystemLoader("templates/"))
```

### validate_block_exists

Check if a block exists before calling `render_block`:

```python
if validate_block_exists(env, "skills/page.html", "page_content"):
    html = env.get_template("skills/page.html").render_block("page_content", ...)
else:
    # Handle missing block
    ...
```

Returns `False` if the template is not found or the block is missing.

### get_structure

Get a lightweight structure manifest (block names, extends parent, dependencies). Cached by Environment for reuse.

```python
struct = get_structure(env, "page.html")
if struct and "page_root" in struct.block_names:
    # Template has page_root block — suitable for layout composition
    ...
```

### block_role_for_framework

Classify block metadata into framework-relevant roles (`"fragment"`, `"page_root"`, or `None`). Useful for frameworks that need to distinguish content blocks from layout roots.

```python
from kida.composition import block_role_for_framework

meta = template.template_metadata()
for name, block in meta.blocks.items():
    role = block_role_for_framework(block)
    if role == "fragment":
        # Suitable for HTMX partial
        ...
```

## Adapter Pattern

A minimal template adapter wraps Kida's APIs:

```python
from kida import Environment
from typing import Any

class KidaAdapter:
    """TemplateAdapter implementation using Kida's block/layout APIs."""

    def __init__(self, env: Environment) -> None:
        self._env = env

    def render_template(self, template: str, context: dict[str, Any]) -> str:
        return self._env.get_template(template).render(context)

    def render_block(self, template: str, block: str, context: dict[str, Any]) -> str:
        return self._env.get_template(template).render_block(block, context)

    def compose_layout(
        self,
        template: str,
        block_overrides: dict[str, str],
        context: dict[str, Any],
    ) -> str:
        return self._env.get_template(template).render_with_blocks(
            block_overrides, **context
        )

    def template_metadata(self, template: str) -> object | None:
        from kida.environment.exceptions import (
            TemplateNotFoundError,
            TemplateSyntaxError,
        )
        try:
            return self._env.get_template(template).template_metadata()
        except (TemplateNotFoundError, TemplateSyntaxError):
            return None
```

[Chirp](https://github.com/lbliii/chirp) uses this pattern in `KidaAdapter`.

## Case Studies

### Bengal (Static Site Generator)

- **Full render** — `render()` for page output
- **Bytecode cache** — Persistent `.bengal/cache/kida/` for cold-start
- **Fragment cache** — `{% cache %}` with site-scoped TTL
- **Analysis** — `block_metadata()`, `is_cacheable()` for incremental builds

### Chirp (Web Framework)

- **Full render** — `render()` for full-page responses
- **Block render** — `render_block()` for HTMX fragments, partial updates
- **Layout composition** — `render_with_blocks()` for programmatic layout assembly
- **Streaming** — `render_stream()`, `render_stream_async()` for chunked HTTP
- **Introspection** — `template_metadata()` for composition planning, `validate_block_exists()` before `render_block`
- **Adapter** — `KidaAdapter` implements Chirp's `TemplateAdapter` interface

## See Also

- [Inheritance](/docs/syntax/inheritance/) — `render_block` with `{% extends %}`
- [Static Analysis](/docs/advanced/analysis/) — Full introspection API
- [render_block and Def Scope](/docs/troubleshooting/render-block-scope/) — Def scope in blocks
