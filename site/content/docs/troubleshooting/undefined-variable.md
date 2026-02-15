---
title: Undefined Variable
description: Debug undefined variable errors
draft: false
weight: 10
lang: en
type: doc
tags:
- troubleshooting
- errors
keywords:
- undefined
- error
- variable
icon: alert-circle
---

# Undefined Variable

Debug `UndefinedError` exceptions.

## The Error

```
UndefinedError: Undefined variable 'usre' in page.html:5
```

## Common Causes

:::{dropdown} Typo in variable name
:icon: spell-check

```kida
{# ❌ Typo #}
{{ usre.name }}

{# ✅ Correct #}
{{ user.name }}
```

Check spelling against what's passed to `render()`.
:::

:::{dropdown} Variable not passed to template
:icon: plug

```python
# ❌ Missing variable
template.render(title="Hello")

# ✅ Include all needed variables
template.render(title="Hello", user=current_user)
```

Ensure all template variables are passed in `render()`.
:::

:::{dropdown} Wrong attribute name
:icon: tag

```kida
{# ❌ Wrong attribute #}
{{ user.nmae }}

{# ✅ Correct attribute #}
{{ user.name }}
```

Verify object attributes match your code.
:::

:::{dropdown} Nested object is None
:icon: layers

```kida
{# ❌ parent might be None #}
{{ page.parent.title }}

{# ✅ Check first #}
{% if page.parent %}
    {{ page.parent.title }}
{% end %}
```

Use conditional checks or `default` filter.
:::

## Solutions

### Use default Filter

```kida
{{ user.nickname | default("Anonymous") }}
{{ config.timeout | default(30) }}
```

### Check with is defined

The `is defined` test works on attribute chains, not just top-level variables. If any part of the chain is missing, the result is `undefined`:

```kida
{% if user is defined %}
    {{ user.name }}
{% else %}
    Guest
{% end %}
```

#### Attribute Chains

```kida
{# Checks if pokemon has a "name" attribute — not just if pokemon exists #}
{% if pokemon.name is defined %}
    {{ pokemon.name }}
{% end %}

{# Works with dict keys too #}
{% if settings.theme is defined %}
    Theme: {{ settings.theme }}
{% end %}

{# Deep chains #}
{% if page.author.avatar is defined %}
    <img src="{{ page.author.avatar }}">
{% end %}
```

#### Undefined Sentinel

Missing attribute access returns an `_Undefined` sentinel (not an empty string). The sentinel is:

- **Falsy** — `{% if pokemon.name %}` works as a guard
- **Stringifies to `""`** — `{{ pokemon.name }}` renders nothing when undefined
- **Iterable** — yields nothing, so `{% for x in missing_attr %}` produces no output

The `is defined` and `is undefined` tests work correctly on attribute chains (e.g. `{% if pokemon.name is defined %}`), making intent explicit. See [[docs/reference/tests|Tests Reference]] for the full test list.

### Optional Chaining Pattern

```kida
{% if post and post.author %}
    {{ post.author.name }}
{% end %}
```

### Safe Navigation

```kida
{{ user | default({}) | attr("name") | default("Unknown") }}
```

## Debug Tips

### Print Available Variables

```python
# In Python
print(context.keys())
```

### Use debug Filter

```kida
{{ user | debug }}
```

Output (to stderr):

```
DEBUG: <User>
  .name = 'Alice'
  .email = 'alice@example.com'
```

### Check Template Context

```python
def render_debug(template_name, **context):
    print(f"Rendering {template_name}")
    print(f"Context keys: {list(context.keys())}")
    return env.render(template_name, **context)
```

## Prevention

### Type Hints for Context

```python
from dataclasses import dataclass

@dataclass
class PageContext:
    title: str
    user: User
    items: list[Item]

# IDE will catch missing fields
context = PageContext(title="Hello", user=user, items=items)
template.render(**asdict(context))
```

### Template Validation

```python
def validate_context(context, required):
    missing = [k for k in required if k not in context]
    if missing:
        raise ValueError(f"Missing: {missing}")
```

## See Also

- [[docs/usage/error-handling|Error Handling]] — Exception types
- [[docs/syntax/variables|Variables]] — Variable access patterns
- [[docs/reference/filters|Filters]] — The default filter
