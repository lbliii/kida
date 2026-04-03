# )彡 Kida

[![PyPI version](https://img.shields.io/pypi/v/kida-templates.svg)](https://pypi.org/project/kida-templates/)
[![Build Status](https://github.com/lbliii/kida/actions/workflows/tests.yml/badge.svg)](https://github.com/lbliii/kida/actions/workflows/tests.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/kida-templates/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**A template engine that compiles to Python AST, renders to HTML/terminal/markdown, and scales across cores on free-threaded Python.**

```python
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")
print(template.render(name="World"))
# Hello, World!
```

---

## Why Kida

Most template engines generate Python source code as strings, then `exec()` it. Kida compiles directly to `ast.Module` — the same structured representation Python itself uses. This unlocks compile-time optimization, precise error mapping, and safe concurrent rendering that string-based engines can't achieve.

| | Kida | Jinja2 |
|---|---|---|
| **Compilation target** | Python AST (`ast.Module`) | Python source strings |
| **Free-threading (PEP 703)** | Safe under `PYTHON_GIL=0` | Not tested/supported |
| **Rendering modes** | `render()`, `render_stream()`, `render_block()`, async variants | `render()`, `generate()` |
| **Compile-time optimization** | Constant folding, dead branch elimination, filter eval, component inlining | None |
| **Terminal rendering** | Built-in (`autoescape="terminal"`) with 30+ ANSI-aware filters | None |
| **Pattern matching** | `{% match %}` / `{% case %}` | None |
| **Null safety** | `??`, `?.`, `?|>`, `?|`, `??=` | `| default` only |
| **Components** | `{% def %}` + `{% slot %}` + named slots | Macros (no slots) |
| **Regions** | `{% region name(params) %}` — parameterized blocks | None |
| **Block rendering** | `render_block()`, `render_with_blocks()` | None (third-party) |
| **Fragment caching** | `{% cache "key" %}` built-in | Extension required |

### Performance

| Template complexity | Kida | vs Jinja2 |
|---|---|---|
| Minimal (~4µs) | Baseline | ~1x |
| Small loop + filter (~7µs) | Baseline | ~1x |
| Medium ~100 vars (~0.2ms) | Baseline | ~1.3x faster |
| Large 1000-item loop (~1.6ms) | Baseline | **2.5x faster** |
| Complex 3-level inheritance (~19µs) | Baseline | **1.5x faster** |
| With `static_context` (compile-time folding) | **1.5-2x additional speedup** | N/A |
| Concurrent (2-4 cores, `PYTHON_GIL=0`) | Linear scaling | Not supported |

---

## Installation

```bash
pip install kida-templates
```

Requires Python 3.14+. Zero runtime dependencies.

---

## Render Anywhere

Kida renders to three surfaces from the same template syntax.

### HTML (default)

```python
from kida import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("page.html")
html = template.render(title="Hello")
```

### Terminal

```python
from kida.terminal import terminal_env

env = terminal_env()
template = env.from_string("""
{{ "Deploy Status" | bold | cyan }}
{{ hr(40) }}
{% for svc in services %}
{{ svc.name | pad(20) }}{{ svc.status | badge }}
{% end %}
""")
print(template.render(services=[
    {"name": "api", "status": "pass"},
    {"name": "worker", "status": "fail"},
]))
```

30+ ANSI-aware filters (`bold`, `fg()`, `pad`, `badge`, `bar`, `kv`, `table`, `tree`, `diff`), built-in panel/box components, and `LiveRenderer` for in-place re-rendering with spinners.

### Markdown

```python
from kida.markdown import markdown_env

env = markdown_env()
template = env.from_string("# {{ title }}\n\n{{ body }}")
md = template.render(title="Report", body="All tests passed.")
```

---

## Key Features

<details>
<summary><strong>Template Inheritance</strong></summary>

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
{% end %}
```

</details>

<details>
<summary><strong>Components & Named Slots</strong></summary>

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

</details>

<details>
<summary><strong>Pattern Matching & Null Safety</strong></summary>

```kida
{% match status %}
{% case "active" %}
    Active user
{% case "pending" %}
    Pending verification
{% case _ %}
    Unknown status
{% end %}

{# Null coalescing #}
{{ user.nickname ?? user.name ?? "Anonymous" }}

{# Optional chaining #}
{{ config?.database?.host }}

{# Safe pipeline — stops on None #}
{{ data ?|> parse ?|> validate ?|> render }}
```

</details>

<details>
<summary><strong>Streaming & Block Rendering</strong></summary>

```python
# Stream chunks as they render (chunked HTTP, SSE)
for chunk in template.render_stream(items=large_list):
    response.write(chunk)

# Render a single block (HTMX partials)
html = template.render_block("content", title="Hello")

# Compose layouts with pre-rendered blocks
html = layout.render_with_blocks({"content": inner_html}, title="Page")
```

</details>

<details>
<summary><strong>Regions — Parameterized Blocks</strong></summary>

```kida
{% region sidebar(current_path="/") %}
  <nav>{{ current_path }}</nav>
{% end %}

{{ sidebar(current_path="/about") }}
```

Regions are blocks (for `render_block()`) and callables (for inline use). Ideal for HTMX OOB swaps and framework integration.

</details>

<details>
<summary><strong>Compile-Time Optimization</strong></summary>

```python
# Pass static data at compile time — kida folds constants,
# eliminates dead branches, and evaluates pure filters
template = env.from_string(source, static_context={
    "site": site_config,
    "settings": app_settings,
})

# Only dynamic data needed at render time
html = template.render(page_title="Home", items=page_items)
```

67 pure filters evaluated at compile time. Dead `{% if debug %}` branches removed entirely. Component inlining for small defs with constant args.

Use `kida render template.html --explain` to see which optimizations are active.

</details>

<details>
<summary><strong>Free-Threading</strong></summary>

All public APIs are safe under `PYTHON_GIL=0` (Python 3.14t, PEP 703):

- Templates compile to immutable AST — no shared mutable state
- Rendering uses thread-local StringBuilder — no contention
- Environment uses copy-on-write for configuration changes
- `LiveRenderer.update()` is thread-safe with internal locking

Module declares GIL independence via `_Py_mod_gil = 0`. Rendering scales linearly with cores.

</details>

<details>
<summary><strong>Framework Integration</strong></summary>

Drop-in adapters for Flask, Starlette/FastAPI, and Django:

```python
# Flask
from kida.contrib.flask import KidaFlask
kida = KidaFlask(app)

# Starlette / FastAPI
from kida.contrib.starlette import KidaStarlette
templates = KidaStarlette(directory="templates")

# Django
TEMPLATES = [{"BACKEND": "kida.contrib.django.KidaDjango", ...}]
```

</details>

---

## GitHub Action — CI Reports

Turn pytest, coverage, ruff, and other tool output into formatted step summaries and PR comments.

```yaml
- name: Run tests
  run: pytest --junitxml=results.xml

- name: Post test report
  uses: lbliii/kida@v0.3.2
  with:
    template: pytest
    data: results.xml
    data-format: junit-xml
```

### Built-in templates

| Template | Data format | Tool |
|----------|-------------|------|
| `pytest` | junit-xml | pytest `--junitxml` |
| `coverage` | json | coverage.py `--json` or lcov |
| `ruff` | json | ruff `--output-format json` |
| `ty` | junit-xml | ty `--output-format junit` |
| `jest` | json | jest `--json` |
| `gotest` | junit-xml | go-junit-report |
| `sarif` | sarif | CodeQL, Semgrep, Trivy, ESLint |

### PR comments with deduplication

```yaml
- name: Post coverage to PR
  uses: lbliii/kida@v0.3.2
  with:
    template: coverage
    data: coverage.json
    post-to: step-summary,pr-comment
```

### Custom templates

```yaml
- uses: lbliii/kida@v0.3.2
  with:
    template: .github/kida-templates/my-report.md
    data: output.json
```

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `template` | *(required)* | Built-in name or path to template file |
| `data` | *(required)* | Path to data file |
| `data-format` | `json` | `json`, `junit-xml`, `sarif`, or `lcov` |
| `post-to` | `step-summary` | `step-summary`, `pr-comment`, or both |
| `comment-header` | template name | Marker for PR comment deduplication |
| `token` | `github.token` | GitHub token (needed for `pr-comment`) |
| `python-version` | `3.14` | Python version (`skip` to use existing) |
| `install` | `true` | Whether to `pip install kida-templates` |

---

## CLI

```bash
# Render a template
kida render template.txt --data context.json
kida render dashboard.txt --mode terminal --width 80 --color truecolor

# Show which compiler optimizations are active
kida render template.html --explain

# Check all templates for syntax errors
kida check templates/

# Strict mode: require explicit end tags ({% endif %} not {% end %})
kida check templates/ --strict

# Validate macro call sites against signatures
kida check templates/ --validate-calls

# Accessibility and type checking
kida check templates/ --a11y --typed

# Auto-format templates
kida fmt templates/
```

---

## API Reference

| Function | Description |
|----------|-------------|
| `Environment()` | Create a template environment |
| `env.from_string(src)` | Compile template from string |
| `env.get_template(name)` | Load template from filesystem |
| `template.render(**ctx)` | Full render (StringBuilder, fastest) |
| `template.render_block(name, **ctx)` | Single block (HTMX partials) |
| `template.render_stream(**ctx)` | Generator (chunked HTTP, SSE) |
| `template.render_async(**ctx)` | Async buffered output |
| `template.render_stream_async(**ctx)` | Async streaming |
| `template.render_with_blocks(overrides, **ctx)` | Compose layout with pre-rendered blocks |
| `template.list_blocks()` | Block names for validation |
| `template.template_metadata()` | Full analysis (blocks, regions, deps) |

Full documentation: **[lbliii.github.io/kida](https://lbliii.github.io/kida/)**. See also: [Kida vs Jinja2](docs/kida-vs-jinja2.md)

| Section | |
|---------|---|
| [Get Started](https://lbliii.github.io/kida/docs/get-started/) | Installation, quickstart, coming from Jinja2 |
| [Syntax](https://lbliii.github.io/kida/docs/syntax/) | Template language reference |
| [Usage](https://lbliii.github.io/kida/docs/usage/) | Loading, rendering, escaping, terminal mode |
| [Framework Integration](https://lbliii.github.io/kida/docs/usage/framework-integration/) | Flask, Starlette, Django adapters |
| [Advanced](https://lbliii.github.io/kida/docs/advanced/) | Compiler, profiling, coverage, security |
| [Reference](https://lbliii.github.io/kida/docs/reference/) | Complete API docs |

---

## Architecture

```
Template Source → Lexer → Parser → Kida AST → Compiler → Python AST → exec()
```

Kida generates `ast.Module` objects directly — no intermediate source strings. This enables compile-time optimization (constant folding, dead branch elimination, filter evaluation), precise error source mapping (exact line:column in template source), and safe concurrent execution (immutable AST, no shared mutable state).

Rendering uses two modes from a single compilation:
- **`render()`** — StringBuilder pattern (`_out.append(...)`) for maximum throughput
- **`render_stream()`** — Python generator (`yield ...`) for statement-level streaming

---

## Development

```bash
git clone https://github.com/lbliii/kida.git
cd kida
uv sync --group dev --python 3.14t
PYTHON_GIL=0 uv run --python 3.14t pytest
```

---

## The Bengal Ecosystem

Kida is part of a pure-Python stack built for 3.14t free-threading.

| | | | |
|--:|---|---|---|
| **ᓚᘏᗢ** | [Bengal](https://github.com/lbliii/bengal) | Static site generator | [Docs](https://lbliii.github.io/bengal/) |
| **∿∿** | [Purr](https://github.com/lbliii/purr) | Content runtime | — |
| **⌁⌁** | [Chirp](https://github.com/lbliii/chirp) | Web framework | [Docs](https://lbliii.github.io/chirp/) |
| **=^..^=** | [Pounce](https://github.com/lbliii/pounce) | ASGI server | [Docs](https://lbliii.github.io/pounce/) |
| **)彡** | **Kida** | Template engine | [Docs](https://lbliii.github.io/kida/) |
| **ฅᨐฅ** | [Patitas](https://github.com/lbliii/patitas) | Markdown parser | [Docs](https://lbliii.github.io/patitas/) |
| **⌾⌾⌾** | [Rosettes](https://github.com/lbliii/rosettes) | Syntax highlighter | [Docs](https://lbliii.github.io/rosettes/) |
| **ᓃ‿ᓃ** | [Milo](https://github.com/lbliii/milo-cli) | Terminal UI framework | [Docs](https://lbliii.github.io/milo-cli/) |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
