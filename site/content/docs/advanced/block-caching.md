---
title: Block Caching
description: Connect static analysis to runtime block caching for framework-level optimization
draft: false
weight: 70
lang: en
type: doc
tags:
- advanced
- caching
- performance
keywords:
- block caching
- site-scoped cache
- CachedBlocksDict
- incremental builds
- cache scope
icon: database
---

# Block Caching

Kida's [[docs/advanced/analysis|static analysis]] can determine which template blocks are safe to cache and at what scope. This article shows how to connect analysis results to runtime caching using `CachedBlocksDict` — the same mechanism [Bengal](https://github.com/bengal-ssg/bengal) uses for 40-60% faster incremental builds.

## The Pipeline

```
analyze → identify cacheable blocks → render once → cache → reuse
```

1. **Analyze** templates with `block_metadata()` or `template_metadata()`
2. **Identify** site-scoped blocks (`cache_scope == "site"`)
3. **Render** those blocks once
4. **Cache** the HTML output
5. **Inject** cached HTML via `CachedBlocksDict` for subsequent renders

## Step 1: Identify Cacheable Blocks

Use the analysis API to find blocks that can be cached:

```python
from kida import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader("templates/"),
    preserve_ast=True,  # Required for analysis
)

template = env.get_template("page.html")

# Get metadata for all blocks
meta = template.template_metadata()
if meta:
    # Blocks safe to cache at the site level
    site_blocks = meta.site_cacheable_blocks()
    for block in site_blocks:
        print(f"{block.name}: scope={block.cache_scope}, pure={block.is_pure}")
        # nav: scope=site, pure=pure
        # footer: scope=site, pure=pure
```

### Cache Scope Meaning

| Scope | Meaning | Cache Strategy |
|-------|---------|---------------|
| `"site"` | Same output for every page | Cache once per build, reuse everywhere |
| `"page"` | Varies per page | Cache per page, invalidate on page change |
| `"none"` | Impure block | Do not cache |
| `"unknown"` | Cannot determine | Treat as uncacheable |

## Step 2: Render and Cache Site Blocks

Render the first page to get site-scoped block HTML, then cache it:

```python
# Render one page to populate site-scoped blocks
first_page_html = template.render(page=pages[0], site=site)

# Extract site-scoped block HTML by rendering blocks individually
site_cache = {}
for block in site_blocks:
    # render_block renders a single block in isolation
    block_html = template.render_block(block.name, page=pages[0], site=site)
    site_cache[block.name] = block_html
```

## Step 3: Inject Cached Blocks

Use `CachedBlocksDict` to intercept block lookups and return cached HTML:

```python
from kida.template.cached_blocks import CachedBlocksDict

cached_names = frozenset(site_cache.keys())
stats = {"hits": 0, "misses": 0}

# Render remaining pages with cached site blocks
for page in pages[1:]:
    # CachedBlocksDict wraps the normal blocks dict
    cached_blocks = CachedBlocksDict(
        original=None,       # Template will populate via setdefault()
        cached=site_cache,   # Pre-rendered HTML
        cached_names=cached_names,
        stats=stats,         # Optional hit/miss tracking
    )

    html = template.render(
        page=page,
        site=site,
        _blocks=cached_blocks,  # Inject cached blocks
    )
```

## CachedBlocksDict

`CachedBlocksDict` is a dict-like wrapper that intercepts block lookups:

```python
from kida.template.cached_blocks import CachedBlocksDict

wrapper = CachedBlocksDict(
    original=None,                          # Underlying blocks dict
    cached={"nav": "<nav>...</nav>"},       # Pre-rendered HTML
    cached_names=frozenset({"nav"}),        # Which blocks are cached
    stats={"hits": 0, "misses": 0},        # Optional statistics
)
```

When the template calls `blocks.get("nav")`, the wrapper returns a function that produces the cached HTML instead of re-rendering. For non-cached blocks, it falls through to the original dict.

### Supported Operations

| Method | Behavior |
|--------|----------|
| `.get(key)` | Returns cached wrapper or falls through |
| `.setdefault(key, default)` | Cached blocks take precedence |
| `[key]` | Returns cached wrapper or falls through |
| `[key] = value` | Writes to original dict |
| `key in dict` | Checks both cached and original |
| `.keys()` | Union of cached and original keys |
| `.copy()` | Returns plain dict with cached wrappers |

### Cache Statistics

Pass a shared stats dict to track hit/miss rates:

```python
stats = {"hits": 0, "misses": 0}

for page in pages:
    blocks = CachedBlocksDict(None, cache, cached_names, stats=stats)
    template.render(page=page, site=site, _blocks=blocks)

hit_rate = stats["hits"] / (stats["hits"] + stats["misses"])
print(f"Block cache hit rate: {hit_rate:.1%}")
```

## Complete Example

```python
from kida import Environment, FileSystemLoader
from kida.template.cached_blocks import CachedBlocksDict

env = Environment(
    loader=FileSystemLoader("templates/"),
    preserve_ast=True,
)

template = env.get_template("page.html")

# 1. Analyze
meta = template.template_metadata()
site_blocks = meta.site_cacheable_blocks() if meta else []
site_block_names = frozenset(b.name for b in site_blocks)

# 2. Render first page (populates cache)
first_html = template.render(page=pages[0], site=site)
site_cache = {}
for block in site_blocks:
    site_cache[block.name] = template.render_block(
        block.name, page=pages[0], site=site
    )

# 3. Render remaining pages with cache
stats = {"hits": 0, "misses": 0}
results = [first_html]

for page in pages[1:]:
    blocks = CachedBlocksDict(None, site_cache, site_block_names, stats=stats)
    results.append(template.render(page=page, site=site, _blocks=blocks))

print(f"Rendered {len(results)} pages")
print(f"Cache hits: {stats['hits']}, misses: {stats['misses']}")
```

## When to Use Block Caching

| Scenario | Benefit |
|----------|---------|
| Static site generation | 40-60% faster full-site rebuilds |
| Server-side rendering with shared layout | Avoid re-rendering nav/footer per request |
| Multi-page PDF generation | Cache header/footer across pages |
| Email batch rendering | Cache shared template chrome |

Block caching is most effective when:
- Templates use inheritance with shared blocks (nav, footer, sidebar)
- The same template renders many times with different page data
- Site-wide data (menus, config) doesn't change between renders

## See Also

- [[docs/advanced/analysis|Static Analysis]] — Block-level dependency and purity analysis
- [[docs/advanced/profiling|Profiling]] — Identify slow blocks worth caching
- [[docs/syntax/caching|Fragment Caching]] — Template-level `{% cache %}` syntax
- [[docs/about/performance|Performance]] — Overall optimization strategy
