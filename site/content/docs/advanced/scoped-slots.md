---
title: Scoped Slots
description: Pass data from components back to their callers with let bindings
draft: false
weight: 45
lang: en
type: doc
tags:
  - syntax
  - components
  - slots
keywords:
  - scoped slots
  - let bindings
  - slot data
  - components
  - data up
icon: arrow-up-circle
---

# Scoped Slots

Scoped slots let a component expose data **up** to the caller. The component
defines what data is available; the caller decides how to render it.

This is the same pattern as Svelte's `let:` directive or Vue's scoped slots.
Use the
[App-Owned Component Authoring Contract](/docs/usage/components/#app-owned-authoring-contract)
to decide when that data boundary earns a component rather than staying inline.

## Basic usage

A component provides data with `let:name=expr` on `{% slot %}`:

```kida
{# components/user-list.html #}
{% def user_list(users) %}
<ul>
  {% for user in users %}
    <li>{% slot row let:item=user %}{{ item }}{% end %}</li>
  {% end %}
</ul>
{% end %}
```

The caller receives that data with `let:name` on `{% call %}`:

```kida
{% from "components/user-list.html" import user_list %}

{% call user_list(users=people) %}
  {% slot row let:item %}
    <strong>{{ item.name }}</strong> &mdash; {{ item.email }}
  {% end %}
{% end %}
```

The component iterates the data. The caller controls the markup. Neither is
coupled to the other.

## How it works

| Side | Syntax | Purpose |
|------|--------|---------|
| Component (def) | `{% slot row let:name=expr %}` | Push data to the caller |
| Caller (call) | `{% slot row let:name %}` inside `{% call %}` | Receive the data |

The `let:` bindings flow **up** from the component's slot to the matching slot
body inside `{% call %}...{% end %}`. The declared names are local to that slot
body.

## Multiple bindings

A slot can expose more than one value:

```kida
{% def data_table(rows) %}
<table>
  {% for row in rows %}
    <tr>{% slot row let:item=row, let:index=loop.index0 %}{% end %}</tr>
  {% end %}
</table>
{% end %}
```

```kida
{% call data_table(rows=data) %}
  {% slot row let:item, let:index %}
    <td>{{ index }}</td>
    <td>{{ item.name }}</td>
    <td>{{ item.value }}</td>
  {% end %}
{% end %}
```

## Expressions in bindings

The `let:` value can be any expression -- attribute access, filters, function
calls:

```kida
{% slot let:label=item.name | upper, let:active=item.is_active %}
  {{ label }}
{% end %}
```

## Default content

When the slot has `let:` bindings and a body, that body is the **default
content** -- rendered when no caller provides a block:

```kida
{% def card(user) %}
<div class="card">
  {% slot body let:item=user %}
    {# Default: simple name display #}
    <span>{{ item.name }}</span>
  {% end %}
</div>
{% end %}
```

Called without a block, the default renders:

```kida
{{ card(user=alice) }}
{# <div class="card"><span>Alice</span></div> #}
```

Called with a block, the caller takes over:

```kida
{% call card(user=alice) %}
  {% slot body let:item %}
    <img src="{{ item.avatar }}"> <b>{{ item.name }}</b>
  {% end %}
{% end %}
```

## Named slots

Scoped slots work with named slots too:

```kida
{% def layout(page) %}
<header>{% slot header %}<h1>{{ page.title }}</h1>{% end %}</header>
<main>{% slot body let:data=page.content %}{{ data }}{% end %}</main>
{% end %}
```

```kida
{% call layout(page=p) %}
  {% slot header %}<h1 class="fancy">{{ p.title }}</h1>{% end %}
  {% slot body let:data %}<div class="prose">{{ data | markdown }}</div>{% end %}
{% end %}
```

## With provide / consume

Scoped slots and `provide`/`consume` solve different problems and coexist
cleanly:

| Pattern | Direction | Use case |
|---------|-----------|----------|
| Scoped slots (`let:`) | Child to parent (up) | Expose iteration data, computed values |
| `provide`/`consume` | Parent to child (down) | Theme, config, implicit context |

They can be used together:

```kida
{% def themed_list(items) %}
{% provide theme = "dark" %}
<ul>
  {% for item in items %}
    <li>{% slot row let:item=item %}{{ item }}{% end %}</li>
  {% end %}
</ul>
{% endprovide %}
{% end %}

{% call themed_list(items=data) %}
  {% slot row let:item %}
    <span class="{{ consume("theme") }}">{{ item.name }}</span>
  {% end %}
{% end %}
```

## Real-world example: sortable table

```kida
{# components/sortable-table.html #}
{% def sortable_table(rows, columns) %}
<table>
  <thead>
    <tr>
      {% for col in columns %}
        <th>{{ col.label }}</th>
      {% end %}
    </tr>
  </thead>
  <tbody>
    {% for row in rows %}
      <tr>{% slot row let:row=row, let:cols=columns %}
        {% for col in cols %}
          <td>{{ row[col.key] }}</td>
        {% end %}
      {% end %}</tr>
    {% end %}
  </tbody>
</table>
{% end %}
```

Default rendering works out of the box. Callers override when they need custom
cell rendering:

```kida
{% call sortable_table(rows=users, columns=cols) %}
  {% slot row let:row, let:cols %}
    <td>{{ row.name }}</td>
    <td>{{ row.email }}</td>
    <td>
      {% if row.active %}
        <span class="badge badge-green">Active</span>
      {% else %}
        <span class="badge badge-gray">Inactive</span>
      {% end %}
    </td>
  {% end %}
{% end %}
```
