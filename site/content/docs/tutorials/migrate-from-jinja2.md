---
title: Migrate from Jinja2
description: Switch from Jinja2 to Kida for template rendering
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

Switch from Jinja2 to Kida for faster, safer template rendering.

## Prerequisites

- Python 3.14+
- Existing Jinja2 templates
- Basic understanding of template syntax

## Step 1: Install Kida

```bash
pip install kida
```

## Step 2: Update Imports

**Before (Jinja2):**

```python
from jinja2 import Environment, FileSystemLoader
from jinja2 import Markup
```

**After (Kida):**

```python
from kida import Environment, FileSystemLoader
from kida import Markup
```

## Step 3: Update Environment Creation

**Before (Jinja2):**

```python
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True,
)
```

**After (Kida):**

```python
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True,
)
```

Most Environment options are compatible!

## Step 4: Update Block Endings (Optional)

Kida supports both Jinja2 endings and unified `{% end %}`:

**Jinja2 style (works in Kida):**

```kida
{% if condition %}...{% endif %}
{% for item in items %}...{% endfor %}
```

**Kida style (recommended):**

```kida
{% if condition %}...{% end %}
{% for item in items %}...{% end %}
```

You can migrate gradually—both syntaxes work.

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
```

Or use the decorator:

```python
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
```

Or use the decorator:

```python
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
| `env.filters[name]` | `env.add_filter(name, func)` |
| `env.tests[name]` | `env.add_test(name, func)` |
| `env.globals[name]` | `env.add_global(name, value)` |
| `{% endif %}` | `{% end %}` (or `{% endif %}`) |
| `{% endfor %}` | `{% end %}` (or `{% endfor %}`) |

## Syntax Differences

| Feature | Jinja2 | Kida |
|---------|--------|------|
| Block endings | `{% endif %}`, `{% endfor %}` | Unified `{% end %}` |
| Pipeline | N/A | `{{ x \|> a \|> b }}` |
| Pattern matching | N/A | `{% match %}...{% case %}` |
| Block caching | N/A | `{% cache key %}...{% end %}` |

## New Features to Explore

After migrating, try these Kida features:

### Unified Block Endings

```kida
{% if condition %}
    {% for item in items %}
        {{ item }}
    {% end %}
{% end %}
```

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

After migration, verify:

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

**Fix**: Import from Kida instead:

```python
from kida import Markup  # Not from markupsafe
```

### Filter Registration

**Error**: `TypeError: 'FilterRegistry' object does not support item assignment`

**Fix**: Use `add_filter()` instead of dictionary assignment:

```python
env.add_filter('name', func)  # Not env.filters['name'] = func
```

## Next Steps

- [[docs/syntax/control-flow|Control Flow]] — New pattern matching syntax
- [[docs/about/comparison|Comparison]] — Full Kida vs Jinja2 comparison
- [[docs/about/performance|Performance]] — Benchmark results
