---
title: Tutorials
description: Step-by-step guides for Jinja2 migration, framework integration, and common Kida workflows
draft: false
weight: 40
lang: en
type: doc
tags:
- tutorials
keywords:
- tutorials
- guides
- migration
- jinja2 migration
- python template engine
category: tutorials
cascade:
  type: doc
icon: notepad
---

# Tutorials

Start with the framework you already use, or follow a migration and workflow
guide below. Every framework quickstart targets Python 3.14+ and reaches a
typed component plus fragment response in about ten minutes.

:::{cards}
:columns: 1
:gap: medium

:::{card} Flask Integration
:icon: globe
:link: /docs/tutorials/flask-integration/
:description: Add a typed component to Flask
:badge: 10 minutes
Build a form and a named fragment route through Kida's Flask adapter.
:::{/card}

:::{card} Django Integration
:icon: globe
:link: /docs/tutorials/django-integration/
:description: Add a typed component to Django
:badge: 10 minutes
Configure Kida as a backend, then render a full form and a named fragment.
:::{/card}

:::{card} FastAPI & Starlette Integration
:icon: zap
:link: /docs/tutorials/starlette-integration/
:description: Add a typed component to FastAPI
:badge: 10 minutes
Build a form and fragment endpoint, with Starlette and streaming patterns.
:::{/card}

:::{card} Migrate from Jinja2
:icon: arrow-right
:link: /docs/tutorials/migrate-from-jinja2/
:description: Switch from Jinja2 to Kida
:badge: Popular
Step-by-step migration with before/after examples, API mapping table, and verification steps.
:::{/card}

:::{card} Upgrade to 0.7
:icon: arrow-up
:link: /docs/tutorials/upgrade-to-v0.7/
:description: Migrate to strict-by-default and null-safe idioms
:badge: 0.7
Three fix patterns for the strict_undefined flip, the escape hatch, and the new `?.` / `| get` operators.
:::{/card}

:::{card} Refactor-Safe Templates
:icon: tree-structure
:link: /docs/tutorials/refactor-safe-templates/
:description: Move folders without breaking includes
:badge: 0.8
Use `./` / `../` for co-located partials and `@alias/` for shared libraries so folder moves become zero-edit refactors.
:::{/card}

:::{card} Build Custom Filters
:icon: filter
:link: /docs/tutorials/custom-filters/
:description: Create your own template filters
Build custom filters from scratch with examples for common use cases.
:::{/card}

:::{card} Agent Integration
:icon: cpu
:link: /docs/tutorials/agent-integration/
:description: Wire AI agents to Kida via AMP
Configure Claude, Copilot, or Cursor to produce structured reviews rendered as PR comments.
:::{/card}

:::{card} Terminal Rendering
:icon: terminal
:link: /docs/tutorials/terminal-rendering/
:description: Build rich terminal output with colors, components, and live updates
Render templates to the terminal with ANSI colors, LiveRenderer animation, and static_context optimization.
:::{/card}

:::{/cards}
