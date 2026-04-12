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

## Basic usage

A component provides data with `let:name=expr` on `{% slot %}`:

```kida
{# components/user-list.html #}
{% def user_list(users) %}
<ul>
  {% for user in users %}
    <li>{% slot let:item=user %}{{ item }}{% end %}</li>
  {% end %}
</ul>
{% end %}
```

The caller receives that data with `let:name` on `{% call %}`:

```kida
{% from "components/user-list.html" import user_list %}

{% call(let:item) user_list(users=people) %}
  <strong>{{ item.name }}</strong> &mdash; {{ item.email }}
{% end %}
```

The component iterates the data. The caller controls the markup. Neither is
coupled to the other.

## How it works

| Side | Syntax | Purpose |
|------|--------|---------|
| Component (def) | `{% slot let:name=expr %}` | Push data to the caller |
| Caller (call) | `{% call(let:name) fn() %}` | Receive the data |

The `let:` bindings flow **up** from the slot to the caller's block. Inside the
`{% call %}...{% end %}` body, the bound names are available as local variables.

## Multiple bindings

A slot can expose more than one value:

```kida
{% def data_table(rows) %}
<table>
  {% for row in rows %}
    <tr>{% slot let:item=row, let:index=loop.index0 %}{% end %}</tr>
  {% end %}
</table>
{% end %}
```

```kida
{% call(let:item, let:index) data_table(rows=data) %}
  <td>{{ index }}</td>
  <td>{{ item.name }}</td>
  <td>{{ item.value }}</td>
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
  {% slot let:item=user %}
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
{% call(let:item) card(user=alice) %}
  <img src="{{ item.avatar }}"> <b>{{ item.name }}</b>
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
{% call(let:data) layout(page=p) %}
  {% slot header %}<h1 class="fancy">{{ p.title }}</h1>{% end %}
  <div class="prose">{{ data | markdown }}</div>
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
    <li>{% slot let:item=item %}{{ item }}{% end %}</li>
  {% end %}
</ul>
{% endprovide %}
{% end %}

{% call(let:item) themed_list(items=data) %}
  <span class="{{ consume("theme") }}">{{ item.name }}</span>
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
      <tr>{% slot let:row=row, let:cols=columns %}
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
{% call(let:row, let:cols) sortable_table(rows=users, columns=cols) %}
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
```
