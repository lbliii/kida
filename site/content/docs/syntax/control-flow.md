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

### set

Assign a variable in the current scope:

```kida
{% set name = "Alice" %}
{% set items = [1, 2, 3] %}
{% set total = price * quantity %}
```

### let

Block-scoped variable (new in Kida):

```kida
{% let temp = calculate_value() %}
{{ temp }}
{% end %}
{# temp is not accessible here #}
```

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
