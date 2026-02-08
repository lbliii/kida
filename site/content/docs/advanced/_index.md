---
title: Advanced
description: Advanced features for framework authors and power users
draft: false
weight: 60
lang: en
type: doc
tags:
- advanced
keywords:
- advanced
- framework
- internals
category: advanced
cascade:
  type: doc
icon: cpu
---

# Advanced

Features for framework authors, SSG/SSR builders, and power users who need to go beyond standard template rendering.

:::{cards}
:columns: 2
:gap: medium

:::{card} Static Analysis
:icon: magnifying-glass
:link: ./analysis
:description: Analyze templates for dependencies, purity, and caching potential
Extract dependency paths, validate contexts, and plan caching strategies.
:::{/card}

:::{card} T-Strings (PEP 750)
:icon: shield
:link: ./t-strings
:description: Auto-escaping HTML and composable regex via Python 3.14 t-strings
Use the `k()` and `r()` tag functions for safe interpolation.
:::{/card}

:::{card} Compiler Internals
:icon: cpu
:link: ./compiler
:description: F-string coalescing, AST preservation, and render modes
Understand and tune the compilation pipeline.
:::{/card}

:::{card} Worker Auto-Tuning
:icon: zap
:link: ./workers
:description: Workload-aware parallelization for free-threaded Python
Optimal worker counts, template scheduling, and environment detection.
:::{/card}

:::{card} Security Hardening
:icon: shield
:link: ./security
:description: Context-specific escaping, URL validation, and attribute safety
Protect against XSS in JavaScript, CSS, and URL contexts.
:::{/card}

:::{card} Profiling
:icon: activity
:link: ./profiling
:description: Opt-in render instrumentation with zero overhead when disabled
Track block timings, macro calls, includes, and filter usage.
:::{/card}

:::{card} Block Caching
:icon: database
:link: ./block-caching
:description: Connect analysis results to runtime block caching
Cache site-scoped blocks for 40-60% faster builds.
:::{/card}

:::{/cards}
