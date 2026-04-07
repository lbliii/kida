# )彡 Kida

[![PyPI version](https://img.shields.io/pypi/v/kida-templates.svg)](https://pypi.org/project/kida-templates/)
[![Build Status](https://github.com/lbliii/kida/actions/workflows/tests.yml/badge.svg)](https://github.com/lbliii/kida/actions/workflows/tests.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/kida-templates/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**A template engine that compiles to Python AST, renders to HTML/terminal/markdown, and scales across cores on free-threaded Python.**

## Installation

```bash
pip install kida-templates
```

Requires Python 3.14+. Zero runtime dependencies.

---

## Render Anywhere

One template syntax, four surfaces.

### HTML

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

### Markdown

```python
from kida.markdown import markdown_env

env = markdown_env()
template = env.from_string("# {{ title }}\n\n{{ body }}")
md = template.render(title="Report", body="All tests passed.")
```

### CI Reports (GitHub Action)

Turn pytest, coverage, ruff, and other tool output into step summaries and PR comments.

```yaml
- uses: lbliii/kida@v0.3.3
  with:
    template: pytest
    data: results.xml
    data-format: junit-xml
    post-to: step-summary,pr-comment
```

Built-in templates for pytest, coverage, ruff, ty, jest, gotest, and sarif. [Full action docs &rarr;](https://lbliii.github.io/kida/docs/usage/github-action/)

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

<details>
<summary><strong>CLI</strong></summary>

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

</details>

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
