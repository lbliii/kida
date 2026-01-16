# )彡 Kida

[![PyPI version](https://img.shields.io/pypi/v/kida.svg)](https://pypi.org/project/kida/)
[![Build Status](https://github.com/lbliii/kida/actions/workflows/tests.yml/badge.svg)](https://github.com/lbliii/kida/actions/workflows/tests.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/kida/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**Modern template engine for Python 3.14t**

```python
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")
print(template.render(name="World"))
# Output: Hello, World!
```

---

## Why Kida?

- **AST-native** — Compiles to Python AST directly, no string generation
- **Free-threading ready** — Safe for Python 3.14t concurrent execution (PEP 703)
- **Fast** — Benchmarks on 3.14t: 3.6x (minimal), 1.7x (small), 1.1x (medium), ~1.0x (large), 1.2x (complex); cold-start +7-8% with bytecode cache (details in performance docs)
- **Modern syntax** — Pattern matching, pipeline operator, unified `{% end %}`
- **Zero dependencies** — Pure Python, includes native `Markup` implementation

---

## Installation

```bash
pip install kida-templates
```

Requires Python 3.14+

---

## Quick Start

| Function | Description |
|----------|-------------|
| `Environment()` | Create a template environment |
| `env.from_string(src)` | Compile template from string |
| `env.get_template(name)` | Load template from filesystem |
| `template.render(**ctx)` | Render with context variables |

---

## Features

| Feature | Description | Docs |
|---------|-------------|------|
| **Template Syntax** | Variables, filters, control flow, pattern matching | [Syntax →](https://lbliii.github.io/kida/docs/syntax/) |
| **Inheritance** | Template extends, blocks, includes | [Inheritance →](https://lbliii.github.io/kida/docs/syntax/inheritance/) |
| **Filters & Tests** | 40+ built-in filters, custom filter registration | [Filters →](https://lbliii.github.io/kida/docs/reference/filters/) |
| **Async Support** | Native `async for`, `await` in templates | [Async →](https://lbliii.github.io/kida/docs/syntax/async/) |
| **Caching** | Fragment caching with TTL support | [Caching →](https://lbliii.github.io/kida/docs/syntax/caching/) |
| **Extensibility** | Custom filters, tests, globals, loaders | [Extending →](https://lbliii.github.io/kida/docs/extending/) |

📚 **Full documentation**: [lbliii.github.io/kida](https://lbliii.github.io/kida/)

---

## Usage

<details>
<summary><strong>File-based Templates</strong> — Load from filesystem</summary>

```python
from kida import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("page.html")
print(template.render(title="Hello", content="World"))
```

</details>

<details>
<summary><strong>Template Inheritance</strong> — Extend base templates</summary>

**base.html:**
```kida
<!DOCTYPE html>
<html>
<body>
    {% block content %}{% end %}
</body>
</html>
```

**page.html:**
```kida
{% extends "base.html" %}
{% block content %}
    <h1>{{ title }}</h1>
    <p>{{ content }}</p>
{% end %}
```

</details>

<details>
<summary><strong>Control Flow</strong> — Conditionals, loops, pattern matching</summary>

```kida
{% if user.is_active %}
    <p>Welcome, {{ user.name }}!</p>
{% end %}

{% for item in items %}
    <li>{{ item.name }}</li>
{% end %}

{% match status %}
{% case "active" %}
    Active user
{% case "pending" %}
    Pending verification
{% case _ %}
    Unknown status
{% end %}
```

</details>

<details>
<summary><strong>Filters & Pipelines</strong> — Transform values</summary>

```kida
{# Traditional syntax #}
{{ title | escape | capitalize | truncate(50) }}

{# Pipeline operator #}
{{ title |> escape |> capitalize |> truncate(50) }}

{# Custom filters #}
{{ items | sort(attribute="name") | first }}
```

</details>

<details>
<summary><strong>Async Templates</strong> — Await in templates</summary>

```python
{% async for item in fetch_items() %}
    {{ item }}
{% end %}

{{ await get_user() }}
```

</details>

<details>
<summary><strong>Fragment Caching</strong> — Cache expensive blocks</summary>

```kida
{% cache "navigation" %}
    {% for item in nav_items %}
        <a href="{{ item.url }}">{{ item.title }}</a>
    {% end %}
{% end %}
```

</details>

---

## Jinja2 Comparison

| Feature | Kida | Jinja2 |
|---------|------|--------|
| **Compilation** | AST → AST | String generation |
| **Rendering** | StringBuilder | Generator yields |
| **Block endings** | Unified `{% end %}` | `{% endif %}`, `{% endfor %}` |
| **Scoping** | Explicit `let`/`set`/`export` | Implicit |
| **Async** | Native `async for`, `await` | `auto_await()` wrapper |
| **Pattern matching** | `{% match %}...{% case %}` | N/A |
| **Null coalescing** | `{{ a ?? b }}` | `{{ a \| default(b) }}` |
| **Optional chaining** | `{{ obj?.attr }}` | N/A |
| **Pipeline syntax** | `{{ value \|> filter }}` | `{{ value \| filter }}` |
| **Caching** | `{% cache key %}...{% end %}` | N/A (extension required) |
| **Free-threading** | Native (PEP 703) | N/A |

---

## Architecture

<details>
<summary><strong>Compilation Pipeline</strong> — AST-native</summary>

```
Template Source → Lexer → Parser → Kida AST → Compiler → Python AST → exec()
```

Unlike Jinja2 which generates Python source strings, Kida generates `ast.Module` objects directly. This enables:

- **Structured code manipulation** — Transform and optimize AST nodes
- **Compile-time optimization** — Dead code elimination, constant folding
- **Precise error source mapping** — Exact line/column in template source

</details>

<details>
<summary><strong>StringBuilder Rendering</strong> — O(n) output</summary>

```python
# Kida's approach (O(n))
_out.append(...)
return "".join(_out)

# vs Jinja2's approach (higher overhead)
yield ...
```

25-40% faster than Jinja2's generator yield pattern for typical templates.

</details>

<details>
<summary><strong>Thread Safety</strong> — Free-threading ready</summary>

All public APIs are thread-safe by design:

- **Template compilation** — Idempotent (same input → same output)
- **Rendering** — Uses only local state (StringBuilder pattern)
- **Environment** — Copy-on-write for filters/tests/globals
- **LRU caches** — Atomic operations

Module declares itself GIL-independent via `_Py_mod_gil = 0` (PEP 703).

</details>

---

## Performance

| Metric | Kida | Jinja2 | Improvement |
|--------|------|--------|-------------|
| Simple render | 0.12ms | 0.18ms | **33% faster** |
| Complex template | 2.1ms | 3.2ms | **34% faster** |
| Concurrent (8 threads) | 0.15ms avg | GIL contention | **Free-threading** |

---

## Documentation

📚 **[lbliii.github.io/kida](https://lbliii.github.io/kida/)**

| Section | Description |
|---------|-------------|
| [Get Started](https://lbliii.github.io/kida/docs/get-started/) | Installation and quickstart |
| [Syntax](https://lbliii.github.io/kida/docs/syntax/) | Template language reference |
| [Usage](https://lbliii.github.io/kida/docs/usage/) | Loading, rendering, escaping |
| [Extending](https://lbliii.github.io/kida/docs/extending/) | Custom filters, tests, loaders |
| [Reference](https://lbliii.github.io/kida/docs/reference/) | Complete API documentation |
| [Tutorials](https://lbliii.github.io/kida/docs/tutorials/) | Jinja2 migration, Flask integration |

---

## Development

```bash
git clone https://github.com/lbliii/kida.git
cd kida
# Uses Python 3.14t by default (.python-version)
uv sync --group dev --python 3.14t
PYTHON_GIL=0 uv run --python 3.14t pytest
```

---

## The Bengal Cat Family

The Bengal Cat Family's core components are written in pure Python:

| | | |
|--:|---|---|
| **ᓚᘏᗢ** | [Bengal](https://github.com/lbliii/bengal) | Static site generator |
| **)彡** | **Kida** | Template engine ← You are here |
| **⌾⌾⌾** | [Rosettes](https://github.com/lbliii/rosettes) | Syntax highlighter |
| **ฅᨐฅ** | [Patitas](https://github.com/lbliii/patitas) | Markdown parser |

Python-native. Free-threading ready. No npm required.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
