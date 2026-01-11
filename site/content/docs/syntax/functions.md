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
