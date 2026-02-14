---
title: Kida Syntax and Features
description: Kida's syntax and when it fits
draft: false
weight: 40
lang: en
type: doc
tags:
- about
- syntax
- features
keywords:
- syntax
- features
- migration
icon: arrows-angle-contract
---

# Kida Syntax and Features

Kida uses Jinja2-compatible syntax with extensions. Key differences for migration.

## Syntax

### Unified Block Endings

Kida uses `{% end %}` for all blocks:

```kida
{% if condition %}
    content
{% end %}

{% for item in items %}
    {{ item }}
{% end %}
```

### Pipeline Operator

Kida uses `|>` for pipelines (Jinja2 uses `|`):

```kida
{{ title |> escape |> upper |> truncate(50) }}
```

### Pattern Matching

```kida
{% match status %}
{% case "active" %}
    Active
{% case "pending" %}
    Pending
{% case "error" %}
    Error
{% case _ %}
    Unknown
{% end %}
```

### Block Caching

```kida
{% cache "sidebar-" + user.id %}
    {{ render_sidebar(user) }}
{% end %}
```

## Features

| Feature | Kida |
|---------|------|
| Compilation | AST → AST |
| Rendering | StringBuilder O(n) |
| Free-threading | Native (PEP 703, Python 3.14t+) |
| Dependencies | Zero |
| Block endings | Unified `{% end %}` |
| Profiling | Opt-in `profiled_render()` |
| Pattern matching | `{% match %}` |
| Block caching | `{% cache %}` |
| Async | Native |

## When to Use Kida

- Need free-threading support (Python 3.14t)
- Want zero dependencies
- Prefer unified block syntax
- Need built-in caching
- Want pattern matching in templates
- Value AST-native compilation
- Work with dict-heavy contexts
- Need built-in render profiling

## Limitations

- No LaTeX/RTF output formats
- Jinja2-specific extensions may not be available

## See Also

- [[docs/about/performance|Performance]] — Benchmarks
- [[docs/about/architecture|Architecture]] — How Kida works
- [[docs/tutorials|Tutorials]] — Migration guides
