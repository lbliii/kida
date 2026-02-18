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
- typed parameters
- type annotations
- validate_calls
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

## Typed Parameters

Parameters can carry optional type annotations following Python syntax:

```kida
{% def card(title: str, items: list, footer: str | None = none) %}
    <h3>{{ title }}</h3>
    {% for item in items %}<p>{{ item }}</p>{% end %}
    {% if footer %}<footer>{{ footer }}</footer>{% end %}
{% end %}
```

Annotations are optional per-parameter — you can mix typed and untyped:

```kida
{% def mixed(name: str, options, count: int = 0) %}
    ...
{% end %}
```

### Supported Syntax

| Syntax | Meaning |
|--------|---------|
| `x: str` | Simple type |
| `x: int` | Simple type |
| `x: list` | Generic without params |
| `x: dict[str, int]` | Generic with params |
| `x: str \| None` | Union (PEP 604 style) |
| `x: MyModel` | Custom type name |

### What Annotations Do

Annotations are **documentation and validation hints**, not enforced at runtime.
The template engine does not perform `isinstance` checks. Their value is:

1. **Compile-time call-site validation** — wrong parameter names are caught immediately when `validate_calls=True` is set on the Environment
2. **IDE support** — annotations flow into the generated Python code, enabling autocomplete in tooling
3. **Self-documenting** — makes component interfaces explicit

### Call-Site Validation

Enable `validate_calls` on the Environment to catch parameter errors at compile time:

```python
from kida import Environment

env = Environment(validate_calls=True)

# This emits a warning: 'titl' is not a param of 'card'
env.from_string("""
    {% def card(title: str) %}{{ title }}{% end %}
    {{ card(titl="oops") }}
""")
```

Validation checks:
- **Unknown parameters** — keyword args not in the definition
- **Missing required parameters** — params without defaults not provided
- `*args` / `**kwargs` in the definition relax validation accordingly

See [[docs/advanced/analysis|Static Analysis]] for the programmatic API.

---

## Capturing Content (Default Slot)

Functions can capture call-block content using `caller()`:

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

`caller()` without arguments reads the **default slot**.

## Named Slots

Kida also supports named slots for multi-region components:

```kida
{% def card(title) %}
    <article>
        <h2>{{ title }}</h2>
        <div class="actions">{% slot header_actions %}</div>
        <div class="body">{% slot %}</div>
    </article>
{% end %}

{% call card("Settings") %}
    {% slot header_actions %}<button>Save</button>{% end %}
    <p>Body content.</p>
{% end %}
```

How it works:

- `{% slot %}` in a `def` is the default placeholder.
- `{% slot name %}` in a `def` is a named placeholder.
- Inside `{% call %}`, use `{% slot name %}...{% end %}` to provide named slot content.
- `caller("name")` retrieves a named slot from inside a `def`.

## Slot Detection

When a function is called via `{% call %}`, it receives slot content accessible through `caller()`. Use the built-in `has_slot()` helper inside a `{% def %}` body to detect whether any call slot content was provided:

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

This pattern is useful for components that should adapt their markup depending on whether slot content is provided, for example rendering a wrapper `<div>` only when there is something to wrap.

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
