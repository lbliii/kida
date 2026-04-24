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

Step-by-step guides for common Kida usage scenarios, migration paths, and integration
workflows.

:::{cards}
:columns: 1
:gap: medium

:::{card} Migrate from Jinja2
:icon: arrow-right
:link: /docs/tutorials/migrate-from-jinja2/
:description: Switch from Jinja2 to Kida
:badge: Popular
Step-by-step migration with before/after examples, API mapping table, and verification steps.
:::{/card}

:::{card} Upgrade to 0.7
:icon: arrow-up-circle
:link: /docs/tutorials/upgrade-to-v0.7/
:description: Migrate to strict-by-default and null-safe idioms
:badge: 0.7
Three fix patterns for the strict_undefined flip, the escape hatch, and the new `?.` / `| get` operators.
:::{/card}

:::{card} Refactor-Safe Templates
:icon: folder-tree
:link: /docs/tutorials/refactor-safe-templates/
:description: Move folders without breaking includes
:badge: 0.9
Use `./` / `../` for co-located partials and `@alias/` for shared libraries so folder moves become zero-edit refactors.
:::{/card}

:::{card} Flask Integration
:icon: globe
:link: /docs/tutorials/flask-integration/
:description: Use Kida with Flask
Set up Kida as Flask's template engine with custom filters and error handling.
:::{/card}

:::{card} Django Integration
:icon: globe
:link: /docs/tutorials/django-integration/
:description: Use Kida with Django
Configure Kida as a Django template backend with settings and views.
:::{/card}

:::{card} Starlette Integration
:icon: zap
:link: /docs/tutorials/starlette-integration/
:description: Use Kida with Starlette and FastAPI
Async rendering, streaming responses, and HTMX patterns.
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
