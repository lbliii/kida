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
:link: /docs/advanced/analysis/
:description: Analyze templates for dependencies, purity, and caching potential
Extract dependency paths, validate contexts, and plan caching strategies.
:::{/card}

:::{card} T-Strings (PEP 750)
:icon: shield
:link: /docs/advanced/t-strings/
:description: Auto-escaping HTML and composable regex via Python 3.14 t-strings
Use the `k()` and `r()` tag functions for safe interpolation.
:::{/card}

:::{card} Compiler Internals
:icon: cpu
:link: /docs/advanced/compiler/
:description: F-string coalescing, AST preservation, and render modes
Understand and tune the compilation pipeline.
:::{/card}

:::{card} Worker Auto-Tuning
:icon: zap
:link: /docs/advanced/workers/
:description: Workload-aware parallelization for free-threaded Python
Optimal worker counts, template scheduling, and environment detection.
:::{/card}

:::{card} Security Hardening
:icon: shield
:link: /docs/advanced/security/
:description: Context-specific escaping, URL validation, and attribute safety
Protect against XSS in JavaScript, CSS, and URL contexts.
:::{/card}

:::{card} Profiling
:icon: activity
:link: /docs/advanced/profiling/
:description: Opt-in render instrumentation with zero overhead when disabled
Track block timings, macro calls, includes, and filter usage.
:::{/card}

:::{card} Block Caching
:icon: database
:link: /docs/advanced/block-caching/
:description: Connect analysis results to runtime block caching
Cache site-scoped blocks for 40-60% faster builds.
:::{/card}

:::{card} Scoped Slots
:icon: layers
:link: /docs/advanced/scoped-slots/
:description: Pass data back from components to callers
Use `let:` bindings on slots for data-driven component APIs.
:::{/card}

:::{card} Content Stacks
:icon: stack
:link: /docs/advanced/content-stacks/
:description: Collect content from nested templates
Use `{% push %}` and `{% stack %}` for deferred CSS, JS, and meta tags.
:::{/card}

:::{card} Sandbox
:icon: lock
:link: /docs/advanced/sandbox/
:description: Restricted execution for untrusted templates
Limit attribute access, function calls, and imports.
:::{/card}

:::{card} CSP Nonces
:icon: shield-check
:link: /docs/advanced/csp/
:description: Content Security Policy nonce injection
Auto-inject nonces into `<script>` and `<style>` tags.
:::{/card}

:::{card} Coverage
:icon: check-circle
:link: /docs/advanced/coverage/
:description: Measure template render coverage
Track which blocks, branches, and filters execute.
:::{/card}

:::{card} Type Checking
:icon: type
:link: /docs/advanced/type-checking/
:description: Static type analysis for template contexts
Catch missing variables and type mismatches before rendering.
:::{/card}

:::{card} Accessibility Linting
:icon: eye
:link: /docs/advanced/a11y-linting/
:description: Check templates for accessibility issues
Detect missing alt text, form labels, and ARIA attributes.
:::{/card}

:::{card} Formatter
:icon: align-left
:link: /docs/advanced/formatter/
:description: Auto-format template source code
Normalize indentation, whitespace, and tag style.
:::{/card}

:::{/cards}
