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

:::{dropdown} Nested object is None or missing
:icon: layers

```kida
{# ❌ page.parent might be None or missing #}
{{ page.parent.title }}

{# ✅ Guard with `is defined` (works for attribute chains) #}
{% if page.parent is defined and page.parent %}
    {{ page.parent.title }}
{% end %}

{# ✅ Or use the null-coalescing operator #}
{{ page.parent.title ?? "" }}
```

Under strict mode (the default), `{% if page.parent %}` alone raises if `parent` is missing — use `is defined` or `??`.
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

#### Undefined Sentinel (lenient mode only)

With `strict_undefined=False` (opt-in), missing attribute access returns an `_Undefined` sentinel. The sentinel is:

- **Falsy** — `{% if pokemon.name %}` works as a guard
- **Stringifies to `""`** — `{{ pokemon.name }}` renders nothing when undefined
- **Iterable** — yields nothing, so `{% for x in missing_attr %}` produces no output

Under the default **strict mode**, missing attributes raise `UndefinedError`. Use `is defined`, `??`, or `| default(...)` to opt specific sites into lenient behavior. See [[docs/reference/tests|Tests Reference]] for the full test list.

### Optional Chaining Pattern

```kida
{% if post is defined and post.author is defined %}
    {{ post.author.name }}
{% end %}
```

### Safe Navigation

```kida
{{ user.name ?? "Unknown" }}
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

## Strict Mode (Default)

As of 0.7.0, `strict_undefined=True` is the default. Missing variables **and** missing attributes raise `UndefinedError` with a descriptive message distinguishing variable, attribute, and key lookups.

```python
env = Environment(loader=FileSystemLoader("templates/"))
# strict_undefined=True by default
```

To guard optional access within a template, use one of:

```kida
{{ user.nickname ?? "Anonymous" }}              {# null-coalescing #}
{{ user.nickname | default("Anonymous") }}       {# default filter #}
{% if user.nickname is defined %}...{% end %}    {# explicit test #}
```

### Opt Out (Lenient Mode)

If you are porting templates that rely on silent empty-string fallback for missing attributes:

```python
env = Environment(
    loader=FileSystemLoader("templates/"),
    strict_undefined=False,
)
```

In lenient mode, missing attributes return an `_Undefined` sentinel (see above). This is recommended only as a transitional shim — prefer fixing sites with the idioms above.

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
