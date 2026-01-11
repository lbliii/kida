---
title: Migrate from Jinja2
description: Rewrite Jinja2 templates for Kida
draft: false
weight: 10
lang: en
type: doc
tags:
- migration
- jinja2
- tutorial
keywords:
- migration
- jinja2
- switch
icon: arrow-right
---

# Migrate from Jinja2

Guide for rewriting Jinja2 templates in Kida syntax.

:::note[Not a Drop-In Replacement]
Kida is **not** compatible with Jinja2. Templates must be rewritten using Kida syntax. This guide helps you translate common patterns.
:::

## Prerequisites

- Python 3.14+
- Familiarity with Jinja2 template syntax

## Step 1: Install Kida

```bash
pip install kida
```

## Step 2: Update Imports

**Before (Jinja2):**

```python
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
```

**After (Kida):**

```python
from kida import Environment, FileSystemLoader
from kida import Markup  # Built-in, no markupsafe
```

## Step 3: Update Environment Creation

**Before (Jinja2):**

```python
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=select_autoescape(),
    extensions=['jinja2.ext.do'],
)
```

**After (Kida):**

```python
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True,
    cache_size=400,
    fragment_ttl=300.0,
)
```

Note: Kida does not use Jinja2-style extensions. For side effects, use `{% set _ = expr %}`.

## Step 4: Rewrite Block Endings

Convert specific endings to unified `{% end %}`:

**Jinja2:**

```jinja2
{% if condition %}
    content
{% endif %}

{% for item in items %}
    {{ item }}
{% endfor %}

{% block content %}
    ...
{% endblock %}
```

**Kida:**

```kida
{% if condition %}
    content
{% end %}

{% for item in items %}
    {{ item }}
{% end %}

{% block content %}
    ...
{% end %}
```

## Step 5: Update Custom Filters

**Before (Jinja2):**

```python
def format_money(value, currency='$'):
    return f'{currency}{value:,.2f}'

env.filters['money'] = format_money
```

**After (Kida):**

```python
def format_money(value, currency='$'):
    return f'{currency}{value:,.2f}'

env.add_filter('money', format_money)

# Or use the decorator
@env.filter()
def format_money(value, currency='$'):
    return f'{currency}{value:,.2f}'
```

## Step 6: Update Custom Tests

**Before (Jinja2):**

```python
def is_prime(n):
    return n > 1 and all(n % i for i in range(2, n))

env.tests['prime'] = is_prime
```

**After (Kida):**

```python
env.add_test('prime', is_prime)

# Or use the decorator
@env.test()
def is_prime(n):
    return n > 1 and all(n % i for i in range(2, n))
```

## API Mapping

| Jinja2 | Kida |
|--------|------|
| `Environment` | `Environment` |
| `FileSystemLoader` | `FileSystemLoader` |
| `DictLoader` | `DictLoader` |
| `Template.render()` | `Template.render()` |
| `Template.render_async()` | `Template.render_async()` |
| `Markup` (markupsafe) | `Markup` (built-in) |
| `env.filters[name] = func` | `env.add_filter(name, func)` |
| `env.tests[name] = func` | `env.add_test(name, func)` |
| `env.globals[name] = value` | `env.add_global(name, value)` |

## Syntax Translation

| Jinja2 | Kida |
|--------|------|
| `{% endif %}` | `{% end %}` |
| `{% endfor %}` | `{% end %}` |
| `{% endblock %}` | `{% end %}` |
| `{% endmacro %}` | `{% end %}` |
| `{{ x \| filter }}` | `{{ x \|> filter }}` (pipeline) |
| `{% if %}...{% elif %}...{% endif %}` | `{% match %}...{% case %}...{% end %}` |
| N/A | `{% cache key %}...{% end %}` |

## New Features

After migrating, explore Kida-only features:

### Pipeline Operator

```kida
{{ title |> escape |> upper |> truncate(50) }}
```

### Pattern Matching

```kida
{% match status %}
{% case "active" %}
    ✓ Active
{% case "pending" %}
    ⏳ Pending
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

## Verification

After migration, verify templates render correctly:

```python
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")
result = template.render(name="World")
assert result == "Hello, World!"
print("✅ Migration successful!")
```

## Common Issues

### Markup Import

**Error**: `ImportError: cannot import name 'Markup' from 'markupsafe'`

**Fix**: Import from Kida:

```python
from kida import Markup  # Not from markupsafe
```

### Filter Registration

**Error**: `TypeError: 'FilterRegistry' object does not support item assignment`

**Fix**: Use `add_filter()`:

```python
env.add_filter('name', func)  # Not env.filters['name'] = func
```

### Block Endings

**Error**: `TemplateSyntaxError: Unexpected tag 'endif'`

**Fix**: Use unified `{% end %}`:

```kida
{% if x %}...{% end %}  # Not {% endif %}
```

## See Also

- [[docs/syntax/control-flow|Control Flow]] — Pattern matching syntax
- [[docs/about/comparison|Comparison]] — Kida vs Jinja2
- [[docs/about/performance|Performance]] — Benchmark results
