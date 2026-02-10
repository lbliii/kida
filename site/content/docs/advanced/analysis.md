---
title: Static Analysis
description: Analyze templates for dependencies, purity, and caching potential
draft: false
weight: 10
lang: en
type: doc
tags:
- advanced
- analysis
- caching
keywords:
- static analysis
- dependencies
- purity
- cache scope
- introspection
- call validation
- validate_calls
icon: magnifying-glass
---

# Static Analysis

Kida can statically analyze compiled templates to extract dependency information,
determine output purity, and recommend caching strategies — all without rendering.
No other Python template engine provides this capability.

## What Analysis Provides

Every compiled template exposes these analysis results:

| Capability | Method | Returns |
|---|---|---|
| **Context dependencies** | `template.required_context()` | Top-level variable names the template accesses |
| **Full dependency paths** | `template.depends_on()` | Dotted paths like `page.title`, `site.pages` |
| **Block metadata** | `template.block_metadata()` | Per-block purity, dependencies, cache scope |
| **Full metadata** | `template.template_metadata()` | Complete analysis including inheritance info |
| **Cache check** | `template.is_cacheable("nav")` | Whether a block can be safely cached |
| **Context validation** | `template.validate_context(ctx)` | Missing variable names before rendering |

## Quick Start

```python
from kida import Environment, DictLoader

env = Environment(loader=DictLoader({
    "page.html": """
        {% extends "base.html" %}
        {% block title %}{{ page.title }}{% end %}
        {% block nav %}
            <nav>{% for item in site.menu %}<a href="{{ item.url }}">{{ item.label }}</a>{% end %}</nav>
        {% end %}
        {% block content %}{{ page.content }}{% end %}
    """,
    "base.html": """
        <html>
        <head><title>{% block title %}{% end %}</title></head>
        <body>{% block nav %}{% end %}{% block content %}{% end %}</body>
        </html>
    """,
}))

template = env.get_template("page.html")
```

### Check What Variables a Template Needs

```python
>>> template.required_context()
frozenset({'page', 'site'})
```

### Validate Context Before Rendering

```python
>>> template.validate_context({"page": page_obj})
['site']  # 'site' is missing

>>> template.validate_context({"page": page_obj, "site": site_obj})
[]  # all required variables present
```

### Inspect Block-Level Metadata

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

### Determine Caching Strategy

```python
>>> template.is_cacheable("nav")    # site-wide cache
True
>>> template.is_cacheable("content")  # page-specific, still cacheable
True
>>> template.is_cacheable()          # all blocks cacheable?
True
```

## Analysis Concepts

### Dependencies

The dependency walker extracts every context variable path a template accesses.
Results are *conservative*: they may include paths not taken at runtime (e.g.,
both branches of an `{% if %}`) but never miss a path that is used.

```python
>>> template.depends_on()
frozenset({'page.title', 'page.content', 'site.menu'})
```

`required_context()` extracts just the top-level names:

```python
>>> template.required_context()
frozenset({'page', 'site'})
```

### Purity

A block is **pure** if its output is deterministic given the same inputs.
Pure blocks can be cached safely. Impure blocks (using `random`, `shuffle`,
or similar) must be re-rendered each time.

| Purity | Meaning | Cacheable? |
|---|---|---|
| `"pure"` | Deterministic output | Yes |
| `"impure"` | Uses non-deterministic functions | No |
| `"unknown"` | Cannot determine statically | Treat as impure |

### Cache Scope

Cache scope tells you *how broadly* a block's output can be reused:

| Scope | Meaning | Example |
|---|---|---|
| `"site"` | Same output for every page | Navigation, footer |
| `"page"` | Varies per page but stable for a given page | Content, title |
| `"none"` | Cannot cache (impure block) | Random quotes |
| `"unknown"` | Cannot determine | Mixed dependencies |

### Landmarks

Kida detects HTML5 landmark elements (`<nav>`, `<main>`, `<header>`, `<footer>`,
`<aside>`) in block output and uses them to infer the block's role:

```python
>>> meta["nav"].emits_landmarks
frozenset({'nav'})
>>> meta["nav"].inferred_role
'navigation'
```

## Context Validation

`validate_context()` is designed for build systems, SSR frameworks, and testing
pipelines that need to catch missing variables before rendering:

```python
template = env.get_template("email.html")
missing = template.validate_context(user_context)
if missing:
    raise ValueError(f"Missing template variables: {missing}")
result = template.render(**user_context)
```

This runs dependency analysis (cached after first call) and compares required
top-level variable names against the provided context keys plus environment
globals. It returns a sorted list of missing names, or an empty list if
everything is present.

## Call-Site Validation

Kida can validate `{% def %}` call sites at compile time, catching parameter errors
before any template is rendered:

```python
from kida import Environment

env = Environment(validate_calls=True)

template = env.from_string("""
    {% def button(text: str, url: str, style="primary") %}
        <a href="{{ url }}" class="btn btn-{{ style }}">{{ text }}</a>
    {% end %}

    {{ button(text="Save", urll="/save") }}
""")
# UserWarning: Call to 'button' at <string>:6 — unknown params: urll; missing required: url
```

### What It Checks

| Issue | Example |
|-------|---------|
| **Unknown params** | Calling `button(labl="X")` when param is `label` |
| **Missing required** | Calling `button()` when `text` has no default |
| **`*args` / `**kwargs` relaxation** | Definitions with `*args` or `**kwargs` suppress unknown-param warnings |

### Programmatic API

For build systems and CI pipelines, use the `BlockAnalyzer` directly:

```python
from kida import Environment, DictLoader
from kida.analysis import BlockAnalyzer

env = Environment(
    loader=DictLoader({"page.html": src}),
    preserve_ast=True,
)
template = env.get_template("page.html")

analyzer = BlockAnalyzer()
issues = analyzer.validate_calls(template._optimized_ast)

for issue in issues:
    if not issue.is_valid:
        print(f"{issue.def_name} at line {issue.lineno}: "
              f"unknown={issue.unknown_params}, "
              f"missing={issue.missing_required}")
```

### CallValidation

| Field | Type | Description |
|-------|------|-------------|
| `def_name` | `str` | Name of the called `{% def %}` |
| `lineno` | `int` | Line number of the call site |
| `col_offset` | `int` | Column offset of the call site |
| `unknown_params` | `tuple[str, ...]` | Keyword args not in the definition |
| `missing_required` | `tuple[str, ...]` | Required params not provided |
| `duplicate_params` | `tuple[str, ...]` | Params passed more than once |

| Property | Description |
|----------|-------------|
| `is_valid` | `True` if no issues were found |

---

## Configuration

Use `AnalysisConfig` to customize analysis behavior for your framework:

```python
from kida import AnalysisConfig
from kida.analysis import BlockAnalyzer

config = AnalysisConfig(
    # Variables indicating page-specific scope
    page_prefixes=frozenset({"post.", "post", "article.", "article"}),
    # Variables indicating site-wide scope
    site_prefixes=frozenset({"settings.", "settings", "global."}),
    # Additional functions your framework guarantees are pure
    extra_pure_functions=frozenset({"asset_url", "t", "current_lang"}),
    # Filters that produce non-deterministic output
    extra_impure_filters=frozenset({"random_choice"}),
)

analyzer = BlockAnalyzer(config=config)
```

Kida ships with a default config (`DEFAULT_CONFIG`) that includes common SSG
pure functions like `asset_url`, `t`, `canonical_url`, etc.

## Case Study: Bengal Static Site Generator

[Bengal](https://github.com/bengal-ssg/bengal) uses Kida's analysis API to
implement smart incremental builds:

1. **Compile all templates** with AST preservation enabled
2. **Analyze each template** to get block metadata
3. **Identify site-cacheable blocks** (nav, footer, sidebar) using `cache_scope == "site"`
4. **Cache site-scoped blocks** once per build, reuse across all pages
5. **Only re-render page-scoped blocks** when page content changes
6. **Track dependencies** to invalidate caches when upstream data changes

This reduces full-site rebuild time by 40-60% for sites with shared navigation
and footer blocks.

## API Reference

### Template Methods

| Method | Signature | Description |
|---|---|---|
| `required_context()` | `() -> frozenset[str]` | Top-level variable names needed |
| `depends_on()` | `() -> frozenset[str]` | All dotted dependency paths |
| `validate_context()` | `(context: dict) -> list[str]` | Missing variable names |
| `block_metadata()` | `() -> dict[str, BlockMetadata]` | Per-block analysis results |
| `template_metadata()` | `() -> TemplateMetadata \| None` | Full template analysis |
| `is_cacheable()` | `(block_name: str \| None) -> bool` | Cache safety check |
| `list_blocks()` | `() -> list[str]` | Block names in template |

### BlockMetadata

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Block identifier |
| `depends_on` | `frozenset[str]` | Context paths accessed |
| `is_pure` | `"pure" \| "impure" \| "unknown"` | Determinism classification |
| `cache_scope` | `"site" \| "page" \| "none" \| "unknown"` | Recommended cache level |
| `emits_html` | `bool` | Whether block produces output |
| `emits_landmarks` | `frozenset[str]` | HTML5 landmarks detected |
| `inferred_role` | `str` | Heuristic role classification |

### TemplateMetadata

| Field | Type | Description |
|---|---|---|
| `name` | `str \| None` | Template identifier |
| `extends` | `str \| None` | Parent template name |
| `blocks` | `dict[str, BlockMetadata]` | All block metadata |
| `top_level_depends_on` | `frozenset[str]` | Dependencies outside blocks |

| Method | Description |
|---|---|
| `all_dependencies()` | Union of all block and top-level dependencies |
| `get_block(name)` | Get metadata for a specific block |
| `cacheable_blocks()` | List of blocks where `is_cacheable()` is True |
| `site_cacheable_blocks()` | List of blocks with `cache_scope == "site"` |

### CallValidation

| Field | Type | Description |
|---|---|---|
| `def_name` | `str` | Name of the called `{% def %}` |
| `lineno` | `int` | Line number of the call site |
| `col_offset` | `int` | Column offset of the call site |
| `unknown_params` | `tuple[str, ...]` | Keyword args not in the definition |
| `missing_required` | `tuple[str, ...]` | Required params not provided |
| `duplicate_params` | `tuple[str, ...]` | Params passed more than once |

| Property | Type | Description |
|---|---|---|
| `is_valid` | `bool` | `True` if no issues were found |

### AnalysisConfig

| Field | Type | Default | Description |
|---|---|---|---|
| `page_prefixes` | `frozenset[str]` | `{"page.", "page", ...}` | Page-scope variable prefixes |
| `site_prefixes` | `frozenset[str]` | `{"site.", "site", ...}` | Site-scope variable prefixes |
| `extra_pure_functions` | `frozenset[str]` | `frozenset()` | Additional pure function names |
| `extra_impure_filters` | `frozenset[str]` | `frozenset()` | Additional impure filter names |
