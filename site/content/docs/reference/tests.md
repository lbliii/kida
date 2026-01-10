---
title: Tests Reference
description: All built-in tests with examples
draft: false
weight: 30
lang: en
type: doc
tags:
- reference
- tests
keywords:
- tests
- reference
- conditionals
icon: check-circle
---

# Tests Reference

Tests are boolean predicates used with `is` in conditionals.

## Usage

```kida
{% if value is test %}
{% if value is test(arg) %}
{% if value is not test %}
```

---

## Type Tests

### defined

Value is not None.

```kida
{% if user is defined %}
    {{ user.name }}
{% end %}
```

### undefined

Value is None.

```kida
{% if user is undefined %}
    <p>Not logged in</p>
{% end %}
```

### none

Value is None (alias for undefined).

```kida
{% if value is none %}
```

### string

Value is a string.

```kida
{% if value is string %}
    {{ value | upper }}
{% end %}
```

### number

Value is int or float (not bool).

```kida
{% if value is number %}
    {{ value * 2 }}
{% end %}
```

### sequence

Value is list, tuple, or string.

```kida
{% if items is sequence %}
    {{ items | length }} items
{% end %}
```

### mapping

Value is a dict.

```kida
{% if data is mapping %}
    {{ data.keys() | list }}
{% end %}
```

### iterable

Value supports iteration.

```kida
{% if items is iterable %}
    {% for item in items %}...{% end %}
{% end %}
```

### callable

Value is callable.

```kida
{% if func is callable %}
    {{ func() }}
{% end %}
```

---

## Boolean Tests

### true

Value is exactly True.

```kida
{% if flag is true %}
    Enabled
{% end %}
```

### false

Value is exactly False.

```kida
{% if flag is false %}
    Disabled
{% end %}
```

---

## Number Tests

### odd

Integer is odd.

```kida
{% if loop.index is odd %}
    <tr class="odd">
{% end %}
```

### even

Integer is even.

```kida
{% if loop.index is even %}
    <tr class="even">
{% end %}
```

### divisibleby

Integer is divisible by N.

```kida
{% if count is divisibleby(3) %}
    Multiple of 3
{% end %}
```

---

## Comparison Tests

### eq / equalto

Equal to value.

```kida
{% if status is eq("active") %}
{% if count is equalto(0) %}
```

### ne

Not equal to value.

```kida
{% if status is ne("deleted") %}
```

### lt / lessthan

Less than value.

```kida
{% if count is lt(10) %}
{% if age is lessthan(18) %}
```

### le

Less than or equal.

```kida
{% if score is le(100) %}
```

### gt / greaterthan

Greater than value.

```kida
{% if count is gt(0) %}
{% if age is greaterthan(21) %}
```

### ge

Greater than or equal.

```kida
{% if level is ge(5) %}
```

### sameas

Identity comparison (is).

```kida
{% if a is sameas(b) %}
    Same object
{% end %}
```

### in

Value is in sequence.

```kida
{% if role is in(["admin", "moderator"]) %}
    Has permissions
{% end %}
```

---

## String Tests

### lower

String is all lowercase.

```kida
{% if text is lower %}
    Already lowercase
{% end %}
```

### upper

String is all uppercase.

```kida
{% if text is upper %}
    Already uppercase
{% end %}
```

### match

String matches regex pattern.

```kida
{% if email is match(".*@.*\\..*") %}
    Valid email format
{% end %}
```

---

## Negation

Use `is not` to negate any test:

```kida
{% if value is not defined %}
{% if count is not even %}
{% if user is not none %}
{% if status is not eq("active") %}
```

---

## Examples

### Type Checking

```kida
{% if data is mapping %}
    {% for key, value in data.items() %}
        {{ key }}: {{ value }}
    {% end %}
{% elif data is sequence %}
    {% for item in data %}
        {{ item }}
    {% end %}
{% elif data is string %}
    {{ data }}
{% end %}
```

### Loop Styling

```kida
<table>
{% for row in data %}
    <tr class="{% if loop.index is odd %}odd{% else %}even{% end %}">
        <td>{{ row.name }}</td>
    </tr>
{% end %}
</table>
```

### Permission Checks

```kida
{% if user is defined %}
    {% if user.role is in(["admin", "moderator"]) %}
        {% include "admin-toolbar.html" %}
    {% end %}
{% end %}
```

### Pagination

```kida
{% if page is gt(1) %}
    <a href="?page={{ page - 1 }}">Previous</a>
{% end %}

{% if page is lt(total_pages) %}
    <a href="?page={{ page + 1 }}">Next</a>
{% end %}
```

## See Also

- [[docs/syntax/control-flow|Control Flow]] — Conditionals and loops
- [[docs/extending/custom-tests|Custom Tests]] — Create tests
