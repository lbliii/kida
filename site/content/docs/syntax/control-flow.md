---
title: Control Flow
description: Conditionals, loops, and pattern matching in Kida templates
draft: false
weight: 20
lang: en
type: doc
tags:
- syntax
- control-flow
keywords:
- if
- for
- match
- conditionals
- loops
icon: git-branch
---

# Control Flow

## Conditionals

### if / elif / else

```kida
{% if user.is_admin %}
    <span class="badge">Admin</span>
{% elif user.is_moderator %}
    <span class="badge">Mod</span>
{% else %}
    <span class="badge">User</span>
{% end %}
```

Note: Kida uses unified `{% end %}` to close all blocks.

### Inline Conditionals

```kida
{{ "Active" if is_active else "Inactive" }}
```

### Boolean Operators

```kida
{% if user and user.is_active %}
{% if not disabled %}
{% if a or b %}
{% if (a and b) or c %}
```

### Comparison Operators

```kida
{% if count > 0 %}
{% if status == "active" %}
{% if value in allowed_values %}
{% if item is defined %}
```

## Loops

### for Loop

```kida
{% for item in items %}
    <li>{{ item.name }}</li>
{% end %}
```

### Loop with else

The `else` block runs when the sequence is empty:

```kida
{% for item in items %}
    <li>{{ item.name }}</li>
{% else %}
    <li>No items found</li>
{% end %}
```

### Loop Context

Access loop state via the `loop` variable:

```kida
{% for item in items %}
    {{ loop.index }}      {# 1-based index #}
    {{ loop.index0 }}     {# 0-based index #}
    {{ loop.first }}      {# True on first iteration #}
    {{ loop.last }}       {# True on last iteration #}
    {{ loop.length }}     {# Total items #}
    {{ loop.revindex }}   {# Reverse index (1-based) #}
    {{ loop.revindex0 }}  {# Reverse index (0-based) #}
{% end %}
```

### Unpacking

```kida
{% for key, value in data.items() %}
    {{ key }}: {{ value }}
{% end %}

{% for x, y, z in coordinates %}
    Point: ({{ x }}, {{ y }}, {{ z }})
{% end %}
```

### Filtering Items

```kida
{% for user in users if user.is_active %}
    {{ user.name }}
{% end %}
```

## Pattern Matching

Kida adds `{% match %}` for cleaner branching:

```kida
{% match status %}
{% case "active" %}
    ✓ Active
{% case "pending" %}
    ⏳ Pending
{% case "error" %}
    ✗ Error: {{ error_message }}
{% case _ %}
    Unknown status
{% end %}
```

### Match with Guards

```kida
{% match user %}
{% case {"role": "admin"} %}
    Full access
{% case {"role": "user", "verified": true} %}
    Standard access
{% case _ %}
    Limited access
{% end %}
```

## Variables

Kida has three scoping keywords. Understanding the difference is critical when migrating
from Jinja2.

### let

Template-wide variable — visible everywhere after assignment:

```kida
{% let name = "Alice" %}
{% let items = [1, 2, 3] %}
{% let total = price * quantity %}
{{ name }}  → Alice
```

This is the closest equivalent to Jinja2's `{% set %}`.

### set

Block-scoped variable — **does not leak** out of `{% if %}`, `{% for %}`, or other blocks:

```kida
{% let x = "outer" %}
{% if true %}
    {% set x = "inner" %}
    {{ x }}  → inner
{% end %}
{{ x }}  → outer   {# set did not modify the outer variable #}
```

> **Coming from Jinja2?** This is the biggest scoping difference. In Jinja2, `set`
> inside a block modifies the outer variable. In Kida, `set` is block-scoped. Use
> `let` for template-wide variables or `export` to push values out of blocks.

### export / promote

Promotes a variable to the template (outermost) scope — it escapes all nested blocks,
not just the immediate parent:

```kida
{% let total = 0 %}
{% for item in items %}
    {% export total = total + item.price %}
{% end %}
{{ total }}  → sum of all prices
```

`promote` is an alias for `export` — use whichever reads better:

```kida
{% for item in items %}
    {% promote first_item ??= item %}
{% end %}
{{ first_item }}  → first item in the list
```

This replaces Jinja2's `namespace()` pattern for accumulating values inside loops.

> **Note:** `export` / `promote` always writes to the template scope, even from deeply
> nested blocks. An `export` inside an `if` inside a `for` will escape both.

### Nullish Assignment (??=)

Use `??=` to assign only when a variable is undefined or None. Works with all three
scoping keywords:

```kida
{# Set defaults without overwriting existing values #}
{% let title ??= "Untitled" %}
{% let show_sidebar ??= true %}

{# In loops — capture only the first value #}
{% for item in items %}
    {% promote winner ??= item %}
{% end %}
{{ winner }}  → first item (??= is a no-op after that)

{# With context variables — respect what the caller passed #}
{% let page_class ??= "default" %}
```

`??=` checks for both undefined and `None`. It does **not** treat falsy values
like `0`, `""`, or `False` as missing — only `None` and truly undefined variables.

## Whitespace Control

Trim whitespace with `-`:

```kida
{%- if true -%}
    trimmed
{%- end -%}
```

- `{%-` trims whitespace before the tag
- `-%}` trims whitespace after the tag

## See Also

- [[docs/syntax/variables|Variables]] — Output expressions
- [[docs/syntax/filters|Filters]] — Transform values
- [[docs/syntax/functions|Functions]] — Reusable template functions
