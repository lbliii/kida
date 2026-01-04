---
title: Comparison
description: Kida vs Jinja2 feature comparison
draft: false
weight: 40
lang: en
type: doc
tags:
- about
- comparison
keywords:
- comparison
- jinja2
- differences
icon: arrows-angle-contract
---

# Comparison

Comprehensive comparison of Kida and Jinja2.

## Feature Matrix

| Feature | Kida | Jinja2 |
|---------|------|--------|
| **Compilation** | AST → AST | String generation |
| **Rendering** | StringBuilder O(n) | Generator yields |
| **Free-threading** | Native (PEP 703) | N/A |
| **Dependencies** | Zero | markupsafe |
| **Block endings** | Unified `{% end %}` | `{% endif %}`, etc. |
| **Pattern matching** | `{% match %}` | N/A |
| **Pipeline** | `\|>` operator | N/A |
| **Block caching** | `{% cache %}` | N/A |
| **Async** | Native | `auto_await()` |

## Syntax Differences

### Block Endings

**Jinja2**:

```jinja2
{% if condition %}
    content
{% endif %}

{% for item in items %}
    {{ item }}
{% endfor %}
```

**Kida** (unified):

```kida
{% if condition %}
    content
{% end %}

{% for item in items %}
    {{ item }}
{% end %}
```

Kida also supports Jinja2-style endings for compatibility.

### Pipeline Operator

**Jinja2**:

```jinja2
{{ title | escape | upper | truncate(50) }}
```

**Kida** (pipeline):

```kida
{{ title |> escape |> upper |> truncate(50) }}
```

Both syntaxes work in Kida.

### Pattern Matching

**Jinja2**:

```jinja2
{% if status == "active" %}
    Active
{% elif status == "pending" %}
    Pending
{% elif status == "error" %}
    Error
{% else %}
    Unknown
{% endif %}
```

**Kida**:

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

**Jinja2**: Not built-in (requires extensions)

**Kida**:

```kida
{% cache "sidebar-" + user.id %}
    {{ render_sidebar(user) }}
{% end %}
```

## API Differences

### Filter Registration

**Jinja2**:

```python
env.filters["double"] = lambda x: x * 2
```

**Kida**:

```python
env.add_filter("double", lambda x: x * 2)

# Or decorator
@env.filter()
def double(value):
    return value * 2
```

### Markup Class

**Jinja2**: Requires `markupsafe`:

```python
from markupsafe import Markup
```

**Kida**: Built-in:

```python
from kida import Markup
```

### Environment Options

**Jinja2**:

```python
env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(),
    extensions=["jinja2.ext.do"],
)
```

**Kida**:

```python
env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=True,
    cache_size=400,
    fragment_ttl=300.0,
)
```

## Performance

| Template | Kida | Jinja2 | Speedup |
|----------|------|--------|---------|
| Small | 0.3ms | 0.5ms | 1.6x |
| Medium | 2ms | 3.5ms | 1.75x |
| Large | 15ms | 25ms | 1.67x |

Kida's StringBuilder pattern is 25-40% faster than Jinja2's generators.

## When to Use Kida

Choose Kida if you:

- Need free-threading support (Python 3.14t)
- Want zero dependencies
- Prefer unified block syntax
- Need built-in caching
- Want pattern matching in templates
- Value AST-native compilation

## When to Keep Jinja2

Keep Jinja2 if you:

- Need LaTeX/RTF output formats
- Use Jinja2-specific extensions
- Have heavy investment in Jinja2 tooling
- Need the sandboxed environment

## Migration

Most Jinja2 templates work unchanged in Kida:

```python
# Before
from jinja2 import Environment, FileSystemLoader

# After
from kida import Environment, FileSystemLoader
```

See [[docs/tutorials/migrate-from-jinja2|Migration Guide]] for details.

## See Also

- [[docs/tutorials/migrate-from-jinja2|Migration Guide]] — Step-by-step migration
- [[docs/about/performance|Performance]] — Detailed benchmarks
- [[docs/about/architecture|Architecture]] — How Kida works

