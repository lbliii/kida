# )彡 Kida

[![PyPI version](https://img.shields.io/pypi/v/kida-templates.svg)](https://pypi.org/project/kida-templates/)
[![Build Status](https://github.com/lbliii/kida/actions/workflows/tests.yml/badge.svg)](https://github.com/lbliii/kida/actions/workflows/tests.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/kida-templates/)
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

## What is Kida?

Kida is a modern template engine for Python 3.14t. It compiles templates to Python AST directly (no string generation), supports streaming and fragment rendering, and is built for free-threading.

**What's good about it:**

- **AST-native** — Compiles to Python AST directly. Structured code manipulation, compile-time optimization, precise error source mapping.
- **Free-threading ready** — Safe for Python 3.14t concurrent execution (PEP 703). All public APIs are thread-safe.
- **Dual-mode rendering** — `render()` uses StringBuilder for maximum throughput. `render_stream()` yields chunks for streaming HTTP and SSE.
- **Modern syntax** — Pattern matching, pipeline operator, unified `{% end %}`, null coalescing, optional chaining.
- **Zero dependencies** — Pure Python, includes native `Markup` implementation.

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
| `template.render(**ctx)` | Render to string (StringBuilder, fastest) |
| `template.render_stream(**ctx)` | Render as generator (yields chunks) |
| `RenderedTemplate(template, ctx)` | Lazy iterable wrapper for streaming |

---

## Features

| Feature | Description | Docs |
|---------|-------------|------|
| **Template Syntax** | Variables, filters, control flow, pattern matching | [Syntax →](https://lbliii.github.io/kida/docs/syntax/) |
| **Inheritance** | Template extends, blocks, includes | [Inheritance →](https://lbliii.github.io/kida/docs/syntax/inheritance/) |
| **Filters & Tests** | 40+ built-in filters, custom filter registration | [Filters →](https://lbliii.github.io/kida/docs/reference/filters/) |
| **Streaming** | Statement-level generator rendering via `render_stream()` | [Streaming →](https://lbliii.github.io/kida/docs/usage/streaming/) |
| **Async Support** | Native `async for`, `await` in templates | [Async →](https://lbliii.github.io/kida/docs/syntax/async/) |
| **Caching** | Fragment caching with TTL support | [Caching →](https://lbliii.github.io/kida/docs/syntax/caching/) |
| **Components & Slots** | `{% def %}`, `{% call %}`, default + named `{% slot %}` | [Functions →](https://lbliii.github.io/kida/docs/syntax/functions/) |
| **Partial Evaluation** | Compile-time evaluation of static expressions | [Advanced →](https://lbliii.github.io/kida/docs/advanced/compiler/) |
| **Block Recompilation** | Recompile only changed blocks in live templates | [Advanced →](https://lbliii.github.io/kida/docs/advanced/compiler/) |
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
<summary><strong>Components & Named Slots</strong> — Reusable UI composition</summary>

```kida
{% def card(title) %}
<article class="card">
  <h2>{{ title }}</h2>
  <div class="actions">{% slot header_actions %}</div>
  <div class="body">{% slot %}</div>
</article>
{% end %}

{% call card("Settings") %}
  {% slot header_actions %}<button>Save</button>{% end %}
  <p>Body content.</p>
{% end %}
```

`{% slot %}` is the default slot. Named slot blocks inside `{% call %}` map to
matching placeholders in `{% def %}`.

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
<summary><strong>Streaming Rendering</strong> — Yield chunks as they're ready</summary>

```python
from kida import Environment

env = Environment()
template = env.from_string("""
<ul>
{% for item in items %}
    <li>{{ item }}</li>
{% end %}
</ul>
""")

# Generator: yields each statement as a string chunk
for chunk in template.render_stream(items=["a", "b", "c"]):
    print(chunk, end="")

# RenderedTemplate: lazy iterable wrapper
from kida import RenderedTemplate
rendered = RenderedTemplate(template, {"items": ["a", "b", "c"]})
for chunk in rendered:
    send_to_client(chunk)
```

Works with inheritance (`{% extends %}`), includes, and all control flow. Blocks like `{% capture %}` and `{% spaceless %}` buffer internally and yield the processed result.

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

## Architecture

<details>
<summary><strong>Compilation Pipeline</strong> — AST-native</summary>

```
Template Source → Lexer → Parser → Kida AST → Compiler → Python AST → exec()
```

Kida generates `ast.Module` objects directly. This enables:

- **Structured code manipulation** — Transform and optimize AST nodes
- **Compile-time optimization** — Dead code elimination, constant folding
- **Precise error source mapping** — Exact line/column in template source

</details>

<details>
<summary><strong>Dual-Mode Rendering</strong> — StringBuilder + streaming generator</summary>

```python
# render() — StringBuilder (fastest, default)
_out.append(...)
return "".join(_out)

# render_stream() — Generator (streaming, chunked HTTP)
yield ...
```

The compiler generates both modes from a single template. `render()` uses StringBuilder for maximum throughput. `render_stream()` uses Python generators for statement-level streaming — ideal for chunked HTTP responses and Server-Sent Events.

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

- **Simple render** — ~0.12ms
- **Complex template** — ~2.1ms
- **Concurrent (8 threads)** — ~0.15ms avg under Python 3.14t free-threading

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

---

## License

MIT License — see [LICENSE](LICENSE) for details.
