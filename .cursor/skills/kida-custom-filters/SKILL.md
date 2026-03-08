---
name: kida-custom-filters
description: Add custom Kida filters with proper type coercion. Use when adding filters, extending templates, or handling YAML/config int/str.
---

# Kida Custom Filters

## Registration

```python
env.add_filter("double", double)

# Or decorator
@env.filter()
def double(value):
    return value * 2

@env.filter("twice")  # Custom name
def my_double(value):
    return value * 2
```

## Batch Registration

```python
env.update_filters({"double": lambda x: x * 2, "triple": lambda x: x * 3})
```

## Filter Arguments

```python
@env.filter()
def truncate_words(value, count=10, end="..."):
    words = str(value).split()
    return " ".join(words[:count]) + end if len(words) > count else value
```

```kida
{{ text | truncate_words(5) }}
{{ text | truncate_words(10, end="[more]") }}
```

## Type Coercion for Numeric Params

Values from YAML, config, and cache can arrive as strings. Filters that accept numeric params must coerce at entry to avoid `TypeError`:

```python
def truncate_chars(text: str, length: int = 120) -> str:
    length = int(length) if length is not None else 120
    return text[:length] + "..." if len(text) > length else text
```

Or use a helper:

```python
def coerce_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

@env.filter()
def truncate_words(value, count=30):
    count = coerce_int(count, 30)
    # ...
```

## Returning Markup

For HTML output, return `Markup` to prevent double-escaping:

```python
from kida import Markup

@env.filter()
def bold(value):
    escaped = Markup.escape(str(value))
    return Markup(f"<b>{escaped}</b>")
```

## Handling None

Make filters None-resilient:

```python
@env.filter()
def upper_safe(value):
    return "" if value is None else str(value).upper()
```

## Best Practices

- **Keep filters pure** — no side effects, no global state
- **Coerce numeric params** — YAML/config may pass `"30"` not `30`
- **Handle None** — return sensible default or empty string
- **Return Markup for HTML** — prevents double-escaping
