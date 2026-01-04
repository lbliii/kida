---
title: Error Handling
description: Template errors, debugging, and stack traces
draft: false
weight: 40
lang: en
type: doc
tags:
- usage
- debugging
keywords:
- errors
- debugging
- exceptions
- stack traces
icon: alert-triangle
---

# Error Handling

Kida provides clear error messages with source locations.

## Exception Types

| Exception | When Raised |
|-----------|-------------|
| `TemplateError` | Base class for all template errors |
| `TemplateSyntaxError` | Invalid template syntax |
| `TemplateNotFoundError` | Template file not found |
| `UndefinedError` | Accessing undefined variable |

## Syntax Errors

```python
from kida import Environment, TemplateSyntaxError

env = Environment()
try:
    template = env.from_string("{% if x %}")  # Missing end
except TemplateSyntaxError as e:
    print(e)
    # TemplateSyntaxError: Unexpected end of template (expected {% end %})
    # File "<string>", line 1
```

Error messages include:

- Error description
- File name (or `<string>` for from_string)
- Line number
- Relevant source snippet

## Undefined Variables

By default, undefined variables raise `UndefinedError`:

```python
from kida import UndefinedError

template = env.from_string("{{ missing }}")
try:
    html = template.render()
except UndefinedError as e:
    print(e)
    # UndefinedError: Undefined variable 'missing' in <string>:1
```

### Handle Missing Values

Use the `default` filter:

```kida
{{ user.nickname | default("Anonymous") }}
{{ config.timeout | default(30) }}
```

Or check with `is defined`:

```kida
{% if user is defined %}
    {{ user.name }}
{% end %}
```

## Template Not Found

```python
from kida import TemplateNotFoundError

try:
    template = env.get_template("nonexistent.html")
except TemplateNotFoundError as e:
    print(e)
    # TemplateNotFoundError: Template 'nonexistent.html' not found in: templates/
```

## Runtime Errors

Python errors during rendering include template context:

```python
template = env.from_string("{{ items[10] }}")
try:
    html = template.render(items=[1, 2, 3])
except IndexError as e:
    # Traceback shows template location
    pass
```

## Debug Filter

Inspect values during development:

```kida
{{ posts | debug }}
{{ posts | debug("my posts") }}
```

Output (to stderr):

```
DEBUG [my posts]: <list[5]>
  [0] Post(title='First Post', weight=10)
  [1] Post(title='Second', weight=None)  <-- None: weight
  ...
```

## Common Error Patterns

### Missing Variable

```
UndefinedError: Undefined variable 'usre' in page.html:5
```

Fix: Check for typos, ensure variable is passed to render().

### Attribute Error

```
UndefinedError: 'dict' object has no attribute 'nmae'
```

Fix: Check attribute spelling, verify object type.

### Type Error in Filter

```
TypeError: object of type 'NoneType' has no len()
```

Fix: Use `default` filter or check for None.

```kida
{{ items | default([]) | length }}
```

### Template Not Found

```
TemplateNotFoundError: Template 'bsae.html' not found
```

Fix: Check file path, verify loader configuration.

## Error Handling in Production

```python
from kida import TemplateError

def render_page(template_name, **context):
    try:
        return env.render(template_name, **context)
    except TemplateError as e:
        # Log error
        logger.error(f"Template error: {e}")
        # Return fallback
        return env.render("error.html", error=str(e))
```

## Best Practices

### Validate Context

```python
def render_safely(template, **context):
    # Validate required fields
    required = ["title", "user"]
    missing = [k for k in required if k not in context]
    if missing:
        raise ValueError(f"Missing context: {missing}")
    
    return template.render(**context)
```

### Use Default Values

```kida
{# Defensive defaults #}
{{ user.name | default("Guest") }}
{{ items | default([]) | length }}
{{ config.get("timeout", 30) }}
```

### Check Before Access

```kida
{% if user and user.profile %}
    {{ user.profile.bio }}
{% end %}
```

## See Also

- [[docs/troubleshooting/undefined-variable|Undefined Variable]] — Debug undefined errors
- [[docs/troubleshooting/template-not-found|Template Not Found]] — Fix loading issues
- [[docs/reference/api|API Reference]] — Exception classes

