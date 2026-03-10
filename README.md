# )彡 Kida

[![PyPI version](https://img.shields.io/pypi/v/kida-templates.svg)](https://pypi.org/project/kida-templates/)
[![Build Status](https://github.com/lbliii/kida/actions/workflows/tests.yml/badge.svg)](https://github.com/lbliii/kida/actions/workflows/tests.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/kida-templates/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**A Python template engine and Jinja2 alternative for HTML templates, streaming, and framework integration**

```python
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")
print(template.render(name="World"))
# Output: Hello, World!
```

---

## What is Kida?

Kida is a modern template engine for Python 3.14t. It works for static site generation (Bengal), dynamic web apps (Chirp), and anywhere you need templates — same syntax, same engine. It compiles templates to Python AST directly (no string generation), supports streaming and block rendering, and is built for free-threading.

**Why people pick it:**

- **AST-native** — Compiles to Python AST directly. Structured code manipulation, compile-time optimization, precise error source mapping.
- **Free-threading ready** — Safe for Python 3.14t concurrent execution (PEP 703). All public APIs are thread-safe.
- **Dual-mode rendering** — `render()` uses StringBuilder for maximum throughput. `render_stream()` yields chunks for streaming HTTP and SSE.
- **Modern syntax** — Pattern matching, pipeline operator, unified `{% end %}`, null coalescing, optional chaining.
- **Zero dependencies** — Pure Python, includes native `Markup` implementation.

## Use Kida For

- **HTML template rendering** — Pages, partials, emails, and reusable components
- **Jinja2-style migration paths** — Familiar syntax with new features and different internals
- **Streaming interfaces** — Chunked HTML, SSE, and progressive rendering
- **Framework integration** — Block rendering, introspection, and template analysis for app frameworks
- **Python 3.14+ template stacks** — Async rendering and free-threading-friendly execution

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
| `template.render(**ctx)` | Full page (StringBuilder, fastest) |
| `template.render_block(name, **ctx)` | Single block (fragments, HTMX) |
| `template.render_stream(**ctx)` | Generator (chunked HTTP, SSE) |
| `template.render_async(**ctx)` | Async buffered output |
| `template.render_stream_async(**ctx)` | Async streaming (for `{% async for %}`) |
| `template.render_with_blocks(overrides, **ctx)` | Compose layout with pre-rendered blocks |
| `template.list_blocks()` | Block names for validation |
| `template.template_metadata()` | Full analysis (blocks, regions, dependencies) |
| `validate_block_exists(env, template, block)` | Check block exists before render_block |
| `RenderedTemplate(template, ctx)` | Lazy iterable wrapper for streaming |

---

## Features

| Feature | Description | Docs |
|---------|-------------|------|
| **Jinja2 Migration** | Learn where syntax matches, what changes, and how to switch safely | [Migrate from Jinja2 →](https://lbliii.github.io/kida/docs/tutorials/migrate-from-jinja2/) |
| **Framework Integration** | Block rendering, metadata, and adapters for web frameworks | [Framework Integration →](https://lbliii.github.io/kida/docs/usage/framework-integration/) |
| **Template Syntax** | Variables, filters, control flow, pattern matching | [Syntax →](https://lbliii.github.io/kida/docs/syntax/) |
| **Inheritance** | Template extends, blocks, includes | [Inheritance →](https://lbliii.github.io/kida/docs/syntax/inheritance/) |
| **Filters & Tests** | 50+ built-in filters, custom filter registration | [Filters →](https://lbliii.github.io/kida/docs/reference/filters/) |
| **Streaming** | Statement-level generator rendering via `render_stream()` | [Streaming →](https://lbliii.github.io/kida/docs/usage/streaming/) |
| **Async Support** | Native `async for`, `await` in templates | [Async →](https://lbliii.github.io/kida/docs/syntax/async/) |
| **Caching** | Fragment caching with TTL support | [Caching →](https://lbliii.github.io/kida/docs/syntax/caching/) |
| **Components & Slots** | `{% def %}`, `{% call %}`, default + named `{% slot %}` | [Functions →](https://lbliii.github.io/kida/docs/syntax/functions/) |
| **Regions** | `{% region name(params) %}...{% end %}` — parameterized blocks for render_block | [Functions →](https://lbliii.github.io/kida/docs/syntax/functions/#regions) |
| **Block Rendering** | `render_block()`, `render_with_blocks()` for fragments and layout composition | [Framework Integration →](https://lbliii.github.io/kida/docs/usage/framework-integration/) |
| **Introspection** | `template_metadata()`, `block_metadata()`, `validate_context()` for frameworks | [Analysis →](https://lbliii.github.io/kida/docs/advanced/analysis/) |
| **Partial Evaluation** | Compile-time evaluation via `static_context` | [Advanced →](https://lbliii.github.io/kida/docs/advanced/compiler/) |
| **Block Recompilation** | Recompile only changed blocks in live templates | [Advanced →](https://lbliii.github.io/kida/docs/advanced/compiler/) |
| **Extensibility** | Custom filters, tests, globals, loaders | [Extending →](https://lbliii.github.io/kida/docs/extending/) |
| **T-Strings (PEP 750)** | `k()` auto-escaping, `r()` composable regex (Python 3.14+) | [T-Strings →](https://lbliii.github.io/kida/docs/advanced/t-strings/) |
| **HTMX Helpers** | `hx_request()`, `hx_target()`, `csrf_token()` for partials | [Custom Globals →](https://lbliii.github.io/kida/docs/extending/custom-globals/) |
| **Worker Auto-Tuning** | `get_optimal_workers()`, `should_parallelize()` for parallel render | [Workers →](https://lbliii.github.io/kida/docs/advanced/workers/) |

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
<summary><strong>Regions</strong> — Parameterized blocks for render_block</summary>

```kida
{% region sidebar(current_path="/") %}
  <nav>{{ current_path }}</nav>
{% end %}

{{ sidebar(current_path="/about") }}
```

Regions are both blocks (for `render_block()`) and callables (for `{{ name(args) }}`).
They can read outer-context variables. Use for HTMX OOB, layout composition, and
framework integration. See [Functions → Regions](https://lbliii.github.io/kida/docs/syntax/functions/#regions).

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

<details>
<summary><strong>Block Rendering</strong> — Fragments and layout composition</summary>

```python
# Render a single block (HTMX partials, cached nav)
html = template.render_block("content", title="Hello")

# Compose layout with pre-rendered blocks
layout = env.get_template("_layout.html")
html = layout.render_with_blocks({"content": inner_html}, title="Page")
```

</details>

---

## Use Cases

| Use case | Key APIs | Example |
|----------|----------|---------|
| **Static sites** | `render()`, fragment cache, bytecode cache | [Bengal](https://github.com/lbliii/bengal) |
| **Dynamic web** | `render_block()`, `render_stream()`, `render_with_blocks()` | [Chirp](https://github.com/lbliii/chirp) |
| **Streaming / SSE** | `render_stream()`, `render_stream_async()` | Chunked HTTP, LLM streaming |
| **Framework integration** | `template_metadata()`, `validate_block_exists()`, `get_structure()` | Build adapters, validate routes |

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

- **Minimal** — ~3.5µs (file-based)
- **Medium** — ~0.4ms (~100 vars)
- **Large** — ~1.9ms (1000 loop items)
- **Concurrent (8 workers)** — scales with worker count under Python 3.14t free-threading

See [benchmarks/README.md](benchmarks/README.md) and [benchmarks/RESULTS.md](benchmarks/RESULTS.md) for full Kida vs Jinja2 comparison.

---

## Documentation

📚 **[lbliii.github.io/kida](https://lbliii.github.io/kida/)**

| Section | Description |
|---------|-------------|
| [Get Started](https://lbliii.github.io/kida/docs/get-started/) | Installation and quickstart |
| [Syntax](https://lbliii.github.io/kida/docs/syntax/) | Template language reference |
| [Usage](https://lbliii.github.io/kida/docs/usage/) | Loading, rendering, escaping |
| [Framework Integration](https://lbliii.github.io/kida/docs/usage/framework-integration/) | Block rendering, introspection, adapters |
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
