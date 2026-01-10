---
title: Custom Tests
description: Create custom test functions for conditionals
draft: false
weight: 20
lang: en
type: doc
tags:
- extending
- tests
keywords:
- custom tests
- extending
- is
icon: check-circle
---

# Custom Tests

Tests are boolean predicates used with `is` in conditionals.

## Basic Test

```python
from kida import Environment

env = Environment()

def is_positive(value):
    return value > 0

env.add_test("positive", is_positive)
```

Template usage:

```kida
{% if count is positive %}
    {{ count }} items
{% end %}
```

## Decorator Syntax

```python
@env.test()
def is_even(value):
    return value % 2 == 0

@env.test("prime")  # Custom name
def is_prime_number(n):
    return n > 1 and all(n % i for i in range(2, int(n**0.5) + 1))
```

Template usage:

```kida
{% if number is even %}
{% if 17 is prime %}
```

## Tests with Arguments

```python
@env.test()
def divisible_by(value, divisor):
    return value % divisor == 0

@env.test()
def between(value, min_val, max_val):
    return min_val <= value <= max_val
```

Template usage:

```kida
{% if count is divisible_by(3) %}
{% if score is between(0, 100) %}
```

## Negation

Use `is not` to negate tests:

```kida
{% if count is not even %}
{% if user is not defined %}
```

## Built-in Tests

| Test | Description |
|------|-------------|
| `defined` | Value is not None |
| `undefined` | Value is None |
| `none` | Value is None |
| `even` | Integer is even |
| `odd` | Integer is odd |
| `number` | Value is int or float |
| `string` | Value is a string |
| `sequence` | Value is list/tuple/string |
| `mapping` | Value is a dict |
| `iterable` | Value supports iteration |
| `callable` | Value is callable |

## Common Patterns

### Type Tests

```python
@env.test()
def is_list(value):
    return isinstance(value, list)

@env.test()
def is_dict(value):
    return isinstance(value, dict)

@env.test()
def is_empty(value):
    if value is None:
        return True
    try:
        return len(value) == 0
    except TypeError:
        return False
```

### Value Tests

```python
@env.test()
def is_blank(value):
    """Test if value is None, empty, or whitespace-only."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return len(value) == 0
    except TypeError:
        return False

@env.test()
def is_in_range(value, start, end):
    return start <= value <= end
```

### Object Tests

```python
@env.test()
def is_admin(user):
    return getattr(user, "role", None) == "admin"

@env.test()
def is_published(post):
    return getattr(post, "status", None) == "published"

@env.test()
def has_children(page):
    children = getattr(page, "children", None)
    return bool(children)
```

### String Tests

```python
@env.test()
def is_email(value):
    import re
    pattern = r'^[\w.-]+@[\w.-]+\.\w+$'
    return bool(re.match(pattern, str(value)))

@env.test()
def is_url(value):
    return str(value).startswith(("http://", "https://"))

@env.test()
def contains(value, substring):
    return substring in str(value)
```

## Batch Registration

```python
tests = {
    "positive": lambda x: x > 0,
    "negative": lambda x: x < 0,
    "zero": lambda x: x == 0,
}

env.update_tests(tests)
```

## Best Practices

### Return Boolean

```python
# ✅ Returns boolean
@env.test()
def is_valid(value):
    return bool(validate(value))

# ❌ Returns non-boolean
@env.test()
def is_valid(value):
    return validate(value)  # Might return None
```

### Handle None

```python
@env.test()
def is_active(value):
    if value is None:
        return False
    return getattr(value, "is_active", False)
```

### Descriptive Names

```python
# ✅ Clear purpose
@env.test()
def has_permission(user, permission):
    return permission in getattr(user, "permissions", [])

# ❌ Vague
@env.test()
def check(value, x):
    ...
```

## See Also

- [[docs/reference/tests|Built-in Tests]] — All built-in tests
- [[docs/syntax/control-flow|Control Flow]] — Using tests in conditionals
- [[docs/extending/custom-filters|Custom Filters]] — Transform values
