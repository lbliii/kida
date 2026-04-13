---
title: "Jinja2 vs Kida: Components"
description: A real-world dashboard card built in Jinja2 and Kida — side by side
draft: false
weight: 15
lang: en
type: doc
tags:
- tutorial
- components
- jinja2
- migration
keywords:
- jinja2 comparison
- component comparison
- macro vs def
- slots
- composition
- scoping
icon: columns
---

# Jinja2 vs Kida: Components

A real-world dashboard card component built in both engines. Same HTML output, very different authoring experience.

The component has:
- Typed props (title, subtitle, variant)
- A header actions slot
- A default body slot
- An optional footer
- Co-located CSS
- Theming via context (not prop drilling)

## The Jinja2 Version

### Component Definition

```jinja2
{# components/card.html (Jinja2) #}

{# No type annotations — params are a guessing game #}
{% macro card(title, subtitle="", variant="default") %}
  <article class="card card--{{ variant }}">
    <header class="card__header">
      <div>
        <h3>{{ title }}</h3>
        {% if subtitle %}<p class="card__subtitle">{{ subtitle }}</p>{% endif %}
      </div>
      {# No named slots — caller() is all-or-nothing #}
    </header>
    <div class="card__body">
      {{ caller() }}
    </div>
  </article>
{% endmacro %}
```

**Problems:**
- No type annotations on parameters
- `caller()` gives you one blob of content — no way to target header actions vs body vs footer separately
- No `has_slot()` — can't conditionally render a footer wrapper

### Usage

```jinja2
{# pages/dashboard.html (Jinja2) #}
{% from "components/card.html" import card %}

{# Need to pass theme through every layer #}
{% call card("Settings", subtitle="Manage preferences", variant="elevated") %}
  <form>
    <label>Theme</label>
    {# How do we read the current theme? It must be passed as a variable #}
    <select name="theme">
      <option {% if theme == "light" %}selected{% endif %}>Light</option>
      <option {% if theme == "dark" %}selected{% endif %}>Dark</option>
    </select>
  </form>
{% endcall %}
```

### Scoping Trap

Jinja2's `{% set %}` leaks out of blocks. This causes subtle bugs:

```jinja2
{# Jinja2 — count leaks across iterations #}
{% set count = 0 %}
{% for section in sections %}
  {% set count = count + 1 %}
  {# count is now modified in the OUTER scope #}
{% endfor %}
{# count == len(sections), not 0 — the set leaked #}
```

To work around this, Jinja2 requires the `namespace()` pattern:

```jinja2
{# Jinja2 — namespace workaround #}
{% set ns = namespace(count=0) %}
{% for section in sections %}
  {% set ns.count = ns.count + 1 %}
{% endfor %}
{{ ns.count }}
```

### Co-located Styles

Jinja2 has no content stacks. You must manage CSS separately:

```jinja2
{# base.html (Jinja2) #}
<head>
  <link rel="stylesheet" href="/css/main.css">
  {# No way for components to inject styles here #}
  {% block extra_styles %}{% endblock %}
</head>

{# Every page that uses card must manually add its CSS #}
{% block extra_styles %}
  <link rel="stylesheet" href="/css/card.css">
{% endblock %}
```

Styles are disconnected from the component that needs them.

### Context / Theming

Jinja2 has no `provide`/`consume`. To theme nested components, you must pass the value through every layer:

```jinja2
{# Jinja2 — prop drilling #}
{% macro page_shell(theme) %}
  {{ sidebar(theme=theme) }}
  <main>{{ caller() }}</main>
{% endmacro %}

{% macro sidebar(theme) %}
  <nav class="sidebar sidebar--{{ theme }}">
    {{ sidebar_item("Home", "/", theme=theme) }}
    {{ sidebar_item("Settings", "/settings", theme=theme) }}
  </nav>
{% endmacro %}

{% macro sidebar_item(label, url, theme) %}
  <a class="sidebar__item sidebar__item--{{ theme }}" href="{{ url }}">
    {{ label }}
  </a>
{% endmacro %}
```

Three layers deep, and every one must forward `theme`.

### Error Handling

Jinja2 has no error boundaries. One broken component crashes the entire page:

```jinja2
{# Jinja2 — if user.profile is None, the whole page 500s #}
{% call card(user.profile.display_name) %}
  {{ render_activity(user.id) }}
{% endcall %}
```

---

## The Kida Version

### Component Definition

```kida
{# components/card.html (Kida) #}

{% def card(title: str, subtitle: str | None = none, variant: str = "default") %}
{% push "styles" %}
<style>
  .card { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  .card--elevated { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  .card__header { padding: 16px; display: flex; justify-content: space-between; }
  .card__body { padding: 0 16px 16px; }
  .card__footer { padding: 12px 16px; border-top: 1px solid var(--border); }
</style>
{% end %}
<article class="card card--{{ variant }}">
  <header class="card__header">
    <div>
      <h3>{{ title }}</h3>
      {% if subtitle %}<p class="card__subtitle">{{ subtitle }}</p>{% end %}
    </div>
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

**What's different:**

| Feature | Jinja2 | Kida |
|---------|--------|------|
| Type annotations | No | `title: str`, `subtitle: str \| None` |
| Named slots | No (`caller()` only) | `{% slot header_actions %}`, `{% slot footer %}` |
| Conditional slot wrapper | No | `has_slot("footer")` |
| Co-located styles | No | `{% push "styles" %}` |
| Validated at check time | No | `kida check --validate-calls` |

### Usage

```kida
{# pages/dashboard.html (Kida) #}
{% from "components/card.html" import card %}

{% provide theme = "dark" %}
{% call card("Settings", subtitle="Manage preferences", variant="elevated") %}
  {% slot header_actions %}
    <button class="btn btn--icon" aria-label="Save">Save</button>
  {% end %}

  <form>
    <label>Theme</label>
    <select name="theme">
      <option {% if consume("theme") == "light" %}selected{% end %}>Light</option>
      <option {% if consume("theme") == "dark" %}selected{% end %}>Dark</option>
    </select>
  </form>

  {% slot footer %}
    <button type="submit">Apply</button>
  {% end %}
{% end %}
{% end %}
```

- Header actions, body, and footer are separate slots — targeted, not jumbled
- Theme comes from `consume("theme")`, not a prop passed through every layer
- Styles are co-located in the component and rendered in `<head>` via `{% stack "styles" %}`

### Scoping

Kida's `{% set %}` is block-scoped. No leaking, no `namespace()` workaround:

```kida
{# Kida — set is block-scoped, use let for template-wide #}
{% let count = 0 %}
{% for section in sections %}
  {% set count = count + 1 %}
  {# This count is local to the for loop — outer count is still 0 #}
{% end %}
{# count == 0 — no leaking #}

{# To modify outer scope, use export #}
{% let total = 0 %}
{% for section in sections %}
  {% export total = total + 1 %}
{% end %}
{# total == len(sections) — explicit, intentional #}
```

### Context / Theming

No prop drilling. Set the theme once, read it anywhere:

```kida
{% def page_shell() %}
  {{ sidebar_nav() }}
  <main>{% slot %}</main>
{% end %}

{% def sidebar_nav() %}
<nav class="sidebar sidebar--{{ consume('theme') }}">
  {{ sidebar_item("Home", "/") }}
  {{ sidebar_item("Settings", "/settings") }}
</nav>
{% end %}

{% def sidebar_item(label: str, url: str) %}
<a class="sidebar__item sidebar__item--{{ consume('theme') }}" href="{{ url }}">
  {{ label }}
</a>
{% end %}
```

Zero mentions of `theme` in any function signature. Each component reads what it needs from context.

### Error Boundaries

Wrap risky components so failures degrade gracefully:

```kida
{% try %}
  {% call card(user.profile.display_name) %}
    {{ render_activity(user.id) }}
  {% end %}
{% fallback error %}
  <div class="card card--error" role="alert">
    <p>Could not load this card.</p>
  </div>
{% end %}
```

The rest of the page renders normally even if this card fails.

### Static Validation

```bash
$ kida check templates/ --validate-calls

templates/pages/dashboard.html:8: Call to 'card' — unknown params: titl
templates/pages/settings.html:14: type: badge() param 'count' expects int, got str ("five")
```

Jinja2 has no equivalent — parameter errors surface at runtime.

---

## Summary

| Capability | Jinja2 | Kida |
|-----------|--------|------|
| Type annotations on params | No | `param: str \| None` |
| Compile-time call validation | No | `kida check --validate-calls` |
| Named slots | No | `{% slot name %}` |
| Conditional slot rendering | No | `has_slot("name")` |
| Scoped slot data (data up) | No | `let:item=expr` |
| Block-scoped variables | No (`set` leaks) | `{% set %}` is block-scoped |
| Explicit outer-scope mutation | `namespace()` hack | `{% export %}` |
| Context propagation | Prop drilling only | `{% provide %}` / `consume()` |
| Error boundaries | No | `{% try %}...{% fallback %}` |
| Co-located component styles | No | `{% push %}` / `{% stack %}` |
| Component discovery CLI | No | `kida components` |
| Component introspection API | No | `template.def_metadata()` |
| Pattern matching | `if`/`elif` chains | `{% match %}` / `{% case %}` |
| Content stacks | No | `{% push %}` / `{% stack %}` |

Both engines produce the same HTML. The difference is in how you get there — and what happens when things go wrong.

## See Also

- [[docs/usage/components|Components Guide]] — Full patterns reference
- [[docs/get-started/coming-from-jinja2|Coming from Jinja2]] — Quick cheat sheet
- [[docs/tutorials/migrate-from-jinja2|Migration Guide]] — Step-by-step migration
- [[docs/about/comparison|Feature Comparison]] — Full feature matrix
