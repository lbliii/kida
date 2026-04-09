---
title: Provide / Consume
description: Pass state from parent components to descendants without prop drilling
draft: false
weight: 21
lang: en
type: doc
tags:
- usage
- components
- context
keywords:
- provide
- consume
- context
- slots
- components
- state
icon: layers
---

# Provide / Consume

`{% provide %}` and `consume()` let a parent push state that any descendant
can read -- across slot boundaries, includes, and imported macros -- without
passing it through every layer of parameters.

## Quick start

```jinja2
{% provide theme = "dark" %}
  {{ consume("theme") }}        {# "dark" #}
{% endprovide %}
```

`provide` pushes a value onto a per-key stack. `consume` reads the top of
that stack, or returns a default if the key is absent.

## Syntax

### provide

```jinja2
{% provide key = expr %}
  ...body...
{% endprovide %}
```

- **key** -- a plain name (not a string).
- **expr** -- any expression: a literal, variable, function call, etc.
- The body can contain any template content.
- `{% end %}` is accepted as a shorthand for `{% endprovide %}`.

### consume

```jinja2
{{ consume("key") }}
{{ consume("key", default) }}
```

- **key** -- a string naming the provided value.
- **default** -- returned when no provider for that key is active. Defaults
  to `None` when omitted.

## Nesting and shadowing

Providers nest. An inner `provide` with the same key shadows the outer one
for the duration of its body, then the outer value is automatically restored:

```jinja2
{% provide color = "red" %}
  {{ consume("color") }}          {# "red" #}

  {% provide color = "blue" %}
    {{ consume("color") }}        {# "blue" #}
  {% end %}

  {{ consume("color") }}          {# "red" again #}
{% end %}
```

Independent keys coexist without interference:

```jinja2
{% provide a = 1 %}
{% provide b = 2 %}
  {{ consume("a") }}, {{ consume("b") }}   {# 1, 2 #}
{% end %}
{% end %}
```

## Components: table + row

The motivating use case is implicit configuration between paired components.
A `table` provides alignment metadata that `row` consumes, so callers never
pass alignment to every row by hand:

```jinja2
{# components/table.html #}
{% def table(headers, align=none) %}
{% provide _table_align = align %}
<table>
  <thead>
    <tr>{% for h in headers %}<th>{{ h }}</th>{% end %}</tr>
  </thead>
  <tbody>{% slot %}</tbody>
</table>
{% endprovide %}
{% end %}

{% def row(*cells) %}
{% set align = consume("_table_align") %}
<tr>
  {% for cell in cells %}
  <td{% if align %} class="align-{{ align[loop.index0] }}"{% endif %}>
    {{ cell }}
  </td>
  {% end %}
</tr>
{% end %}
```

Usage:

```jinja2
{% from "components/table.html" import table, row %}

{% call table(headers=["Name", "Count"], align=["left", "right"]) %}
  {{ row("Alice", "42") }}
  {{ row("Bob", "17") }}
{% end %}
```

`row` never receives alignment as a parameter -- it reads it from the
nearest `table` ancestor via `consume`.

## Theme provider pattern

Another common pattern: a theme wrapper that sets context for all
descendant components.

```jinja2
{% def theme_provider(name="light") %}
{% provide theme = name %}
<div class="theme-{{ name }}">{% slot %}</div>
{% endprovide %}
{% end %}

{% def button(label) %}
<button class="btn btn-{{ consume("theme", "light") }}">{{ label }}</button>
{% end %}
```

Nested providers override the theme for their subtree:

```jinja2
{% call theme_provider("dark") %}
  {{ button("Save") }}           {# btn-dark #}
  {% call theme_provider("accent") %}
    {{ button("Upgrade") }}      {# btn-accent #}
  {% end %}
  {{ button("Cancel") }}         {# btn-dark (restored) #}
{% end %}
```

## Where consume works

Provided values are visible everywhere the render context is shared:

| Boundary | Visible? |
|----------|----------|
| Slot content (`{% call %}...{% end %}`) | Yes |
| Macro calls (`{{ child() }}`) | Yes |
| Imported macros (`{% from "x.html" import y %}`) | Yes |
| Includes (`{% include "x.html" %}`) | Yes |
| Child templates (inheritance) | Yes |

## Error safety

`provide` compiles to a `try`/`finally` block, so the stack is always
cleaned up -- even when the body raises an exception. After an error, a
fresh render starts with a clean provider state.

## Naming conventions

Use an underscore prefix for keys that are internal to a component pair:

```jinja2
{% provide _table_align = align %}    {# internal to table/row #}
```

Use plain names for user-facing configuration:

```jinja2
{% provide theme = "dark" %}
```

## Example

A full working example is in
[`examples/provide_consume/`](https://github.com/lbliii/kida/tree/main/examples/provide_consume).
