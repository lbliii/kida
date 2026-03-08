---
name: kida-static-analysis
description: Use Kida static analysis for pre-render validation, incremental builds, block caching. Use when validating template context, optimizing build times, or implementing caching.
---

# Kida Static Analysis

Kida analyzes compiled templates without rendering. Use for validation, incremental builds, and caching.

## API Overview

| Method | Returns |
|--------|---------|
| `required_context()` | Top-level variable names needed |
| `depends_on()` | Dotted paths: `page.title`, `site.menu` |
| `validate_context(ctx)` | List of missing variable names |
| `block_metadata()` | Per-block purity, dependencies, cache scope |
| `template_metadata()` | Full analysis including inheritance |
| `is_cacheable(block_name)` | Whether block can be safely cached |

## Pre-Render Validation

Catch missing variables before rendering:

```python
missing = template.validate_context(user_context)
if missing:
    raise ValueError(f"Missing template variables: {missing}")
result = template.render(**user_context)
```

## Context Dependencies

```python
>>> template.required_context()
frozenset({'page', 'site'})

>>> template.depends_on()
frozenset({'page.title', 'page.content', 'site.menu'})
```

Results are conservative: may over-approximate, never miss a used path.

## Block Metadata

```python
>>> meta = template.block_metadata()
>>> nav = meta["nav"]
>>> nav.depends_on
frozenset({'site.menu'})
>>> nav.is_pure
'pure'
>>> nav.cache_scope
'site'
>>> nav.is_cacheable()
True
```

## Purity

| Value | Meaning | Cacheable? |
|-------|---------|------------|
| `"pure"` | Deterministic output | Yes |
| `"impure"` | Uses random, shuffle, etc. | No |
| `"unknown"` | Cannot determine | Treat as impure |

## Cache Scope

| Scope | Meaning | Example |
|-------|---------|---------|
| `"site"` | Same for every page | Nav, footer |
| `"page"` | Varies per page | Content, title |
| `"none"` | Impure | Random quotes |
| `"unknown"` | Cannot determine | Mixed deps |

## Caching Strategy

```python
if template.is_cacheable("nav"):
    html = cache.get_or_render("nav", lambda: template.render_block("nav", site=site))
else:
    html = template.render_block("nav", site=site)
```

## AST Preservation

Analysis requires `preserve_ast=True` (default). Templates loaded from bytecode cache without source may return empty metadata.

## BlockMetadata Fields

- `name`, `depends_on`, `is_pure`, `cache_scope`
- `emits_html`, `emits_landmarks`, `inferred_role`

## TemplateMetadata

- `name`, `extends`, `blocks`, `top_level_depends_on`
- `all_dependencies()`, `get_block(name)`, `cacheable_blocks()`, `site_cacheable_blocks()`
