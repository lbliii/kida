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

## What's good about it

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

:::{card} Zero Dependencies
:icon: package
Pure Python with no runtime dependencies. Includes native `Markup` class—no markupsafe required.
:::{/card}

:::{/cards}

---

## Performance

StringBuilder rendering for O(n) concatenation:

```python
# Kida: O(n) StringBuilder
_out.append(...)
return "".join(_out)
```

| Template Size | Time |
|---------------|------|
| Small (10 vars) | ~0.3ms |
| Medium (100 vars) | ~2ms |
| Large (1000 vars) | ~15ms |

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
| **)彡** | **Kida** | Template engine ← You are here | [Docs](https://lbliii.github.io/kida/) |
| **ฅᨐฅ** | [Patitas](https://github.com/lbliii/patitas) | Markdown parser | [Docs](https://lbliii.github.io/patitas/) |
| **⌾⌾⌾** | [Rosettes](https://github.com/lbliii/rosettes) | Syntax highlighter | [Docs](https://lbliii.github.io/rosettes/) |

Python-native. Free-threading ready. No npm required.
