---
title: T-Strings (PEP 750)
description: Auto-escaping HTML and composable regex via Python 3.14 template strings
draft: false
weight: 20
lang: en
type: doc
tags:
- advanced
- t-strings
- security
keywords:
- t-strings
- PEP 750
- template strings
- auto-escaping
- composable regex
- k tag
- r tag
icon: shield
---

# T-Strings (PEP 750)

Kida ships two t-string tag functions that leverage Python 3.14's native template strings ([PEP 750](https://peps.python.org/pep-0750/)):

| Tag | Purpose | Returns |
|-----|---------|---------|
| `k()` | Auto-escaping HTML interpolation | `str` |
| `r()` | Composable regex with ReDoS validation | `ComposablePattern` |

Both are available from the top-level `kida` package and from `kida.tstring`.

## The `k` Tag — Auto-Escaping HTML

`k()` processes a t-string with automatic HTML escaping. Values are escaped unless they implement the `__html__()` protocol (i.e., they are `Markup` instances).

```python
from kida.tstring import k

name = "<script>alert('xss')</script>"
html = k(t"Hello, {name}!")
# 'Hello, &lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;!'
```

### Safe Content Passes Through

Objects that implement `__html__()` (like `Markup`) are not double-escaped:

```python
from kida import Markup
from kida.tstring import k

safe_html = Markup("<b>Bold</b>")
result = k(t"Content: {safe_html}")
# 'Content: <b>Bold</b>'
```

### Use Cases

- **Server-side rendering** — Build HTML fragments in Python with auto-escaping
- **Email templates** — Quick HTML generation without loading a full template
- **CLI tools** — Generate safe HTML output from user input

```python
from kida.tstring import k

def render_user_card(name: str, bio: str) -> str:
    return k(t"""
        <div class="card">
            <h2>{name}</h2>
            <p>{bio}</p>
        </div>
    """)

# User input is automatically escaped
render_user_card("<script>", "I'm a <b>hacker</b>")
```

## The `r` Tag — Composable Regex

`r()` composes regex patterns safely by wrapping interpolated values in non-capturing groups. This prevents group index collision and quantifier interference.

```python
from kida.tstring import r

NAME = r"[a-zA-Z_][a-zA-Z0-9_]*"
INTEGER = r"\d+"
pattern = r(t"{NAME}|{INTEGER}")
pattern.compile().match("variable_123")
# <re.Match object; span=(0, 12), match='variable_123'>
```

### ComposablePattern

The `r()` tag returns a `ComposablePattern` — a lazy-compiling regex wrapper with safety validation:

```python
from kida.tstring import ComposablePattern

NAME = ComposablePattern(r"[a-zA-Z_][a-zA-Z0-9_]*")
INTEGER = ComposablePattern(r"\d+")

# Compose with | operator
combined = NAME | INTEGER
print(combined.pattern)
# '(?:[a-zA-Z_][a-zA-Z0-9_]*)|(?:\d+)'

# Compile when ready
regex = combined.compile()
regex.match("hello")  # <re.Match object>
```

| Method | Description |
|--------|-------------|
| `pattern` | The raw regex pattern string (property) |
| `compile(flags=0)` | Compile to `re.Pattern` (cached for flags=0) |
| `\|` operator | Combine patterns with alternation |

### ReDoS Validation

Patterns are validated at creation time for known ReDoS-vulnerable constructs (exponential backtracking):

```python
from kida.tstring import ComposablePattern, PatternError

try:
    ComposablePattern(r"(a+)+")  # Nested quantifiers
except PatternError as e:
    print(e)
    # Pattern may be vulnerable to ReDoS (exponential backtracking)
```

Disable validation when you know the pattern is safe:

```python
ComposablePattern(r"(a+)+", validate=False)
```

### Composing with T-Strings

Interpolated values can be strings or `ComposablePattern` instances:

```python
from kida.tstring import r, ComposablePattern

# String interpolation
IDENT = r"[a-zA-Z_]\w*"
STRING = r"'[^']*'"
token = r(t"{IDENT}|{STRING}")

# ComposablePattern interpolation
ident_pat = ComposablePattern(r"[a-zA-Z_]\w*")
string_pat = ComposablePattern(r"'[^']*'")
token = r(t"{ident_pat}|{string_pat}")
```

## API Reference

### Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `k()` | `(template: TemplateProtocol) -> str` | Auto-escaping HTML interpolation |
| `r()` | `(template: TemplateProtocol) -> ComposablePattern` | Safe regex composition |

### Classes

| Class | Description |
|-------|-------------|
| `ComposablePattern` | Lazy-compiling regex with ReDoS validation |
| `PatternError` | Raised for invalid or unsafe patterns |
| `TemplateProtocol` | Protocol for t-string compatibility |

### Import Paths

```python
# From top-level package
from kida import k, r, ComposablePattern

# From tstring module
from kida.tstring import k, r, ComposablePattern, PatternError
```

## See Also

- [[docs/usage/escaping|Escaping]] — HTML auto-escaping in templates
- [[docs/advanced/security|Security]] — Context-specific escaping utilities
- [PEP 750](https://peps.python.org/pep-0750/) — Tag Strings for Writing Domain-Specific Languages
