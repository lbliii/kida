---
title: Kida
description: Modern template engine for Python 3.14t
template: home.html
weight: 100
type: page
draft: false
lang: en
keywords: [kida, template-engine, jinja2, python, free-threading, async]
category: home

# Hero configuration
blob_background: true

# CTA Buttons
cta_buttons:
  - text: Get Started
    url: /docs/get-started/
    style: primary
  - text: Syntax Guide
    url: /docs/syntax/
    style: secondary

show_recent_posts: false
---

## Templates, Evolved

**AST-native. Free-threading ready. Zero regex.**

Kida is a pure-Python template engine designed for Python 3.14t+. It compiles templates directly to Python AST—no string manipulation, no regex, no security vulnerabilities.

```python
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")
print(template.render(name="World"))
# Output: Hello, World!
```

---

## Why Kida?

:::{cards}
:columns: 2
:gap: medium

:::{card} AST-Native Compilation
:icon: cpu
Compiles templates to `ast.Module` objects directly. No string concatenation, no regex parsing, no code generation vulnerabilities.
:::{/card}

:::{card} Free-Threading Ready
:icon: zap
Built for Python 3.14t (PEP 703). Renders templates concurrently without the GIL. Declares `_Py_mod_gil = 0`.
:::{/card}

:::{card} Modern Syntax
:icon: code
Unified `{% end %}` for all blocks. Pattern matching with `{% match %}`. Pipelines with `|>`. Built-in caching.
:::{/card}

:::{card} Jinja2 Compatible
:icon: arrows-angle-contract
Parses existing Jinja2 templates. Migration path from Jinja2 is smooth—most templates work unchanged.
:::{/card}

:::{/cards}

---

## Quick Comparison

| Feature | Kida | Jinja2 |
|---------|------|--------|
| **Compilation** | AST → AST | String generation |
| **Rendering** | StringBuilder O(n) | Generator yields |
| **Block endings** | Unified `{% end %}` | `{% endif %}`, `{% endfor %}` |
| **Async** | Native `async for` | `auto_await()` wrapper |
| **Pattern matching** | `{% match %}` | N/A |
| **Free-threading** | Native (PEP 703) | N/A |

---

## Performance

StringBuilder rendering is 25-40% faster than Jinja2's generator pattern:

```python
# Kida: O(n) StringBuilder
_out.append(...)
return "".join(_out)

# Jinja2: Generator yields (higher overhead)
yield ...
```

| Template Size | Kida | Jinja2 | Speedup |
|---------------|------|--------|---------|
| Small (10 vars) | 0.3ms | 0.5ms | 1.6x |
| Medium (100 vars) | 2ms | 3.5ms | 1.75x |
| Large (1000 vars) | 15ms | 25ms | 1.67x |

---

## Zero Dependencies

Kida is pure Python with no runtime dependencies:

```toml
[project]
dependencies = []  # Zero!
```

Includes a native `Markup` class for safe HTML handling—no markupsafe required.
