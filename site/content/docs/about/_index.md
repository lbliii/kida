---
title: About
description: Architecture, performance, and design philosophy
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
category: about
cascade:
  type: doc
icon: info
---

# About

Understand Kida's design and capabilities.

:::{cards}
:columns: 2
:gap: medium

:::{card} Architecture
:icon: cpu
:link: ./architecture
:description: How Kida works internally
Lexer → Parser → Compiler → Template pipeline.
:::{/card}

:::{card} Performance
:icon: zap
:link: ./performance
:description: Benchmarks and optimization
StringBuilder rendering, caching strategies.
:::{/card}

:::{card} Thread Safety
:icon: shield
:link: ./thread-safety
:description: Free-threading support
PEP 703 compliance and concurrent rendering.
:::{/card}

:::{card} Comparison
:icon: arrows-angle-contract
:link: ./comparison
:description: Kida vs Jinja2
Comprehensive feature comparison.
:::{/card}

:::{card} FAQ
:icon: help-circle
:link: ./faq
:description: Frequently asked questions
Common questions answered.
:::{/card}

:::{card} Ecosystem
:icon: layers
:link: ./ecosystem
:description: The Bengal stack
All seven projects in the reactive Python stack.
:::{/card}

:::{/cards}
