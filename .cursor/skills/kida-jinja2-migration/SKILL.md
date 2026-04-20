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
| `{% macro name(...) %}` | `{% def name(...) %}` (Kida has no `{% macro %}` keyword) |
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
| `{% let x = ... %}` | Template-wide (like Jinja2's `set`) |
| `{% set x = ... %}` | Block-scoped — does **not** leak out of `{% if %}`, `{% for %}`, etc. |
| `{% export x = ... %}` | Promotes variable to template (outermost) scope; escapes multiple nested blocks |

> **⚠ Key difference from Jinja2:** In Jinja2, `{% set %}` inside `{% if %}` modifies
> the outer variable. In Kida, `{% set %}` is block-scoped — the value stays inside the
> block. Use `{% let %}` for template-wide variables, or `{% export %}` to push a value
> out of a block into the template scope (it can cross multiple nested blocks).
>
> ```kida
> {# Kida: set is block-scoped #}
> {% let name = "outer" %}
> {% if true %}
>     {% set name = "inner" %}  {# does NOT change the outer 'name' #}
> {% end %}
> {{ name }}  → outer
>
> {# To modify outer scope from inside a block, use export: #}
> {% if true %}
>     {% export name = "inner" %}
> {% end %}
> {{ name }}  → inner
> ```

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

## Strict Mode (Undefined Variables)

Kida raises `UndefinedError` for any undefined variable — it never silently returns an empty
string like Jinja2. This is the default and cannot be disabled.

```kida
{# This raises UndefinedError if 'nickname' is not in the context #}
{{ nickname }}

{# Use | default() for optional values #}
{{ nickname | default("Anonymous") }}

{# Use 'is defined' test for conditional logic #}
{% if nickname is defined %}
    Hello, {{ nickname }}
{% end %}
```

> **Migration tip:** Audit every variable in your Jinja2 templates. Any variable that
> might not be passed to `render()` needs `| default(...)` or an `is defined` guard.

## New Kida Features

- **`{% cache key %}...{% end %}`** — Built-in block caching
- **Native async** — `{% async for %}`, `{{ await expr }}`
- **Streaming** — `template.render_stream()` for HTMX/SSE

## No `namespace()` Support

Jinja2's `namespace()` object does not exist in Kida. Use the scoping keywords instead:

| Jinja2 pattern | Kida equivalent |
|---------------|-----------------|
| `{% set ns = namespace(count=0) %}` | `{% let count = 0 %}` |
| `{% set ns.count = ns.count + 1 %}` (inside loop) | `{% export count = count + 1 %}` |

## `format` Filter Uses `str.format()`

The `format` filter uses Python's `str.format()` with `{}` placeholders — **not** `%`-style:

```kida
{# Correct — str.format() style #}
{{ "Hello, {}!" | format(name) }}
{{ "{:.2f}" | format(price) }}

{# WRONG — %-style will raise an error #}
{{ "%.2f" | format(price) }}
```

For numeric formatting, prefer the dedicated filters:

```kida
{{ price | decimal(2) }}           → 19.99
{{ amount | format_number(2) }}    → 1,234.57
```

## Common Migration Errors

| Error | Fix |
|-------|-----|
| `ImportError: Markup from markupsafe` | Import `Markup` from `kida` |
| `FilterRegistry does not support item assignment` | Use `env.add_filter(name, func)` |
| `Unexpected tag 'endif'` | Use `{% end %}` not `{% endif %}` |
| `UndefinedError: Undefined variable 'varname' in <template>:<line>` | Add `| default("")` or pass it to `render()` |
| `format filter uses str.format()` | Use `{}` placeholders, not `%s`/`%.2f` |
| `Unknown icon 'arrow'` | Use directional variant: `icons.arrow_r`, `arrow_l`, `arrow_u`, `arrow_d` |
| Variable doesn't update outside `{% if %}` | `{% set %}` is block-scoped — use `{% let %}` or `{% export %}` |

## Verification

```python
template = env.from_string("Hello, {{ name }}!")
assert template.render(name="World") == "Hello, World!"
```
