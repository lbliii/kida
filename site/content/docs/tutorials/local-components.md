---
title: "Build App-Owned Local Components"
description: Compose typed Kida controls and product patterns with ordinary application CSS and server-rendered state
draft: false
weight: 12
lang: en
type: doc
tags:
- tutorial
- components
- css
keywords:
- local components
- app-owned css
- scoped slots
- server rendered state
icon: puzzle
---

# Build App-Owned Local Components

The runnable [`examples/local_components`](https://github.com/lbliii/kida/tree/main/examples/local_components)
shows a modular application without a component-library abstraction. Kida owns
typed props, slots, imports, metadata, and diagnostics. The application owns
its component boundaries, product patterns, CSS variables, visual identity,
and asset delivery.

## Follow the ownership tree

```text
templates/
  components/controls.html
  patterns/search-panel.html
  pages/search.html
static/
  tokens.css
  components.css
```

The reusable controls own accessibility policy such as label/input association.
The search panel owns a stable product concept: its form, live result status,
empty state, iteration, and scoped result seam. Route-specific result-card
markup remains inline in the page because extracting it would add indirection
without adding policy or another interface.

The query and results are rendered on the server. A `role="status"`
`aria-live="polite"` region communicates the returned state; no client-side UI
state or JavaScript framework is required.

## Validate the boundaries

From the repository root:

```bash
uv run python examples/local_components/app.py
uv run kida check \
  --root app=examples/local_components/templates \
  --validate-calls --a11y
uv run kida components \
  --root app=examples/local_components/templates \
  --json
```

The namespaced root gives every template a stable `app/...` identifier. JSON
component records retain the owning root, physical source path, typed props,
and slots. A misspelled required prop produces `K-CMP-001` at the owned call
site. A malformed scoped-slot declaration produces `K-PAR-001` with the valid
`let:` syntax before render.

## Keep CSS ordinary

`tokens.css` defines semantic custom properties; `components.css` uses ordinary
CSS layers for controls and the product pattern. Kida does not invent a token
schema, selector transform, theme persistence API, router, or frontend build
step. Adapters may supply explicit additional roots and response roles, but
those conventions stay outside Kida core.

The [app-owned authoring contract](/docs/usage/components/#app-owned-authoring-contract)
explains the extraction rules behind the example. The pinned
[Chirp downstream pilot](https://github.com/lbliii/kida/issues/280#issuecomment-5006187657)
proves the same loader-ownership boundary in a real framework adapter without
making `chirp-ui` an ambient dependency.
