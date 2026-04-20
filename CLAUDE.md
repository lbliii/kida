# Kida — Development Guide

## What is Kida?

Kida is a Python template engine that compiles to AST, renders to HTML/terminal/markdown, and scales across cores on free-threaded Python 3.14t. Zero runtime dependencies.

## Build & Test

```bash
uv sync --group dev     # Install deps
uv run pytest            # Run tests
uv run ruff check .      # Lint
uv run ruff format .     # Format
uv run ty check src/     # Type check (Astral ty, Rust-based)
```

## Project Structure

```
src/kida/
  __init__.py           # Public API: Environment, FileSystemLoader, Markup, etc.
  lexer.py              # Tokenizer
  parser/               # Parser (core + statement/expression mixins)
  compiler/             # AST compiler (core + statement mixins)
  nodes/                # AST node definitions
  template/             # Template class, render_block, render_with_blocks
  environment/          # Environment, loaders, filter/test registries
    filters/            # Built-in filters (tojson, default, escape, etc.)
  render_context.py     # Render-time context + scoping
  render_accumulator.py # Output accumulation
  composition.py        # validate_block_exists, render_with_blocks helpers
  analysis/             # Static analysis (dependencies, purity, a11y, coverage)
  sandbox.py            # Sandboxed execution
  formatter.py          # Template source formatter
  cli.py                # CLI: kida check, kida format
  markdown/             # Markdown render surface
  terminal/             # Terminal render surface (ANSI colors)
  tstring.py            # T-string / k(t"...") inline templates
  utils/                # Markup (safe strings), constants, HTML utilities
tests/
site/content/docs/      # Documentation (Bengal-powered)
```

## Syntax Quick Reference

### Block Endings

Kida uses unified `{% end %}` to close all blocks:

```kida
{% if x %}...{% end %}
{% for y in items %}...{% end %}
{% block content %}...{% end %}
{% def card(title) %}...{% end %}
{% call card("hi") %}...{% end %}
```

Explicit closers (`{% endif %}`, `{% endfor %}`, `{% endblock %}`) are accepted for
readability in deeply nested templates, but `{% end %}` is the canonical style.

### Variable Scoping

| Keyword | Scope | Jinja2 equivalent |
|---------|-------|-------------------|
| `{% let x = ... %}` | Template-wide — visible everywhere after assignment | `{% set %}` at top level |
| `{% set x = ... %}` | Block-scoped — does NOT leak out of `{% if %}`, `{% for %}`, etc. | No equivalent (Jinja2 `set` leaks) |
| `{% export x = ... %}` | Promotes to template (outermost) scope from any nesting depth | `namespace()` pattern |

This is the #1 Jinja2 migration trap: `{% set %}` inside a block does NOT modify outer variables in Kida.

### Inheritance (extends + block)

```kida
{% extends "base.html" %}
{% block title %}My Page{% end %}
{% block content %}<p>Hello</p>{% end %}
```

- No `super()` — child blocks fully replace parent content
- Use empty extension blocks (`{% block extra_head %}{% end %}`) for add-to patterns
- Blocks cannot be defined inside loops — use `{% def %}` instead

### Composition (def + call + slot)

This is how chirp-ui components work. A `{% def %}` defines a component with named slots:

```kida
{# Define a component with named slots #}
{% def card(title) %}
<div class="card">
  <h3>{{ title }}</h3>
  <div class="actions">{% slot header_actions %}</div>
  <div class="body">{% slot %}</div>
</div>
{% end %}

{# Use it with {% call %} and provide slot content #}
{% call card("Settings") %}
  {% slot header_actions %}<button>Save</button>{% end %}
  <p>Body content goes here (default slot).</p>
{% end %}
```

Key rules:
- `{% slot %}` in a def = default slot placeholder (rendered via `caller()`)
- `{% slot name %}` in a def = named slot placeholder (rendered via `caller("name")`)
- `{% slot name %}...{% end %}` inside `{% call %}` = provides content for a named slot
- Bare content inside `{% call %}` = provides content for the default slot
- There is NO `{% fill %}` tag — use `{% slot %}` inside `{% call %}` blocks

### Regions (parameterized blocks)

Regions compile to both a block (for `render_block()`) and a callable:

```kida
{% region sidebar(current_path="/") %}
  <nav>{{ current_path }}</nav>
{% end %}

{# Use as callable: #}
{{ sidebar(current_path="/about") }}
```

```python
# Use as block from Python:
html = template.render_block("sidebar", current_path="/settings")
```

Use regions for HTMX OOB updates and framework composition. Use defs for component slots.

### Filters

```kida
{{ title | upper }}                          {# Standard pipe #}
{{ title |> escape |> upper |> truncate(50) }} {# Pipeline operator (left-to-right) #}
{{ value ?| upper ?? "N/A" }}                {# Null-safe filter #}
{{ data | tojson }}                           {# JSON serialization #}
{{ data | tojson(indent=2) }}                {# Pretty-printed #}
{{ data | tojson(attr=true) }}               {# Safe in double-quoted HTML attributes #}
```

### tojson Filter

`tojson` outputs `Markup(json.dumps(...))` — marked safe so the autoescaper
does not HTML-encode the quotes. This is correct inside `<script>` tags:

```kida
<script id="config" type="application/json">{{ data | tojson }}</script>
```

In **double-quoted HTML attributes**, raw JSON quotes break the attribute. Use
`attr=true` so the output is entity-encoded (`&quot;`, etc.); the browser decodes
before JS reads the value:

```kida
<div x-data="{{ config | tojson(attr=true) }}">
```

Or use a single-quoted attribute with default `tojson`, or a JSON `<script>` tag:

```kida
<div x-data='{{ config | tojson }}'>
<script id="my-config" type="application/json">{{ config | tojson }}</script>
<div x-data="myComponent()">
```

### Other Notable Features

- `{% match status %}{% case "active" %}...{% case _ %}...{% end %}` — pattern matching
- `{% cache "key" %}...{% end %}` — block-level caching
- `{% let title ??= "Untitled" %}` — nullish assignment (only if undefined/None)
- `{% provide theme = "dark" %}...{% endprovide %}` + `{{ consume("theme") }}` — context propagation
- `{% try %}...{% fallback error %}...{% end %}` — error boundaries
- `{% push "head" %}<link ...>{% end %}` + `{% stack "head" %}` — content stacks
- `{% yield name %}` — slot forwarding in nested macro composition

## Jinja2 Migration Traps

| Jinja2 | Kida | Notes |
|--------|------|-------|
| `{% endif %}` | `{% end %}` | Unified block ending |
| `{% endfor %}` | `{% end %}` | Unified block ending |
| `{% endblock %}` | `{% end %}` | Unified block ending |
| `{% macro %}` | `{% def %}` | `{% macro %}` is NOT a valid keyword in Kida — rename to `{% def %}` |
| `{{ super() }}` | N/A | No super() — use extension blocks |
| `{% set x = ... %}` | `{% let x = ... %}` | Kida `set` is block-scoped, not template-wide |
| `namespace(count=0)` | `{% let count = 0 %}` + `{% export %}` | No namespace() in Kida |
| `env.filters["name"] = fn` | `env.add_filter("name", fn)` | Dict assignment not supported |
| `{% fill name %}` | Does not exist | Use `{% slot name %}` inside `{% call %}` |

## Composition vs Inheritance

Kida supports two models:

| | Inheritance (`extends`) | Composition (`render_with_blocks`) |
|---|---|---|
| How | Child template replaces parent blocks | Framework injects pre-rendered HTML into block slots |
| Used by | Standalone templates, Bengal SSG | Chirp filesystem pages |
| Template syntax | `{% extends "base.html" %}` | No extends — page defines blocks, framework wraps |
| Block override | Child overrides parent blocks | Only blocks named in `render_with_blocks({...})` are filled |

When Chirp uses `render_with_blocks`, only the blocks explicitly passed (typically `content`) are injected. Sibling blocks like `page_scripts` that are not in the dict are silently ignored.

## Key APIs

```python
from kida import Environment, FileSystemLoader, Markup

env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("page.html")

html = template.render(title="Hello")                     # Full render
html = template.render_block("content", title="Hello")    # Single block
html = template.render_with_blocks({"content": inner}, title="Hello")  # Composition
meta = template.template_metadata()                       # AST introspection
blocks = template.block_metadata()                        # Block name → metadata
```

## Dependencies

- **Runtime**: None (pure Python, zero dependencies)
- **Optional**: `markupsafe` (perf — faster escaping), `bengal` (docs site)
- **Dev**: pytest, ruff, ty, hypothesis, pre-commit
- **Python**: 3.14+ required (free-threading ready)
