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
| `k(t"...")` | Quick inline HTML snippets with auto-escaping |
| `plain(t"...")` | Non-HTML string assembly (logs, errors, terminal output) |
| `env.from_string(...)` | Dynamic templates with filters, control flow |
| `env.get_template(...)` | File-based templates, inheritance, caching |

> **Performance note:** `k()` and `plain()` are ~1.5-4x slower than equivalent f-strings
> due to PEP 750 `Interpolation` object overhead. Use them when you need auto-escaping
> (`k`) or t-string composability (`plain`), not as a general f-string replacement.
> See [T-Strings (PEP 750)]({{< relref "/docs/advanced/t-strings#performance-t-strings-vs-f-strings" >}}) for benchmark data.

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

## The `plain` Tag

For non-HTML contexts where escaping is unwanted, use `plain()`:

```python
from kida import plain

user = "<admin>"
msg = plain(t"Logged in: {user}")
# 'Logged in: <admin>'  — no escaping
```

`plain()` supports conversion specs (`!r`, `!s`, `!a`) and format specs (`:>3`, `:.2f`). See [T-Strings (PEP 750)]({{< relref "/docs/advanced/t-strings#the-plain-tag--no-escape-concatenation" >}}) for details.

## Requirements

T-strings require Python 3.14+ (PEP 750). On earlier Python versions, `k` and `plain` are `None` and importing them will not raise an error, but calling them will.

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

- [[docs/advanced/t-strings|T-Strings (PEP 750)]] — Full reference for `k()`, `plain()`, and `r()` tags, plus performance data
- [[docs/usage/escaping|Escaping]] — HTML escaping and the Markup class
- [[docs/reference/api|API Reference]] — Full `k` tag API
