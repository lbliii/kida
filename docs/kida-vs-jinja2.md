# Kida vs Jinja2

A practical comparison for developers evaluating template engines. Kida is not a drop-in replacement for Jinja2 — it's a different engine with familiar syntax, new capabilities, and different internals.

---

## At a Glance

| | Kida | Jinja2 |
|---|---|---|
| **Python version** | 3.14+ | 3.8+ |
| **Dependencies** | Zero | MarkupSafe |
| **Compilation** | Template → Kida AST → Python AST → `exec()` | Template → Python source string → `exec()` |
| **Free-threading** | Safe under `PYTHON_GIL=0` (PEP 703) | Not tested/supported |
| **Rendering modes** | `render()`, `render_stream()`, `render_block()`, `render_async()`, `render_with_blocks()` | `render()`, `generate()` |
| **Output targets** | HTML, terminal (ANSI), markdown | HTML, text |
| **Compile-time optimization** | Constant folding, dead branch elimination, pure filter eval, component inlining | None |

---

## Syntax Comparison

### What's Identical

```
{{ variable }}                    {# same #}
{{ user.name }}                   {# same #}
{{ items | join(", ") }}          {# same #}
{% extends "base.html" %}         {# same #}
{% block content %}...{% end %}   {# same (with end) #}
{% include "partial.html" %}      {# same #}
{% set x = 42 %}                  {# same #}
{# comments #}                    {# same #}
```

### What Changes

#### Block endings

```jinja2
{# Jinja2 — tag-specific endings #}
{% if user %}...{% endif %}
{% for x in items %}...{% endfor %}
{% block nav %}...{% endblock %}

{# Kida — unified {% end %} (or explicit: {% endif %}, {% endfor %}, {% endblock %}) #}
{% if user %}...{% end %}
{% for x in items %}...{% end %}
{% block nav %}...{% end %}
```

Both `{% end %}` and explicit closers (`{% endif %}`, `{% endfor %}`, etc.) work in Kida. Use `kida check --strict` to enforce explicit closers.

#### Filter syntax

```jinja2
{# Jinja2 — pipe operator only #}
{{ title | escape | upper | truncate(50) }}

{# Kida — pipe works the same, plus pipeline operator #}
{{ title | escape | upper | truncate(50) }}
{{ title |> escape |> upper |> truncate(50) }}
```

`|` and `|>` both work. `|>` reads left-to-right and may be clearer for long chains.

#### Macros → Components

```jinja2
{# Jinja2 — macros #}
{% macro button(label, type="primary") %}
  <button class="btn-{{ type }}">{{ label }}</button>
{% endmacro %}
{{ button("Save") }}

{# Kida — def + call + slots #}
{% def button(label, type="primary") %}
  <button class="btn-{{ type }}">{{ label }}</button>
{% end %}
{{ button("Save") }}

{# Kida — with slots for richer composition #}
{% def card(title) %}
<article>
  <h2>{{ title }}</h2>
  <div class="actions">{% slot actions %}</div>
  <div class="body">{% slot %}</div>
</article>
{% end %}

{% call card("Settings") %}
  {% slot actions %}<button>Save</button>{% end %}
  <p>Main content here.</p>
{% end %}
```

### What Kida Adds

#### Pattern matching

```kida
{% match http_status %}
{% case 200 %}
    <span class="ok">OK</span>
{% case 301 | 302 %}
    <span class="redirect">Redirect</span>
{% case 404 %}
    <span class="error">Not Found</span>
{% case _ %}
    <span class="unknown">{{ http_status }}</span>
{% end %}
```

Jinja2 equivalent requires `{% if %}` / `{% elif %}` chains.

#### Null safety operators

```kida
{# Null coalescing — first non-None value #}
{{ user.nickname ?? user.name ?? "Anonymous" }}

{# Optional chaining — short-circuit on None #}
{{ config?.database?.host }}

{# Safe pipeline — None propagates without error #}
{{ data ?|> parse ?|> validate ?|> render }}

{# Optional filter — skips filter when None #}
{{ value ?| upper ?? "N/A" }}

{# Nullish assignment — assign only if undefined/None #}
{% let title ??= "Untitled" %}
```

Jinja2 equivalent: `{{ value | default("fallback") }}` (only handles undefined, not `None`).

#### Regions — parameterized blocks

```kida
{% region sidebar(style="default", show_search=true) %}
  <nav class="{{ style }}">
    {% if show_search %}<input type="search">{% end %}
    {% for item in nav_items %}
      <a href="{{ item.url }}">{{ item.title }}</a>
    {% end %}
  </nav>
{% end %}

{# Use as block #}
{{ sidebar(style="compact", show_search=false) }}

{# Or render server-side for HTMX OOB #}
html = template.render_block("sidebar", style="compact", show_search=False)
```

No Jinja2 equivalent — regions bridge macros (callable) and blocks (renderable server-side).

#### Block rendering

```python
# Kida — render a single named block
html = template.render_block("content", title="Hello")

# Kida — compose layout from pre-rendered blocks
html = layout.render_with_blocks({"sidebar": sidebar_html}, title="Page")
```

Jinja2 has no built-in block rendering (requires third-party `jinja2-fragments`).

#### Fragment caching

```kida
{% cache "sidebar-" ~ user.id %}
    {% for item in nav_items %}
        <a href="{{ item.url }}">{{ item.title }}</a>
    {% end %}
{% end %}
```

Jinja2 requires the `jinja2.ext.FragmentCacheExtension` (unofficial).

#### Terminal rendering

```python
from kida.terminal import terminal_env

env = terminal_env()
template = env.from_string("""
{{ "Status" | bold | cyan }}
{% for svc in services %}
{{ svc.name | pad(20) }}{{ svc.status | badge }}
{% end %}
""")
```

30+ ANSI-aware filters, box/panel components, `LiveRenderer` for animated output. No Jinja2 equivalent.

---

## API Mapping

| Operation | Jinja2 | Kida |
|-----------|--------|------|
| Create environment | `jinja2.Environment()` | `kida.Environment()` |
| File loader | `jinja2.FileSystemLoader(path)` | `kida.FileSystemLoader(path)` |
| Dict loader | `jinja2.DictLoader(mapping)` | `kida.DictLoader(mapping)` |
| Load template | `env.get_template(name)` | `env.get_template(name)` |
| From string | `env.from_string(source)` | `env.from_string(source)` |
| Render | `template.render(**ctx)` | `template.render(**ctx)` |
| Stream | `template.generate(**ctx)` | `template.render_stream(**ctx)` |
| Add filter | `env.filters["name"] = fn` | `env.add_filter("name", fn)` |
| Add test | `env.tests["name"] = fn` | `env.add_test("name", fn)` |
| Add global | `env.globals["name"] = val` | `env.add_global("name", val)` |
| Sandbox | `jinja2.SandboxedEnvironment()` | `kida.SandboxedEnvironment()` |
| Async render | — | `template.render_async(**ctx)` |
| Block render | — | `template.render_block(name, **ctx)` |
| Compose blocks | — | `template.render_with_blocks(overrides, **ctx)` |
| Metadata | — | `template.template_metadata()` |
| Terminal mode | — | `terminal_env()` |

---

## Performance

Benchmarks on Python 3.14.2t (Apple M-series, single thread):

| Template | Kida | Jinja2 | Ratio |
|----------|------|--------|-------|
| Minimal (1 var) | ~4µs | ~4µs | 1x |
| Small (loop + filter) | ~7µs | ~7µs | 1x |
| Medium (~100 vars) | ~0.2ms | ~0.26ms | 1.3x faster |
| Large (1000 items) | ~1.6ms | ~4ms | **2.5x faster** |
| Complex (3-level inheritance) | ~19µs | ~29µs | **1.5x faster** |

With `static_context` (compile-time constant folding):

| Template | Dynamic | Static | Speedup |
|----------|---------|--------|---------|
| Filter chains | 6.3µs | 3.8µs | **1.67x** |
| Dashboard (8 metrics) | 120µs | 102µs | **1.18x** |
| Status bar | 35µs | 23µs | **1.54x** |

Under free-threading (`PYTHON_GIL=0`), kida scales linearly with cores. Jinja2 does not support free-threading.

---

## Migration Checklist

1. **Install**: `pip install kida-templates`

2. **Update imports**:
   ```python
   # Before
   from jinja2 import Environment, FileSystemLoader
   # After
   from kida import Environment, FileSystemLoader
   ```

3. **Update block endings** (optional — explicit closers still work):
   ```kida
   {% endif %} → {% end %}  (or keep {% endif %})
   {% endfor %} → {% end %} (or keep {% endfor %})
   ```

4. **Update macro syntax**:
   ```kida
   {% macro name() %} → {% def name() %}
   {% endmacro %}     → {% end %}
   ```

5. **Update filter registration**:
   ```python
   # Before
   env.filters["name"] = fn
   # After
   env.add_filter("name", fn)
   ```

6. **Test**: Run your templates and compare output. Most Jinja2 templates work with minimal changes.

---

## Honest Differences

Things Jinja2 does that Kida doesn't:

- **Wider Python support** — Jinja2 works on 3.8+. Kida requires 3.14+.
- **Larger ecosystem** — More third-party extensions, loaders, and integrations.
- **Drop-in compatibility** — Kida is close but not identical. Block endings, macro syntax, and scoping rules differ.
- **Battle-tested at scale** — Jinja2 powers Flask, Ansible, Salt, and thousands of production systems. Kida is newer.

Things Kida does that Jinja2 doesn't:

- **Free-threading** — True parallel rendering under `PYTHON_GIL=0`.
- **AST-native compilation** — Compile-time optimization, structured code analysis.
- **Block rendering** — `render_block()` for HTMX fragments without third-party extensions.
- **Terminal rendering** — First-class ANSI output with filters, components, live rendering.
- **Null safety** — `??`, `?.`, `?|>`, `?|`, `??=` operators.
- **Pattern matching** — `{% match %}` / `{% case %}`.
- **Regions** — Parameterized blocks that work as both callables and renderable fragments.
- **Zero dependencies** — No MarkupSafe, no C extensions.

---

## Further Reading

- [Full migration tutorial](https://lbliii.github.io/kida/docs/tutorials/migrate-from-jinja2/)
- [Template syntax reference](https://lbliii.github.io/kida/docs/syntax/)
- [Benchmark results](https://lbliii.github.io/kida/docs/about/performance/)
- [API documentation](https://lbliii.github.io/kida/docs/reference/)
