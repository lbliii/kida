---
title: Troubleshooting
description: Common errors and how to fix them
draft: false
weight: 70
lang: en
type: doc
tags:
- troubleshooting
keywords:
- troubleshooting
- errors
- debugging
category: troubleshooting
cascade:
  type: doc
icon: alert-triangle
---

# Troubleshooting

Common errors and solutions.

:::{cards}
:columns: 2
:gap: medium

:::{card} Undefined Variable
:icon: alert-circle
:link: /docs/troubleshooting/undefined-variable/
:description: UndefinedError debugging
Variable not found or None handling.
:::{/card}

:::{card} Template Not Found
:icon: file-x
:link: /docs/troubleshooting/template-not-found/
:description: TemplateNotFoundError debugging
Template loading and path issues.
:::{/card}

:::{card} Circular Imports
:icon: git-branch
:link: /docs/troubleshooting/circular-imports/
:description: K-TPL-003 — Circular macro import
{% from %} must not import self or create cycles.
:::{/card}

:::{card} render_block and Def Scope
:icon: layers
:link: /docs/troubleshooting/render-block-scope/
:description: Blocks don't inherit defs
Split defs into a separate file when using render_block.
:::{/card}

:::{/cards}
