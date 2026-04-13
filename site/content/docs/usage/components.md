---
title: Components
description: Build reusable UI components with defs, slots, typed props, and context propagation
draft: false
weight: 22
lang: en
type: doc
tags:
- usage
- components
- composition
keywords:
- components
- def
- call
- slot
- composition
- props
- typed parameters
- provide
- consume
icon: puzzle
category: documentation
---

# Components

Kida's component model gives you the composition patterns of React or Svelte — typed props, named slots, context propagation, error boundaries — without a build step or JavaScript runtime. Everything compiles to Python AST and renders server-side.

This guide covers the blessed patterns for writing, organizing, and consuming components.

## Anatomy of a Component

A Kida component is a `{% def %}` with typed parameters and slots:

```kida
{% def card(title: str, variant: str = "default") %}
<article class="card card--{{ variant }}">
  <header class="card__header">
    <h3>{{ title }}</h3>
    {% slot header_actions %}
  </header>
  <div class="card__body">
    {% slot %}
  </div>
  {% if has_slot("footer") %}
  <footer class="card__footer">
    {% slot footer %}
  </footer>
  {% end %}
</article>
{% end %}
```

This single definition gives you:

- **Typed props** — `title: str` is validated by `kida check --validate-calls`
- **Default values** — `variant` falls back to `"default"`
- **Named slots** — `header_actions` and `footer` for targeted content injection
- **Default slot** — `{% slot %}` captures the primary body content
- **Conditional rendering** — `has_slot("footer")` only renders the footer wrapper when content is provided

## Using Components

### Inline Call (No Slots)

For simple components that don't need body content:

```kida
{{ card("Settings") }}
```

### Call Block (With Slots)

Use `{% call %}` to pass slot content:

```kida
{% call card("Settings", variant="elevated") %}
  {% slot header_actions %}
    <button class="btn btn--icon">Save</button>
  {% end %}

  <form>
    <label>Theme</label>
    <select name="theme">
      <option>Light</option>
      <option>Dark</option>
    </select>
  </form>

  {% slot footer %}
    <button type="submit">Apply</button>
  {% end %}
{% end %}
```

- Bare content inside `{% call %}` fills the **default slot**
- `{% slot name %}...{% end %}` inside `{% call %}` fills a **named slot**
- Unfilled slots produce no output

## Component Organization

### One Component Per File

For shared components, define one primary component per file:

```
templates/
  components/
    card.html
    button.html
    modal.html
    nav/
      breadcrumbs.html
      sidebar.html
```

```kida
{# components/button.html #}
{% def button(label: str, variant: str = "primary", disabled: bool = false) %}
<button class="btn btn--{{ variant }}" {% if disabled %}disabled{% end %}>
  {{ label }}
</button>
{% end %}
```

Import and use:

```kida
{% from "components/button.html" import button %}
{% from "components/card.html" import card %}

{% call card("User Profile") %}
  {{ button("Edit", variant="secondary") }}
{% end %}
```

### Grouped Components

When small components are logically related, group them in one file:

```kida
{# components/forms.html #}
{% def text_input(name: str, label: str, value: str = "", required: bool = false) %}
<div class="form-field">
  <label for="{{ name }}">{{ label }}</label>
  <input type="text" id="{{ name }}" name="{{ name }}" value="{{ value }}"
    {% if required %}required{% end %}>
</div>
{% end %}

{% def select_input(name: str, label: str, options: list) %}
<div class="form-field">
  <label for="{{ name }}">{{ label }}</label>
  <select id="{{ name }}" name="{{ name }}">
    {% for opt in options %}
    <option value="{{ opt.value }}">{{ opt.label }}</option>
    {% end %}
  </select>
</div>
{% end %}

{% def checkbox(name: str, label: str, checked: bool = false) %}
<label class="checkbox">
  <input type="checkbox" name="{{ name }}" {% if checked %}checked{% end %}>
  {{ label }}
</label>
{% end %}
```

Import selectively:

```kida
{% from "components/forms.html" import text_input, select_input %}
```

### Discovering Components

Use the CLI to list all components across your project:

```bash
kida components templates/

# Filter by name
kida components templates/ --filter card

# Machine-readable output
kida components templates/ --json
```

Or use the Python API:

```python
template = env.get_template("components/card.html")
for name, meta in template.def_metadata().items():
    params = ", ".join(
        f"{p.name}: {p.annotation}" if p.annotation else p.name
        for p in meta.params
    )
    print(f"  def {name}({params})")
    if meta.slots:
        print(f"    slots: {', '.join(meta.slots)}")
```

## Typed Props

Type annotations on parameters serve as documentation and enable static validation:

```kida
{% def badge(label: str, count: int, variant: str | None = none) %}
<span class="badge {% if variant %}badge--{{ variant }}{% end %}">
  {{ label }}: {{ count }}
</span>
{% end %}
```

### Supported Types

| Annotation | Validates Literals |
|-----------|---------|
| `str` | String literals |
| `int` | Integer literals |
| `float` | Float and integer literals |
| `bool` | `true` / `false` |
| `None` | `none` literal |
| `str \| None` | Union types (PEP 604 style) |
| `list`, `dict`, custom types | Accepted as documentation; not validated statically |

### Validation

Enable compile-time checking with `validate_calls=True` on the Environment or via the CLI:

```bash
# Catches: unknown params, missing required params, type mismatches on literals
kida check templates/ --validate-calls
```

```
components/card.html:14: type: badge() param 'count' expects int, got str ("five")
```

Variable arguments are skipped — only literal values can be type-checked statically.

## Slot Patterns

### Default Slot Only

For components with a single content area:

```kida
{% def panel(title: str) %}
<section class="panel">
  <h2>{{ title }}</h2>
  {% slot %}
</section>
{% end %}
```

### Named Slots for Multi-Region Layout

When a component has distinct content regions:

```kida
{% def page_layout(title: str) %}
<div class="layout">
  <header>
    <h1>{{ title }}</h1>
    {% slot toolbar %}
  </header>
  <aside>{% slot sidebar %}</aside>
  <main>{% slot %}</main>
  <footer>{% slot footer %}</footer>
</div>
{% end %}
```

### Conditional Slots

Use `has_slot()` to adapt markup based on whether content was provided:

```kida
{% def alert(message: str, variant: str = "info") %}
<div class="alert alert--{{ variant }}" role="alert">
  <p>{{ message }}</p>
  {% if has_slot() %}
  <div class="alert__actions">
    {% slot %}
  </div>
  {% end %}
</div>
{% end %}
```

### Scoped Slots

Components can pass data **back** to the caller with `let:` bindings:

```kida
{% def data_table(items: list) %}
<table>
  {% for item in items %}
  <tr>
    {% slot row let:item=item let:index=loop.index %}
      <td>{{ item }}</td>
    {% end %}
  </tr>
  {% end %}
</table>
{% end %}

{% call data_table(users) %}
  {% slot row %}
    <td>{{ item.name }}</td>
    <td>{{ item.email }}</td>
  {% end %}
{% end %}
```

See [[docs/advanced/scoped-slots|Scoped Slots]] for the full guide.

### Slot Forwarding

When wrapping a component in another component, use `{% yield %}` to forward slots:

```kida
{% def selection_bar() %}<nav>{{ caller() }}</nav>{% end %}

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

`{% yield name %}` renders the enclosing def's caller slot, even inside a nested `{% call %}` block.

## Context Propagation

### The Prop Drilling Problem

Without context propagation, deeply nested components need every intermediate layer to pass props through:

```kida
{# Every layer must forward "theme" — fragile and verbose #}
{% def page_shell(theme: str) %}
  {{ sidebar(theme=theme) }}
  {{ content_area(theme=theme) }}
{% end %}
```

### Provide / Consume

Use `{% provide %}` to push state and `consume()` to read it anywhere in the subtree:

```kida
{# Layout sets theme once #}
{% provide theme = "dark" %}
  {% call page_shell() %}
    {% slot sidebar %}
      {{ sidebar_nav() }}
    {% end %}
    Main content here.
  {% end %}
{% end %}

{# sidebar_nav.html — reads theme without it being passed as a prop #}
{% def sidebar_nav() %}
<nav class="sidebar sidebar--{{ consume('theme') }}">
  ...
</nav>
{% end %}
```

- `consume("key")` returns the nearest ancestor's provided value
- Nested `{% provide %}` blocks shadow outer values (like CSS custom properties)
- Works across slot boundaries, includes, and imported components

See [[docs/usage/provide-consume|Provide / Consume]] for the full guide.

## Error Boundaries

Wrap component calls in `{% try %}...{% fallback %}` to prevent one broken component from crashing the entire page:

```kida
{% try %}
  {% call user_card(user) %}
    {{ render_activity_feed(user.id) }}
  {% end %}
{% fallback error %}
  <div class="card card--error">
    <p>Could not load user card.</p>
  </div>
{% end %}
```

When an error occurs inside the `{% try %}` block, Kida discards its partial output and renders the `{% fallback %}` block instead. The `error` variable contains the exception.

This is especially useful for:
- Components that depend on external data (API calls, database queries)
- Third-party components you don't control
- Graceful degradation in production

See [[docs/usage/error-boundaries|Error Boundaries]] for the full guide.

## Component Styles with Push/Stack

Use content stacks to co-locate CSS with the component that needs it:

```kida
{# components/tooltip.html #}
{% def tooltip(text: str) %}
{% push "styles" %}
<style>
  .tooltip { position: relative; display: inline-block; }
  .tooltip__text {
    visibility: hidden; position: absolute; z-index: 1;
    background: #333; color: #fff; padding: 4px 8px;
    border-radius: 4px; font-size: 0.875rem;
  }
  .tooltip:hover .tooltip__text { visibility: visible; }
</style>
{% end %}
<span class="tooltip">
  {% slot %}
  <span class="tooltip__text">{{ text }}</span>
</span>
{% end %}
```

```kida
{# base.html #}
<head>
  <link rel="stylesheet" href="/css/main.css">
  {% stack "styles" %}
</head>
```

The `{% push "styles" %}` block inside the component sends its CSS to the `{% stack "styles" %}` in the base layout. Styles are only included when the component is actually used. See [[docs/advanced/content-stacks|Content Stacks]] for details.

## Introspection API

Kida provides programmatic access to component metadata for framework authors and tooling:

```python
template = env.get_template("components/card.html")

# List all defs
print(template.list_defs())  # ["card"]

# Full metadata
meta = template.def_metadata()
card = meta["card"]
print(card.params)          # (DefParamInfo(name='title', annotation='str', ...), ...)
print(card.slots)           # ('header_actions', 'footer')
print(card.has_default_slot)  # True
print(card.depends_on)      # frozenset()
```

### Block-Level Metadata

For templates using `{% block %}` inheritance:

```python
meta = template.template_metadata()
for name, block in meta.blocks.items():
    if block.is_cacheable():
        print(f"{name}: cache_scope={block.cache_scope}")
```

See [[docs/advanced/analysis|Static Analysis]] for the full analysis API.

## Quick Reference

| Pattern | Syntax | Use When |
|---------|--------|----------|
| Define component | `{% def name(props) %}...{% end %}` | Always |
| Inline call | `{{ name(args) }}` | No body content needed |
| Call with slots | `{% call name(args) %}...{% end %}` | Passing body/slot content |
| Default slot (def) | `{% slot %}` | Single content area |
| Named slot (def) | `{% slot name %}` | Multiple content regions |
| Fill slot (call) | `{% slot name %}...{% end %}` | Providing named content |
| Conditional slot | `has_slot()` / `has_slot("name")` | Adapt markup to slot presence |
| Scoped slot | `{% slot let:x=expr %}` | Pass data back to caller |
| Forward slot | `{% yield name %}` | Wrap component in another |
| Context push | `{% provide key = val %}` | Avoid prop drilling |
| Context read | `consume("key")` | Read ancestor-provided value |
| Error boundary | `{% try %}...{% fallback %}...{% end %}` | Isolate failures |
| Co-located styles | `{% push "styles" %}...{% end %}` | Component-scoped CSS |
| Type annotation | `param: str` | Self-documenting + validation |

## See Also

- [[docs/syntax/functions|Functions]] — Full `{% def %}` syntax reference
- [[docs/advanced/scoped-slots|Scoped Slots]] — Data-up pattern with `let:` bindings
- [[docs/usage/provide-consume|Provide / Consume]] — Context propagation
- [[docs/usage/error-boundaries|Error Boundaries]] — `{% try %}`/`{% fallback %}`
- [[docs/advanced/content-stacks|Content Stacks]] — `{% push %}`/`{% stack %}`
- [[docs/tutorials/component-comparison|Jinja2 vs Kida Components]] — Side-by-side comparison
