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
- region
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

### Slot Forwarding with `{% yield %}`

When composing macros, you often need to forward the outer caller's slot content into a nested `{% call %}`. The `{% slot %}` tag has context-dependent meaning: inside `{% call %}` it defines content (a `SlotBlock`), not a render reference. Use `{% yield %}` when you want to **render** the enclosing def's caller slot regardless of block context:

```kida
{% def selection_bar() %}<bar>{{ caller() }}</bar>{% end %}
{% def resource_index() %}
  {% call selection_bar() %}
    {% yield selection %}
  {% end %}
{% end %}
{% call resource_index() %}
  {% slot selection %}Badges{% end %}
  Cards
{% end %}
```

- `{% yield %}` — render the caller's default slot (same as `{% slot %}` inside a def).
- `{% yield name %}` — render the caller's named slot `name`.

`{% yield %}` is self-closing (no `{% end %}`) and always produces a render reference, even inside `{% call %}` blocks. It resolves to the **nearest enclosing def's caller**, regardless of nesting depth. No caller means no output (silent no-op).

**When to use:** Prefer `{% yield %}` over the double-nesting workaround `{% slot x %}{% slot x %}{% end %}` when forwarding slots through nested calls.

### Slot Context Inheritance

Slot content is rendered in the **caller's context**. Variables from the page or render context are available in slot content without `| default()`:

```kida
{% def form(action, method="get") %}
<form action="{{ action }}" method="{{ method }}">
    {% slot %}
</form>
{% end %}

{% block page_content %}
{% call form("/search") %}
    {{ search_field("q", value=q) }}
    {% if selected_tags %}
        {{ hidden_field("tags", value=selected_tags | join(",")) }}
    {% end %}
{% end %}
{% end %}
```

When `render_block("page_content", q="...", selected_tags=["a","b"])` is called, `q` and `selected_tags` are available inside the form slot because the slot body inherits the caller's render context. This works for both `render()` and `render_block()`.

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

### Scoped Slots

Slots can also pass data **back up** to the caller using `let:` bindings.
See [Scoped Slots]({{< ref "docs/advanced/scoped-slots" >}}) for the full guide.

---

## Islands Wrapper Pattern

Functions are a good fit for reusable island mount wrappers in server-rendered apps:

```kida
{% def island_shell(name, attrs="") %}
<section{{ attrs }}>
    <div class="island-fallback">
        {% slot %}
    </div>
</section>
{% end %}

{% call island_shell("editor", attrs=island_attrs("editor", {"doc_id": doc.id}, "editor-root")) %}
    <p>Server-rendered fallback editor UI.</p>
{% end %}
```

Guidelines:

- Keep fallback slot content usable without JavaScript.
- Pass serialized props via helper globals (avoid manual inline JSON).
- Prefer stable mount IDs for deterministic remount behavior.
- Use explicit wrapper signatures when creating state primitives:

```kida
{% def grid_state_shell(state_key, columns, attrs="") %}
<section{{ attrs }}>
    {% slot %}
</section>
{% end %}
```

---

## Regions

Regions are parameterized blocks that work as both **blocks** (for `render_block()`) and **callables** (for `{{ name(args) }}`). Use them when you need parameterized fragments for HTMX partials, OOB updates, or layout composition.

### Syntax

```kida
{% region name(param1, param2=default) %}
    ...body...
{% end %}

{{ name(value1, value2) }}
```

### Block and Callable

A region compiles to both:

- A **block** — call `template.render_block("name", param1=..., param2=...)`
- A **callable** — use `{{ name(args) }}` in the template body

```kida
{% region sidebar(current_path="/") %}
  <nav>{{ current_path }}</nav>
{% end %}

{% block content %}
  {{ sidebar(current_path="/about") }}
{% end %}
```

```python
# From Python: render the region as a block
html = template.render_block("sidebar", current_path="/settings")
```

### Outer Context

Region bodies can read variables from the outer render context (not just parameters):

```kida
{% region crumbs(current_path="/") %}
{{ breadcrumb_items | default([{"label":"Home","href":"/"}]) | length }}
{% end %}

{{ crumbs(current_path="/x") }}
```

When `render_block("crumbs", ...)` or `{{ crumbs(...) }}` is called, the region receives its params plus the caller's context. `breadcrumb_items` comes from the outer context.

### Region default expressions

Optional parameters can use **any expression** as a default, not just simple variable names. Defaults are evaluated at **call time** from the caller's context:

```kida
{% region sidebar(section, meta=page.metadata) %}
  <nav>{{ meta.title }}</nav>
{% end %}

{% region stats(count=items | length) %}
  {{ count }} items
{% end %}

{% region header(title=page?.title ?? "Default") %}
  <h1>{{ title }}</h1>
{% end %}
```

Supported expressions include:

- **Simple names** — `current_page=page` (zero-overhead inline lookup)
- **Attribute access** — `meta=page.metadata`
- **Filters** — `count=items | length`
- **Optional chaining** — `title=page?.title ?? "Default"`
- **Null coalescing** — `meta=data?.info ?? {}`

Static analysis (`depends_on`) correctly captures context paths from complex defaults for incremental build and cache scope inference.

### Regions vs Defs

| Use case | Region | Def |
|----------|--------|-----|
| `render_block()` | ✅ Yes — region is a block | ❌ No — def is not a block |
| `{{ name(args) }}` | ✅ Yes | ✅ Yes |
| Slots / `{% call %}` | ❌ No | ✅ Yes |
| Outer-context access | ✅ Yes | ✅ Yes (via caller context) |
| Framework OOB discovery | ✅ `meta.regions()` | ❌ N/A |

**Use regions** when you need parameterized blocks for `render_block()`, HTMX OOB, or framework layout composition. **Use defs** when you need slots, `{% call %}`, or component composition.

### Framework Integration

Frameworks like [Chirp](https://github.com/lbliii/chirp) use `template_metadata().regions()` to discover OOB regions at build time. Each region's `BlockMetadata` includes `is_region`, `region_params`, and `depends_on` for cache scope inference. See [Framework Integration](/docs/usage/framework-integration/).

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

### Macro vs Context Variable Naming

When importing macros that render context variables, **use different names** so the macro does not shadow the variable. Prefer verb-prefixed names for macros and noun-like names for context variables:

```kida
{# Good: Macro and variable have different names #}
{% from "_route_tabs.html" import render_route_tabs %}
{% if route_tabs | default([]) %}
    {{ render_route_tabs(route_tabs, current_path) }}
{% end %}

{# Avoid: Same name causes shadowing — route_tabs may resolve to the macro #}
{% from "_route_tabs.html" import route_tabs %}
{% if route_tabs | default([]) %}  {# When route_tabs not in context, this is the macro (truthy) #}
    {{ route_tabs(route_tabs, current_path) }}  {# Passes macro as first arg → "not iterable" #}
{% end %}
```

| Use for | Naming | Examples |
|---------|--------|----------|
| Macros | Verb-prefixed | `render_route_tabs`, `format_date`, `render_nav` |
| Context variables | Noun-like | `route_tabs`, `items`, `skills` |

If you see `Cannot iterate over macro 'X'`, a macro is shadowing a context variable. Rename the macro (e.g. `render_X`) to avoid the collision.

## See Also

- [[docs/syntax/inheritance|Inheritance]] — Extend base templates
- [[docs/syntax/includes|Includes]] — Include partials
- [[docs/extending/custom-filters|Custom Filters]] — Python-defined filters
