# )彡 Kida

[![PyPI version](https://img.shields.io/pypi/v/kida-templates.svg)](https://pypi.org/project/kida-templates/)
[![Build Status](https://github.com/lbliii/kida/actions/workflows/tests.yml/badge.svg)](https://github.com/lbliii/kida/actions/workflows/tests.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/kida-templates/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**A Python component framework for HTML — typed props, named slots, scoped state, error boundaries, and zero JavaScript.**

Kida compiles templates to Python AST, renders to HTML/terminal/markdown, and scales across cores on free-threaded Python 3.14t. Zero runtime dependencies.

## Quick Start

```bash
pip install kida-templates
```

```kida
{% def card(title: str, variant: str = "default") %}
<article class="card card--{{ variant }}">
  <h3>{{ title }}</h3>
  <div class="actions">{% slot header_actions %}</div>
  <div class="body">{% slot %}</div>
</article>
{% end %}

{% call card("Settings", variant="elevated") %}
  {% slot header_actions %}<button>Save</button>{% end %}
  <p>Configure your preferences.</p>
{% end %}
```

```python
from kida import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("page.html")
html = template.render(title="Hello")
```

---

## Component Model

Kida gives you the composition patterns of modern frontend frameworks, without a build step.

| Feature | Syntax |
|---------|--------|
| Typed props | `{% def card(title: str, count: int = 0) %}` |
| Named slots | `{% slot header %}` / `{% slot %}` (default) |
| Conditional slots | `has_slot("footer")` |
| Scoped slots (data up) | `{% slot row let:item=item %}` |
| Slot forwarding | `{% yield name %}` |
| Context propagation | `{% provide theme = "dark" %}` / `consume("theme")` |
| Error boundaries | `{% try %}...{% fallback error %}...{% end %}` |
| Co-located styles | `{% push "styles" %}` / `{% stack "styles" %}` |
| Pattern matching | `{% match status %}{% case "active" %}...{% end %}` |
| Block-scoped variables | `{% set %}` (scoped) / `{% let %}` (template-wide) / `{% export %}` |

### Static Validation

```bash
kida check templates/ --validate-calls
```

```
card.html:14: type: badge() param 'count' expects int, got str ("five")
dashboard.html:8: Call to 'card' — unknown params: titl
```

Catches unknown params, missing required params, and literal type mismatches at check time.

### Component Discovery

```bash
kida components templates/

# components/card.html
#   def card(title: str, subtitle: str | None = None)
#     slots: header_actions, footer
#
# components/button.html
#   def button(label: str, variant: str = "primary")
#     slots: (none)
#
# 2 component(s) found.
```

### Introspection API

```python
template = env.get_template("components/card.html")
meta = template.def_metadata()
card = meta["card"]
print(card.params)           # (DefParamInfo(name='title', annotation='str', ...), ...)
print(card.slots)            # ('header_actions', 'footer')
print(card.has_default_slot) # True
```

---

## Why Not Jinja2?

| | Jinja2 | Kida |
|---|---|---|
| **Typed parameters** | No | `param: str \| None` |
| **Named slots** | No (`caller()` only) | `{% slot name %}` |
| **Scoped variables** | `set` leaks out of blocks | `set` is block-scoped |
| **Context propagation** | Prop drilling | `provide` / `consume` |
| **Error boundaries** | No | `{% try %}...{% fallback %}` |
| **Component styles** | Disconnected CSS files | `{% push "styles" %}` |
| **Call-site validation** | Runtime errors | Compile-time checks |
| **Component discovery** | Read every file | `kida components` CLI |
| **Block rendering** | No | `render_block()` for HTMX partials |
| **Streaming** | Limited | `render_stream()` for chunked HTTP/SSE |
| **Free-threading** | No | GIL-free on Python 3.14t |

---

## Render Surfaces

One template syntax, four outputs.

<details>
<summary><strong>HTML</strong></summary>

```python
from kida import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))
html = env.get_template("page.html").render(title="Hello")
```

</details>

<details>
<summary><strong>Terminal</strong></summary>

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

</details>

<details>
<summary><strong>Markdown</strong></summary>

```python
from kida.markdown import markdown_env

env = markdown_env()
md = env.from_string("# {{ title }}\n\n{{ body }}").render(
    title="Report", body="All tests passed."
)
```

</details>

<details>
<summary><strong>CI Reports (GitHub Action)</strong></summary>

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

</details>

---

## More Features

<details>
<summary><strong>Template Inheritance</strong></summary>

```kida
{# base.html #}
<!DOCTYPE html>
<html>
<body>{% block content %}{% end %}</body>
</html>

{# page.html #}
{% extends "base.html" %}
{% block content %}<h1>{{ title }}</h1>{% end %}
```

</details>

<details>
<summary><strong>Regions (Parameterized Blocks)</strong></summary>

```kida
{% region sidebar(current_path="/") %}
  <nav>{{ current_path }}</nav>
{% end %}

{{ sidebar(current_path="/about") }}
```

Regions are blocks (for `render_block()`) and callables (for inline use). Ideal for HTMX OOB swaps.

</details>

<details>
<summary><strong>Pattern Matching & Null Safety</strong></summary>

```kida
{% match status %}
{% case "active" %}Active{% case "pending" %}Pending{% case _ %}Unknown
{% end %}

{{ user.nickname ?? user.name ?? "Anonymous" }}
{{ config?.database?.host }}
{{ data ?|> parse ?|> validate ?|> render }}
```

</details>

<details>
<summary><strong>Streaming & Block Rendering</strong></summary>

```python
# Stream chunks as they render
for chunk in template.render_stream(items=large_list):
    response.write(chunk)

# Render a single block (HTMX partials)
html = template.render_block("content", title="Hello")

# Compose layouts with pre-rendered blocks
html = layout.render_with_blocks({"content": inner_html}, title="Page")
```

</details>

<details>
<summary><strong>Compile-Time Optimization</strong></summary>

```python
template = env.from_string(source, static_context={
    "site": site_config, "settings": app_settings,
})
html = template.render(page_title="Home", items=page_items)
```

67 pure filters evaluated at compile time. Dead branches removed. Component inlining for small defs with constant args. Use `kida render template.html --explain` to see active optimizations.

</details>

<details>
<summary><strong>Free-Threading</strong></summary>

All public APIs are safe under `PYTHON_GIL=0` (Python 3.14t, PEP 703). Templates compile to immutable AST, rendering uses thread-local accumulators, and the Environment uses copy-on-write. Scales linearly with cores.

</details>

<details>
<summary><strong>Framework Integration</strong></summary>

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
kida render template.txt --data context.json
kida check templates/ --validate-calls --a11y --typed
kida components templates/ --json
kida fmt templates/
kida extract templates/ -o messages.pot
```

</details>

---

## Upgrading

Moving from 0.6.x? See the [Upgrade to 0.7 tutorial](https://lbliii.github.io/kida/docs/tutorials/upgrade-to-v0.7/) for the `strict_undefined=True` migration patterns and the new null-safe idioms (`?.`, `?[`, `| get`).

## The Bengal Ecosystem

Kida is part of a pure-Python stack built for 3.14t free-threading.

| | | | |
|--:|---|---|---|
| **ᓚᘏᗢ** | [Bengal](https://github.com/lbliii/bengal) | Static site generator | [Docs](https://lbliii.github.io/bengal/) |
| **∿∿** | [Purr](https://github.com/lbliii/purr) | Content runtime | — |
| **⌁⌁** | [Chirp](https://github.com/lbliii/chirp) | Web framework | [Docs](https://lbliii.github.io/chirp/) |
| **=^..^=** | [Pounce](https://github.com/lbliii/pounce) | ASGI server | [Docs](https://lbliii.github.io/pounce/) |
| **)彡** | **Kida** | Component framework | [Docs](https://lbliii.github.io/kida/) |
| **ฅᨐฅ** | [Patitas](https://github.com/lbliii/patitas) | Markdown parser | [Docs](https://lbliii.github.io/patitas/) |
| **⌾⌾⌾** | [Rosettes](https://github.com/lbliii/rosettes) | Syntax highlighter | [Docs](https://lbliii.github.io/rosettes/) |
| **ᓃ‿ᓃ** | [Milo](https://github.com/lbliii/milo-cli) | Terminal UI framework | [Docs](https://lbliii.github.io/milo-cli/) |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
