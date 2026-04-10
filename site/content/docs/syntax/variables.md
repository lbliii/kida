---
title: Variables
description: Output expressions and variable access in Kida templates
draft: false
weight: 10
lang: en
type: doc
tags:
- syntax
- variables
keywords:
- variables
- expressions
- output
icon: variable
---

# Variables

## Basic Output

Use double braces to output expressions:

```kida
{{ name }}
{{ user.email }}
{{ items[0] }}
{{ 1 + 2 }}
```

## Attribute Access

Access object attributes with dot notation:

```kida
{{ user.name }}
{{ page.metadata.title }}
```

For dictionary keys:

```kida
{{ data.key }}
{{ data["key-with-dashes"] }}
```

### Dict-Safe Resolution

For **dict** objects, dot notation resolves to dictionary keys first, then falls back to attributes. This means `{{ data.items }}` returns `data["items"]` (your data), not the `dict.items` method:

```kida
{# data = {"items": ["a", "b"], "keys": ["x", "y"]} #}

{{ data.items }}    {# → ["a", "b"] — the key, not dict.items() #}
{{ data.keys }}     {# → ["x", "y"] — the key, not dict.keys() #}
```

For non-dict objects (dataclasses, custom classes), dot notation uses `getattr` first, then falls back to subscript. This is the safe default for objects with `__getitem__`.

> **Jinja2 difference**: Jinja2 always tries `getattr` first regardless of type, so `{{ data.items }}` resolves to the `dict.items` method. Kida handles this correctly for dicts.

## Index Access

Access sequence items by index:

```kida
{{ items[0] }}
{{ items[-1] }}  {# Last item #}
{{ matrix[0][1] }}
```

## HTML Escaping

By default, output is HTML-escaped for security:

```kida
{{ "<script>" }}
```

Output: `&lt;script&gt;`

### Mark Content as Safe

Use the `safe` filter for trusted HTML:

```kida
{{ html_content | safe }}
```

Or with an optional reason for code review:

```kida
{{ cms_block | safe(reason="sanitized by bleach") }}
```

## Pipelines

Chain filters with the pipe operator:

```kida
{{ name | upper }}
{{ title | escape | truncate(50) }}
```

Use the pipeline operator `|>` for improved readability:

```kida
{{ title |> escape |> upper |> truncate(50) }}
```

Both syntaxes are equivalent:

```kida
{# Traditional pipe #}
{{ items | sort(attribute='date') | first }}

{# Pipeline operator #}
{{ items |> sort(attribute='date') |> first }}
```

### Safe Pipeline

Use `?|>` for None-propagating pipelines. If the value is None, the entire chain
short-circuits instead of erroring:

```kida
{# Without ?|> — errors if user.name is None #}
{{ user.name |> upper |> trim }}

{# With ?|> — safely returns None, then ?? provides fallback #}
{{ user?.name ?|> upper ?|> trim ?? "Anonymous" }}
```

This composes naturally with optional chaining (`?.`) and null coalescing (`??`).

### Optional Filter

Use `?|` to skip a filter when the value is None:

```kida
{# Errors if value is None #}
{{ value | upper }}

{# Safely skips — returns None, then ?? provides fallback #}
{{ value ?| upper ?? "N/A" }}

{# Chain multiple optional filters #}
{{ config?.debug ?| string ?? "unset" }}
```

`?|` works like `|` but checks for None before applying the filter. Use it
anywhere you'd write `| default("") | filter` — it's cleaner and doesn't
swallow falsy values like `0` or `""`.

## Default Values

Handle missing or None values:

```kida
{{ user.nickname | default("Anonymous") }}
{{ count | default(0) }}
```

Shorthand `d` alias:

```kida
{{ missing | d("fallback") }}
```

## Expressions

Full Python expressions are supported:

```kida
{{ price * 1.1 }}
{{ "Hello, " + name }}
{{ items | length > 0 }}
{{ value if condition else fallback }}
```

## String Literals

Use single or double quotes:

```kida
{{ "Hello" }}
{{ 'World' }}
{{ "It's fine" }}
{{ 'Say "hi"' }}
```

## String Concatenation

Kida supports both `+` and `~` for string building:

- `+` adds when both operands are numeric, otherwise it concatenates as strings.
- `~` always coerces both sides to strings, which makes it the clearest choice for dynamic
  URLs, paths, and IDs.

```kida
{{ "Hello, " + name }}
{{ count + " items" }}
{{ "/path/" ~ id ~ "/action" }}
hx-post="{{ '/chains/' ~ chain_id ~ '/add-step' }}"
```

Static analysis tools (e.g. Chirp's contract checker) treat these concatenated attribute
values as dynamic and skip route validation for such URLs.

## Method Calls

Call methods on objects:

```kida
{{ name.upper() }}
{{ items.count(x) }}
{{ text.split(',')[0] }}
```

## Global Functions

Built-in functions available in all templates:

```kida
{{ range(10) }}
{{ len(items) }}
{{ dict(a=1, b=2) }}
```

Available globals: `range`, `dict`, `list`, `set`, `tuple`, `len`, `str`, `int`, `float`, `bool`, `abs`, `min`, `max`, `sum`, `sorted`, `reversed`, `enumerate`, `zip`, `map`, `filter`.

## List Comprehensions

Transform iterables inline using Python-style list comprehensions:

```kida
{# Basic comprehension #}
{% set doubled = [x * 2 for x in items] %}

{# With filter #}
{% set names = [name | title for name in raw_names] %}

{# With condition #}
{% set visible = [item for item in items if item.active] %}

{# Shaping data for components #}
{% set opts = [{"value": s, "label": s | capitalize} for s in options] %}
```

List comprehensions support a single `for...in` clause with an optional `if` condition. Use them for presentation-level data shaping — for business logic, keep transformations in Python.

Tuple unpacking in the target is supported:

```kida
{% set keys = [k for k, v in pairs] %}
```

## See Also

- [[docs/syntax/filters|Filters]] — Transform output values
- [[docs/syntax/control-flow|Control Flow]] — Conditionals and loops
- [[docs/reference/filters|Filter Reference]] — All built-in filters
