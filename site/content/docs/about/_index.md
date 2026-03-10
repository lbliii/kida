---
title: About
description: Architecture, performance, comparisons, and design philosophy for the Kida Python template engine
draft: false
weight: 00
lang: en
type: doc
tags:
- about
keywords:
- about
- architecture
- performance
- python template engine
- jinja2 alternative
category: about
cascade:
  type: doc
icon: info
---

# About

Understand Kida's design, performance profile, and where it fits as a Python template
engine or Jinja2 alternative.

:::{cards}
:columns: 2
:gap: medium

:::{card} Architecture
:icon: cpu
:link: /docs/about/architecture/
:description: How Kida works internally
Lexer → Parser → Compiler → Template pipeline.
:::{/card}

:::{card} Performance
:icon: zap
:link: /docs/about/performance/
:description: Benchmarks and optimization
StringBuilder rendering, caching strategies.
:::{/card}

:::{card} Thread Safety
:icon: shield
:link: /docs/about/thread-safety/
:description: Free-threading support
PEP 703 compliance and concurrent rendering.
:::{/card}

:::{card} Syntax and Features
:icon: arrows-angle-contract
:link: /docs/about/comparison/
:description: Kida syntax, comparisons, and when it fits
Syntax reference, Jinja2 comparison, and migration notes.
:::{/card}

:::{card} FAQ
:icon: help-circle
:link: /docs/about/faq/
:description: Frequently asked questions
Common questions answered.
:::{/card}

:::{card} Ecosystem
:icon: layers
:link: /docs/about/ecosystem/
:description: The Bengal stack
All seven projects in the reactive Python stack.
:::{/card}

:::{/cards}
