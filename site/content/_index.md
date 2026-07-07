---
title: Kida
description: Server-side components for Python with typed props, named slots, and static validation — no npm or build step
template: home.html
weight: 100
type: page
draft: false
lang: en
keywords: [kida, server-side components, python components, typed props, named slots, static validation, jinja2 alternative]
category: home

# Hero configuration
blob_background: true

# CTA Buttons
cta_buttons:
  - text: Get Started
    url: /docs/get-started/
    style: primary
  - text: Build Components
    url: /docs/usage/components/
    style: secondary

show_recent_posts: false
---

## Server-Side Components for Python

**Typed props. Named slots. Static validation. No npm. No build step.**

Kida gives server-rendered Python apps a real component model. Define components
with typed props, compose them with named slots, and catch broken calls before a
request reaches production. The rendering substrate is pure Python 3.14+ with no
runtime dependencies or JavaScript toolchain.

```kida
{% def card(title: str, variant: str = "default") %}
<article class="card card--{{ variant }}">
  <header>{{ title }}</header>
  <div class="card__body">{% slot %}</div>
</article>
{% enddef %}

{% call card("Settings", variant="elevated") %}
  <p>Configure your preferences.</p>
{% endcall %}
```

---

## A Component Model, Not a Macro Convention

:::{cards}
:columns: 2
:gap: medium

:::{card} Typed Props
:icon: check-circle
Declare `title: str` and defaults where the component is defined. Kida validates
literal call sites before render.
:::{/card}

:::{card} Named and Scoped Slots
:icon: blocks
Compose headers, bodies, actions, and data-bearing child content without reducing
everything to one `caller()` blob.
:::{/card}

:::{card} Free-Threading Ready
:icon: zap
Built for Python 3.14t (PEP 703), with immutable compiled templates, `ContextVar`
render state, and copy-on-write environment mutation.
:::{/card}

:::{card} Pure Python
:icon: package
No npm, build step, or runtime dependencies. Use Kida from Flask, Django,
FastAPI/Starlette, Chirp, Bengal, scripts, and CI.
:::{/card}

:::{/cards}

## Catch Broken Calls Before Render

```kida
{% def badge(count: int, label: str) %}
<span class="badge">{{ count }} {{ label }}</span>
{% enddef %}

{{ badge(count="five", lable="Messages") }}
```

```text
K-CMP-001: Call to 'badge' — unknown params: lable; missing required: label
K-CMP-002: param 'count' expects int, got str ('five')
```

---

## Use Kida Where You Are

- Add typed components to an existing Flask, Django, FastAPI, or Starlette app.
- Render full pages, HTMX fragments, streamed responses, or static sites.
- Reuse the same component semantics for HTML, Markdown, terminal output, and CI reports.
- Give frameworks structured component metadata instead of asking them to inspect AST internals.

[Build typed components](/docs/usage/components/) or compare
[Kida components with Jinja2 macros](/docs/tutorials/component-comparison/).

---

## Zero Dependencies

Kida is pure Python with no runtime dependencies:

```toml
[project]
dependencies = []  # Zero!
```

Includes a native `Markup` class for safe HTML handling—no markupsafe required.

---

## The Bengal Ecosystem

A structured reactive stack — every layer written in pure Python for 3.14t free-threading.

| | | | |
|--:|---|---|---|
| **ᓚᘏᗢ** | [Bengal](https://github.com/lbliii/bengal) | Static site generator | [Docs](https://lbliii.github.io/bengal/) |
| **∿∿** | [Purr](https://github.com/lbliii/purr) | Content runtime | — |
| **⌁⌁** | [Chirp](https://github.com/lbliii/chirp) | Web framework | [Docs](https://lbliii.github.io/chirp/) |
| **=^..^=** | [Pounce](https://github.com/lbliii/pounce) | ASGI server | [Docs](https://lbliii.github.io/pounce/) |
| **)彡** | **Kida** | Server-side component system ← You are here | [Docs](https://lbliii.github.io/kida/) |
| **ฅᨐฅ** | [Patitas](https://github.com/lbliii/patitas) | Markdown parser | [Docs](https://lbliii.github.io/patitas/) |
| **⌾⌾⌾** | [Rosettes](https://github.com/lbliii/rosettes) | Syntax highlighter | [Docs](https://lbliii.github.io/rosettes/) |

Python-native. Free-threading ready. No npm required.
