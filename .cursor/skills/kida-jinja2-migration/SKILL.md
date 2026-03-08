---
name: kida-jinja2-migration
description: Convert Jinja2 templates to Kida syntax. Use when migrating from Jinja2, Django templates, or similar engines.
---

# Kida Jinja2 Migration

Kida is not a drop-in replacement. Templates must be rewritten. This skill guides the conversion.

## Block Endings: Unified `{% end %}`

Jinja2 uses tag-specific endings. Kida uses one:

| Jinja2 | Kida |
|--------|------|
| `{% endif %}` | `{% end %}` |
| `{% endfor %}` | `{% end %}` |
| `{% endblock %}` | `{% end %}` |
| `{% endmacro %}` | `{% end %}` |

```kida
{% if condition %}...{% end %}
{% for item in items %}...{% end %}
{% block content %}...{% end %}
```

## Imports and Environment

```python
# Before (Jinja2)
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

# After (Kida)
from kida import Environment, FileSystemLoader, Markup
```

## Filter and Test Registration

```python
# Jinja2
env.filters['money'] = format_money
env.tests['prime'] = is_prime

# Kida
env.add_filter('money', format_money)
env.add_test('prime', is_prime)
```

## Scoping: `{% let %}`, `{% set %}`, `{% export %}`

| Keyword | Scope |
|---------|-------|
| `{% set x = ... %}` | Current scope (like Jinja2) |
| `{% let x = ... %}` | Block-local, does not leak out |
| `{% export x = ... %}` | Exports to parent scope |

## Pipeline Operator `|>`

Kida adds `|>` for left-to-right filter chains. Both `|` and `|>` work:

```kida
{{ title |> escape |> upper |> truncate(50) }}
```

## Pattern Matching `{% match %}`

Replace chained `{% if %}`/`{% elif %}` with `{% match %}`:

```kida
{% match status %}
{% case "active" %}<span class="green">Active</span>
{% case "pending" %}<span class="yellow">Pending</span>
{% case _ %}<span>Unknown</span>
{% end %}
```

## Strict Mode

Undefined variables raise `UndefinedError` instead of returning empty string. Use `| default()` for optional values:

```kida
{{ user.nickname | default("Anonymous") }}
```

## New Kida Features

- **`{% cache key %}...{% end %}`** — Built-in block caching
- **Native async** — `{% async for %}`, `{{ await expr }}`
- **Streaming** — `template.render_stream()` for HTMX/SSE

## Common Migration Errors

| Error | Fix |
|-------|-----|
| `ImportError: Markup from markupsafe` | Import `Markup` from `kida` |
| `FilterRegistry does not support item assignment` | Use `env.add_filter(name, func)` |
| `Unexpected tag 'endif'` | Use `{% end %}` not `{% endif %}` |

## Verification

```python
template = env.from_string("Hello, {{ name }}!")
assert template.render(name="World") == "Hello, World!"
```
