---
name: kida-bengal-integration
description: Use Kida with Bengal SSG: block caching, incremental builds, template context. Use when building Bengal sites or optimizing build performance.
---

# Kida Bengal Integration

Bengal uses Kida's static analysis for incremental builds and block caching.

## Workflow

1. **Compile templates** — Enable AST preservation (default)
2. **Analyze each template** — Get block metadata
3. **Identify site-cacheable blocks** — `cache_scope == "site"` (nav, footer, sidebar)
4. **Cache site-scoped blocks** — Once per build, reuse across all pages
5. **Re-render page-scoped blocks only** — When page content changes
6. **Track dependencies** — Invalidate when upstream data changes

Result: 40-60% rebuild time reduction for sites with shared layout.

## Bengal Engine APIs

### get_template_introspection

```python
info = engine.get_template_introspection("page.html")
if info:
    for block_name, meta in info["blocks"].items():
        if meta.cache_scope == "site":
            # Block is site-cacheable
            pass
```

### get_cacheable_blocks

Returns `block_name → cache_scope` for blocks with `cache_scope in ("site", "page")` and `is_pure == "pure"`:

```python
cacheable = engine.get_cacheable_blocks("base.html")
# {'nav': 'site', 'footer': 'site', 'content': 'page'}
```

## Cache Scope

| Scope | Meaning | Example |
|-------|---------|---------|
| `site` | Same for every page | Nav, footer |
| `page` | Varies per page | Content, title |

## Template Context

Bengal passes `page` and `site` (and theme-specific vars) to templates. Ensure templates use these consistently for analysis to infer cache scope correctly.
