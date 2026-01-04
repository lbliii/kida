---
title: Custom Filters
description: Create custom template filters
draft: false
weight: 10
lang: en
type: doc
tags:
- extending
- filters
keywords:
- custom filters
- extending
icon: filter
---

# Custom Filters

Filters transform values in template expressions.

## Basic Filter

```python
from kida import Environment

env = Environment()

def double(value):
    return value * 2

env.add_filter("double", double)
```

Template usage:

```kida
{{ 21 | double }}
{# Output: 42 #}
```

## Decorator Syntax

```python
@env.filter()
def double(value):
    return value * 2

@env.filter("twice")  # Custom name
def my_double(value):
    return value * 2
```

## Filter Arguments

```python
@env.filter()
def truncate_words(value, count=10, end="..."):
    words = str(value).split()
    if len(words) <= count:
        return value
    return " ".join(words[:count]) + end
```

Template usage:

```kida
{{ text | truncate_words(5) }}
{{ text | truncate_words(10, end="[more]") }}
```

## Keyword Arguments

```python
@env.filter()
def format_number(value, decimals=2, separator=","):
    formatted = f"{value:,.{decimals}f}"
    if separator != ",":
        formatted = formatted.replace(",", separator)
    return formatted
```

Template usage:

```kida
{{ price | format_number }}
{{ price | format_number(decimals=0) }}
{{ price | format_number(separator=".") }}
```

## Handling None

Make filters None-resilient:

```python
@env.filter()
def upper_safe(value):
    if value is None:
        return ""
    return str(value).upper()
```

## Returning Markup

For HTML output, return Markup to prevent double-escaping:

```python
from kida import Markup

@env.filter()
def bold(value):
    escaped = Markup.escape(str(value))
    return Markup(f"<b>{escaped}</b>")

@env.filter()
def link(value, url):
    escaped_text = Markup.escape(str(value))
    escaped_url = Markup.escape(str(url))
    return Markup(f'<a href="{escaped_url}">{escaped_text}</a>')
```

## Batch Registration

```python
filters = {
    "double": lambda x: x * 2,
    "triple": lambda x: x * 3,
    "reverse": lambda x: x[::-1],
}

env.update_filters(filters)
```

## Common Patterns

### Currency Formatting

```python
@env.filter()
def currency(value, symbol="$", decimals=2):
    if value is None:
        return ""
    return f"{symbol}{value:,.{decimals}f}"
```

### Date Formatting

```python
from datetime import datetime

@env.filter()
def format_date(value, pattern="%Y-%m-%d"):
    if value is None:
        return ""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(pattern)
```

### Text Slugification

```python
import re

@env.filter()
def slugify(value):
    if value is None:
        return ""
    text = str(value).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")
```

### Pluralization

```python
@env.filter()
def pluralize(count, singular, plural=None):
    if plural is None:
        plural = singular + "s"
    return singular if count == 1 else plural
```

Usage:

```kida
{{ items | length }} {{ items | length | pluralize("item") }}
```

## Best Practices

### Keep Filters Pure

```python
# ✅ Pure: no side effects
@env.filter()
def process(value):
    return value.upper()

# ❌ Impure: modifies external state
counter = 0
@env.filter()
def count_calls(value):
    global counter
    counter += 1  # Side effect
    return value
```

### Handle Edge Cases

```python
@env.filter()
def safe_divide(value, divisor):
    if divisor == 0:
        return 0  # Or raise error
    return value / divisor
```

### Document Filters

```python
@env.filter()
def initials(name, separator=""):
    """
    Extract initials from a name.
    
    Args:
        name: Full name string
        separator: Character between initials
    
    Returns:
        Initials (e.g., "JD" for "John Doe")
    """
    if not name:
        return ""
    return separator.join(
        word[0].upper() for word in name.split() if word
    )
```

## See Also

- [[docs/reference/filters|Built-in Filters]] — All built-in filters
- [[docs/tutorials/custom-filters|Custom Filters Tutorial]] — Step-by-step guide
- [[docs/syntax/filters|Filter Syntax]] — Using filters in templates

