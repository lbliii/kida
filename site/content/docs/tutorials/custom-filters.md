---
title: Build Custom Filters
description: Create custom template filters from scratch
draft: false
weight: 30
lang: en
type: doc
tags:
- tutorial
- filters
- extending
keywords:
- custom filters
- tutorial
- extending
icon: filter
---

# Build Custom Filters

Create custom template filters for domain-specific transformations.

## Prerequisites

- Python 3.14+
- Kida installed
- Basic Python knowledge

## Step 1: Understand Filters

Filters transform values in templates:

```kida
{{ value | filter_name }}
{{ value | filter_name(arg1, arg2) }}
```

A filter is a Python function that takes a value and returns a transformed value.

## Step 2: Create a Simple Filter

```python
from kida import Environment

env = Environment()

# Simple filter: double a number
def double(value):
    return value * 2

env.add_filter("double", double)
```

Use in template:

```kida
{{ 21 | double }}
{# Output: 42 #}
```

## Step 3: Filters with Arguments

```python
def truncate_words(value, count=10, end="..."):
    """Truncate text to a number of words."""
    words = str(value).split()
    if len(words) <= count:
        return value
    return " ".join(words[:count]) + end

env.add_filter("truncate_words", truncate_words)
```

Use in template:

```kida
{{ long_text | truncate_words(5) }}
{{ long_text | truncate_words(10, end="[more]") }}
```

## Step 4: Use the Decorator

```python
@env.filter()
def format_price(value, currency="$", decimals=2):
    """Format a number as currency."""
    return f"{currency}{value:,.{decimals}f}"

@env.filter("money")  # Custom name
def format_money(value):
    return f"${value:,.2f}"
```

## Step 5: Handle None Values

Make filters None-resilient:

```python
@env.filter()
def slugify(value):
    """Convert text to URL slug."""
    if value is None:
        return ""

    import re
    text = str(value).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")
```

## Step 6: Return Markup

For filters that return HTML, use Markup:

```python
from kida import Markup

@env.filter()
def highlight(value, term):
    """Highlight search term in text."""
    if not term or not value:
        return value

    # Escape the text first
    escaped = Markup.escape(str(value))
    term_escaped = Markup.escape(term)

    # Replace with highlighted version
    highlighted = str(escaped).replace(
        term,
        f'<mark>{term_escaped}</mark>'
    )
    return Markup(highlighted)
```

## Complete Examples

### Date Formatting

```python
from datetime import datetime, date

@env.filter()
def format_date(value, format="%B %d, %Y"):
    """Format a date or datetime."""
    if value is None:
        return ""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, (date, datetime)):
        return value.strftime(format)
    return str(value)
```

```kida
{{ post.date | format_date }}
{{ event.time | format_date("%I:%M %p") }}
```

### File Size

```python
@env.filter()
def filesize(value, binary=False):
    """Format bytes as human-readable size."""
    if value is None:
        return "0 B"

    value = float(value)
    base = 1024 if binary else 1000
    suffix = "iB" if binary else "B"

    for unit in ["", "K", "M", "G", "T"]:
        if abs(value) < base:
            return f"{value:.1f} {unit}{suffix}"
        value /= base

    return f"{value:.1f} P{suffix}"
```

```kida
{{ file.size | filesize }}
{{ file.size | filesize(binary=true) }}
```

### Pluralization

```python
@env.filter()
def pluralize(count, singular, plural=None):
    """Return singular or plural form."""
    if plural is None:
        plural = singular + "s"
    return singular if count == 1 else plural
```

```kida
{{ items | length }} {{ items | length | pluralize("item") }}
{# "3 items" or "1 item" #}
```

### JSON Syntax Highlighting

```python
import json
from kida import Markup

@env.filter()
def json_pretty(value, indent=2):
    """Pretty-print JSON with HTML formatting."""
    formatted = json.dumps(value, indent=indent, default=str)
    # Could add syntax highlighting here
    return Markup(f'<pre><code>{Markup.escape(formatted)}</code></pre>')
```

## Testing Filters

```python
def test_format_price():
    env = Environment()

    @env.filter()
    def format_price(value, currency="$"):
        return f"{currency}{value:,.2f}"

    template = env.from_string("{{ amount | format_price }}")
    assert template.render(amount=1234.5) == "$1,234.50"

    template = env.from_string("{{ amount | format_price('€') }}")
    assert template.render(amount=100) == "€100.00"
```

## Best Practices

### Handle Edge Cases

```python
@env.filter()
def safe_divide(value, divisor):
    """Divide with fallback for zero."""
    if divisor == 0:
        return 0
    return value / divisor
```

### Document Your Filters

```python
@env.filter()
def initials(name, separator=""):
    """
    Extract initials from a name.

    Args:
        name: Full name string
        separator: Character between initials

    Returns:
        Initials string (e.g., "JD" for "John Doe")
    """
    if not name:
        return ""
    return separator.join(word[0].upper() for word in name.split() if word)
```

### Keep Filters Pure

Filters should not have side effects:

```python
# ✅ Pure: no side effects
@env.filter()
def double(value):
    return value * 2

# ❌ Impure: modifies state
@env.filter()
def increment_counter(value):
    global counter
    counter += 1  # Side effect!
    return value
```

## Next Steps

- [[docs/extending/custom-filters|Custom Filters Reference]] — Full filter API
- [[docs/reference/filters|Built-in Filters]] — Filter reference
- [[docs/extending/custom-tests|Custom Tests]] — Create test functions
