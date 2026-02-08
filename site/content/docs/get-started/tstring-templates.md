---
title: T-String Templates
description: Use Python 3.14 t-strings for inline template rendering with auto-escaping
draft: false
weight: 50
lang: en
type: doc
tags:
- tstrings
- pep750
keywords:
- t-strings
- pep 750
- template strings
- inline templates
- k tag
icon: type
---

# T-String Templates

Kida provides the `k` tag for Python 3.14's t-strings (PEP 750), giving you inline template rendering with automatic HTML escaping.

## Quick Example

```python
from kida import k

name = "World"
html = k(t"<h1>Hello, {name}!</h1>")
print(html)
# Output: <h1>Hello, World!</h1>
```

## Auto-Escaping

The `k` tag escapes interpolated values by default, preventing XSS:

```python
from kida import k

user_input = '<script>alert("xss")</script>'
html = k(t"<p>Comment: {user_input}</p>")
print(html)
# Output: <p>Comment: &lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;</p>
```

Values that implement `__html__()` (like Kida's `Markup` class) are trusted and not double-escaped:

```python
from kida import k, Markup

safe_html = Markup("<strong>bold</strong>")
html = k(t"<p>{safe_html}</p>")
print(html)
# Output: <p><strong>bold</strong></p>
```

## When to Use

| Approach | Best For |
|----------|----------|
| `k(t"...")` | Quick inline snippets, string building in Python code |
| `env.from_string(...)` | Dynamic templates with filters, control flow |
| `env.get_template(...)` | File-based templates, inheritance, caching |

T-strings are ideal when you need a few lines of safe HTML without loading a full template:

```python
from kida import k

def render_badge(label: str, color: str) -> str:
    return k(t'<span class="badge badge-{color}">{label}</span>')

def render_user_list(users: list[dict]) -> str:
    items = "".join(
        k(t"<li>{user['name']} ({user['email']})</li>")
        for user in users
    )
    return k(t"<ul>{items}</ul>")
```

## Requirements

T-strings require Python 3.14+ (PEP 750). On earlier Python versions, `k` is `None` and importing it will not raise an error, but calling it will.

```python
from kida import k

if k is not None:
    html = k(t"Hello, {name}!")
else:
    # Fallback for pre-3.14
    from kida import Environment
    env = Environment()
    html = env.render_string("Hello, {{ name }}!", name=name)
```

## See Also

- [[docs/usage/escaping|Escaping]] — HTML escaping and the Markup class
- [[docs/reference/api|API Reference]] — Full `k` tag API
