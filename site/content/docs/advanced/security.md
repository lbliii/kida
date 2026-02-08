---
title: Security Hardening
description: Context-specific escaping, URL validation, and attribute safety
draft: false
weight: 50
lang: en
type: doc
tags:
- advanced
- security
keywords:
- security
- escaping
- javascript
- css
- url validation
- xss
- event handlers
- attribute validation
icon: shield
---

# Security Hardening

Beyond HTML auto-escaping, Kida provides context-specific escaping utilities for framework authors who need to embed user data in JavaScript, CSS, and URL contexts safely.

All functions are O(n) single-pass with no regex in the hot path and no ReDoS risk.

```python
from kida.utils.html import js_escape, css_escape, url_is_safe, safe_url, xmlattr
```

## Context-Specific Escaping

HTML escaping alone isn't enough when embedding values in different contexts. Each context has different dangerous characters:

| Context | Function | Danger |
|---------|----------|--------|
| HTML content | `html_escape()` | `<`, `>`, `&`, `"`, `'` break markup |
| JavaScript strings | `js_escape()` | `"`, `'`, `` ` ``, `\n`, `</script>` break string literals |
| CSS values | `css_escape()` | `(`, `)`, `\`, `<` enable injection |
| URL attributes | `url_is_safe()` | `javascript:`, `data:` execute code |

### JavaScript Escaping

Use `js_escape()` when embedding user data inside JavaScript string literals:

```python
from kida.utils.html import js_escape

user_input = 'Hello "World" </script><script>alert(1)'
safe = js_escape(user_input)
# 'Hello \\"World\\" \\x3c\\/script\\x3e\\x3cscript\\x3ealert(1)'
```

What it escapes:
- String delimiters: `"`, `'`, `` ` `` (template literals)
- Template literal interpolation: `$` (prevents `${...}` injection)
- Newlines: `\n`, `\r`, `\t`
- Script-breaking: `<`, `>`, `/` (prevents `</script>` breakout)
- Line separators: `U+2028`, `U+2029` (break JS strings)
- NUL bytes: `\x00` (bypass attempts)

```python
# Safe to embed in inline scripts
html = f'<script>var name = "{js_escape(user_input)}";</script>'
```

> **Warning**: `js_escape()` is for string literals only. For JSON data, use `json.dumps()`. For numeric values, validate with `int()` or `float()`.

### JSString

Wrap escaped values to prevent accidental double-escaping:

```python
from kida.utils.html import js_escape, JSString

safe = JSString(js_escape(user_input))
# Type-safe marker, similar to Markup for HTML
```

### CSS Escaping

Use `css_escape()` when embedding values in CSS property values:

```python
from kida.utils.html import css_escape

user_color = 'red; background: url(javascript:alert(1))'
safe = css_escape(user_color)
# 'red; background: url\\(javascript:alert\\(1\\)\\)'
```

What it escapes: `\`, `"`, `'`, `(`, `)`, `/`, `<`, `>`, `&`, NUL bytes.

## URL Validation

### url_is_safe

Check if a URL has a safe protocol scheme before using it in `href` or `src` attributes:

```python
from kida.utils.html import url_is_safe

url_is_safe("https://example.com")       # True
url_is_safe("/path/to/page")             # True (relative)
url_is_safe("javascript:alert(1)")       # False
url_is_safe("  javascript:alert(1)  ")   # False (whitespace stripped)
url_is_safe("data:text/html,<h1>Hi</h1>")  # False (by default)
url_is_safe("data:image/png;base64,...", allow_data=True)  # True
```

Safe schemes: `http`, `https`, `mailto`, `tel`, `ftp`, `ftps`, `sms`.

The function uses window-based parsing (O(n) single pass, no regex) and strips NUL bytes before validation.

### safe_url

Return a fallback value when a URL is unsafe:

```python
from kida.utils.html import safe_url

safe_url("https://example.com")        # 'https://example.com'
safe_url("javascript:alert(1)")        # '#'
safe_url("javascript:void(0)", fallback="/home")  # '/home'
```

## Attribute Validation

### xmlattr

Convert a dictionary to HTML attributes with validation and escaping:

```python
from kida.utils.html import xmlattr

attrs = xmlattr({"class": "btn primary", "data-id": "123", "disabled": True})
# Markup('class="btn primary" data-id="123" disabled="True"')
```

`None` values are skipped:

```python
xmlattr({"class": "btn", "id": None})
# Markup('class="btn"')
```

### Event Handler Detection

By default, `xmlattr()` warns when it encounters event handler attributes (potential XSS vectors):

```python
xmlattr({"onclick": "handleClick()"})
# UserWarning: Event handler attribute 'onclick' can execute JavaScript.
```

Kida tracks 84 event handler attributes from the WHATWG HTML Living Standard, including mouse, keyboard, focus, form, drag, clipboard, media, pointer, animation, and transition events.

Control the behavior:

```python
# Suppress warnings (you've verified the handlers are safe)
xmlattr({"onclick": "handler()"}, allow_events=True)

# Automatically strip event handlers
xmlattr({"onclick": "handler()", "class": "btn"}, strip_events=True)
# Markup('class="btn"')
```

### Attribute Name Validation

Attribute names are validated per the HTML5 spec. Invalid names (containing whitespace, NUL, quotes, `>`, `/`, `=`) are rejected:

```python
# Strict mode (default) — raises ValueError
xmlattr({"invalid name": "value"})  # ValueError

# Lenient mode — skips with warning
xmlattr({"invalid name": "value"}, strict=False)  # Markup('')
```

## NUL Byte Stripping

All escaping functions strip `\x00` (NUL) bytes. NUL bytes can be used to bypass filters in some contexts:

```python
from kida.utils.html import html_escape

html_escape("safe\x00<script>")
# 'safe&lt;script&gt;'  (NUL removed, script escaped)
```

## format_html

A convenience function for building HTML with escaped arguments:

```python
from kida.utils.html import format_html

html = format_html("<p>Hello, {name}!</p>", name="<script>")
# Markup('<p>Hello, &lt;script&gt;!</p>')

html = format_html("<a href='{url}'>{text}</a>", url="/page", text="<Click>")
# Markup("<a href='/page'>&lt;Click&gt;</a>")
```

> **Warning**: The format string itself is **not** escaped. Only use with trusted format strings.

## API Reference

| Function | Signature | Description |
|----------|-----------|-------------|
| `js_escape()` | `(value: Any) -> str` | JavaScript string literal escaping |
| `css_escape()` | `(value: Any) -> str` | CSS property value escaping |
| `url_is_safe()` | `(url: str, *, allow_data: bool = False) -> bool` | Protocol scheme validation |
| `safe_url()` | `(url: str, *, fallback: str = "#") -> str` | Safe URL with fallback |
| `xmlattr()` | `(value: dict, *, allow_events, strip_events, strict) -> Markup` | Dict to HTML attributes |
| `format_html()` | `(format_string: str, *args, **kwargs) -> Markup` | HTML formatting with escaping |
| `JSString` | class | Safe string marker for JS context |

All functions are importable from `kida.utils.html`.

## See Also

- [[docs/usage/escaping|Escaping]] — HTML auto-escaping in templates
- [[docs/advanced/t-strings|T-Strings]] — Auto-escaping with PEP 750
- [[docs/reference/filters|Filter Reference]] — `escape`, `safe`, `tojson` filters
