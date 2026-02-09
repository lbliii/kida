---
title: Functions
description: Define reusable template functions and macros
draft: false
weight: 40
lang: en
type: doc
tags:
- syntax
- functions
- macros
keywords:
- functions
- macros
- def
- reusable
icon: function
---

# Functions

Define reusable template functions within your templates.

## Defining Functions

Use `{% def %}` to create a function:

```kida
{% def greet(name) %}
    <p>Hello, {{ name }}!</p>
{% end %}

{{ greet("Alice") }}
{{ greet("Bob") }}
```

## Parameters

### Required Parameters

```kida
{% def button(text, url) %}
    <a href="{{ url }}" class="button">{{ text }}</a>
{% end %}

{{ button("Click Me", "/action") }}
```

### Default Values

```kida
{% def button(text, url, style="primary") %}
    <a href="{{ url }}" class="button button-{{ style }}">{{ text }}</a>
{% end %}

{{ button("Save", "/save") }}
{{ button("Cancel", "/cancel", style="secondary") }}
```

### Keyword Arguments

```kida
{% def card(title, content="", footer=none) %}
    <div class="card">
        <h3>{{ title }}</h3>
        {% if content %}
            <p>{{ content }}</p>
        {% end %}
        {% if footer %}
            <footer>{{ footer }}</footer>
        {% end %}
    </div>
{% end %}

{{ card(title="Hello", content="World") }}
{{ card("Title Only") }}
```

## Capturing Content

Functions can capture block content using `caller()`:

```kida
{% def wrapper(title) %}
    <section>
        <h2>{{ title }}</h2>
        <div class="content">
            {{ caller() }}
        </div>
    </section>
{% end %}

{% call wrapper("Section Title") %}
    <p>This content is passed to the wrapper.</p>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
{% end %}
```

## Slot Detection

When a function is called via `{% call %}`, it receives slot content accessible through `caller()`. Use the built-in `has_slot()` function inside a `{% def %}` body to detect whether slot content was provided:

```kida
{% def card(title) %}
    <div class="card">
        <h3>{{ title }}</h3>
        {% if has_slot() %}
            <div class="card-body">
                {{ caller() }}
            </div>
        {% end %}
    </div>
{% end %}
```

When called directly, `has_slot()` returns `false`:

```kida
{{ card("Simple Card") }}
{# Output: <div class="card"><h3>Simple Card</h3></div> #}
```

When called with `{% call %}`, `has_slot()` returns `true`:

```kida
{% call card("Rich Card") %}
    <p>This content appears in the card body.</p>
    <button>Action</button>
{% end %}
{# Output includes the card-body wrapper #}
```

This pattern is useful for components that should adapt their markup depending on whether slot content is provided — for example, rendering a wrapper `<div>` only when there's something to wrap.

---

## Macros

Kida also supports the `{% macro %}` syntax:

```kida
{% macro input(name, value="", type="text") %}
    <input type="{{ type }}" name="{{ name }}" value="{{ value }}">
{% endmacro %}

{{ input("username") }}
{{ input("password", type="password") }}
```

## Importing Functions

Import functions from other templates:

```kida
{% from "macros.html" import button, input %}

{{ button("Submit", "/submit") }}
{{ input("email", type="email") }}
```

Import all with a namespace:

```kida
{% import "forms.html" as forms %}

{{ forms.input("name") }}
{{ forms.textarea("bio") }}
```

## Best Practices

### Single Responsibility

Each function should do one thing:

```kida
{# Good: Single purpose #}
{% def user_avatar(user, size=32) %}
    <img src="{{ user.avatar_url }}"
         alt="{{ user.name }}"
         width="{{ size }}"
         height="{{ size }}">
{% end %}

{# Avoid: Too much logic #}
{% def user_card_with_everything(user, show_bio, show_posts, ...) %}
    ...
{% end %}
```

### Descriptive Names

```kida
{# Good: Clear purpose #}
{% def format_price(amount, currency="USD") %}
{% def user_badge(role) %}
{% def pagination_nav(current, total) %}

{# Avoid: Vague names #}
{% def render(x) %}
{% def do_thing(item) %}
```

## See Also

- [[docs/syntax/inheritance|Inheritance]] — Extend base templates
- [[docs/syntax/includes|Includes]] — Include partials
- [[docs/extending/custom-filters|Custom Filters]] — Python-defined filters
