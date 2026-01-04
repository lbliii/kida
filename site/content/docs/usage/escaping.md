---
title: Escaping
description: HTML escaping and safe content handling
draft: false
weight: 30
lang: en
type: doc
tags:
- usage
- security
keywords:
- escaping
- html
- xss
- markup
- safe
icon: shield
---

# Escaping

Kida auto-escapes output by default to prevent XSS vulnerabilities.

## Autoescape

With `autoescape=True` (default), output is HTML-escaped:

```python
env = Environment(autoescape=True)
template = env.from_string("{{ content }}")
html = template.render(content="<script>alert('xss')</script>")
# Output: &lt;script&gt;alert('xss')&lt;/script&gt;
```

Special characters are replaced:

| Character | Escaped |
|-----------|---------|
| `<` | `&lt;` |
| `>` | `&gt;` |
| `&` | `&amp;` |
| `"` | `&quot;` |
| `'` | `&#x27;` |

## Disable Autoescape

For specific templates:

```python
# Callable autoescape
def should_escape(template_name):
    if template_name is None:
        return True
    return template_name.endswith(".html")

env = Environment(autoescape=should_escape)
```

Globally (not recommended):

```python
env = Environment(autoescape=False)
```

## Safe Filter

Mark content as trusted HTML:

```kida
{{ html_content | safe }}
```

With optional reason for code review:

```kida
{{ cms_block | safe(reason="sanitized by bleach library") }}
{{ admin_html | safe(reason="admin-only content") }}
```

## Markup Class

Create safe HTML in Python:

```python
from kida import Markup

# String marked as safe
safe_html = Markup("<b>Bold</b>")
template.render(content=safe_html)  # Not escaped
```

### Markup Operations

```python
# Concatenation escapes unsafe strings
safe = Markup("<b>")
result = safe + "<script>"  # <b>&lt;script&gt;
result = safe + Markup("<i>")  # <b><i>

# Format escapes arguments
Markup("<p>{}</p>").format("<script>")
# <p>&lt;script&gt;</p>
```

### Escape Function

```python
from kida import Markup

# Escape a string
escaped = Markup.escape("<script>")
# &lt;script&gt;
```

## Common Patterns

### Pre-Sanitized Content

When content is already sanitized:

```python
import bleach

cleaned = bleach.clean(user_html, tags=["b", "i", "a"])
template.render(content=Markup(cleaned))
```

### Rendered Markdown

```python
import markdown

html = markdown.markdown(source)
template.render(content=Markup(html))
```

### HTML in JSON

The `tojson` filter escapes for JavaScript:

```kida
<script>
const data = {{ user_data | tojson }};
</script>
```

## Security Best Practices

### Always Use Autoescape

```python
# ✅ Autoescape on (default)
env = Environment(autoescape=True)

# ❌ Never disable globally
env = Environment(autoescape=False)
```

### Audit `safe` Usage

```kida
{# ✅ Document why it's safe #}
{{ content | safe(reason="sanitized by bleach") }}

{# ❌ Unmarked safe usage #}
{{ user_input | safe }}
```

### Validate Content

```python
# ✅ Sanitize before marking safe
cleaned = bleach.clean(content, tags=ALLOWED_TAGS)
Markup(cleaned)

# ❌ Never mark user input safe directly
Markup(request.form["content"])  # XSS vulnerability!
```

## Escape Filter

Explicitly escape content:

```kida
{{ content | escape }}
{{ content | e }}  {# Short alias #}
```

Useful when autoescape is disabled for a template.

## See Also

- [[docs/reference/filters|Filter Reference]] — escape, safe, striptags
- [[docs/syntax/variables|Variables]] — Output expressions
- [[docs/usage/error-handling|Error Handling]] — Debug template issues

