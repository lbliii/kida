---
name: kida-chirp-integration
description: Use Kida with Chirp for HTMX partials, fragment rendering, block validation. Use when building Chirp web apps.
---

# Kida Chirp Integration

Chirp uses Kida's introspection and block APIs for dynamic web apps.

## Workflow

1. **Composition planning** — Use `template_metadata()` to discover blocks and inheritance before rendering
2. **Block validation** — Call `validate_block_exists(env, template_name, block)` before `render_block()` to avoid KeyError
3. **Fragment rendering** — Use `render_block()` for HTMX partial responses and Turbo Stream updates
4. **Layout assembly** — Use `render_with_blocks()` to inject pre-rendered content into layout templates
5. **Adapter pattern** — `KidaAdapter` implements Chirp's `TemplateAdapter` interface

## Key APIs

### render_block

Render a single block for HTMX partials:

```python
template = env.get_template("page.html")
html = template.render_block("content", title="Hello", items=items)
```

Supports inherited blocks: render parent-only blocks (e.g. `sidebar`) from a descendant template.

### validate_block_exists

Check block exists before `render_block()` to avoid KeyError:

```python
from kida.composition import validate_block_exists

if validate_block_exists(env, "page.html", "content"):
    html = env.get_template("page.html").render_block("content", **ctx)
```

### render_with_blocks

Inject pre-rendered HTML into blocks:

```python
layout = env.get_template("_layout.html")
html = layout.render_with_blocks({"content": inner_html}, title="Page Title")
```

### template_metadata

Discover blocks and inheritance:

```python
meta = template.template_metadata()
if meta:
    print(meta.extends)
    print(list(meta.blocks.keys()))
```

### list_blocks

List all blocks including inherited:

```python
blocks = template.list_blocks()
# ['title', 'nav', 'content', 'footer']
```

## Template Composition Patterns

### Composition vs Inheritance

Chirp uses two rendering models depending on context:

| | Inheritance (`extends`) | Composition (`render_with_blocks`) |
|---|---|---|
| How | Child replaces parent blocks | Framework injects pre-rendered HTML into named block slots |
| Used by | Standalone app templates | Filesystem page templates (`mount_pages`) |
| Template syntax | `{% extends "base.html" %}` | No extends — page defines blocks, Chirp wraps with layouts |
| Which blocks render | All blocks in the inheritance chain | Only blocks named in the `render_with_blocks({...})` dict |

Chirp's filesystem page renderer calls `render_with_blocks({"content": page_html})` — only
the `content` block is injected. **Sibling blocks like `page_scripts` that are not in the
dict are silently ignored.** This is the most common gotcha.

### Named Slots in Components (def + call + slot)

chirp-ui macros use `{% def %}` with named slots. The caller provides content
via `{% slot name %}...{% end %}` inside `{% call %}`:

```kida
{% from "chirpui/modal.html" import modal %}

{% call modal(title="Confirm", id="confirm-dialog") %}
    {% slot footer %}
        <button>Cancel</button>
        <button>OK</button>
    {% end %}
    <p>Are you sure?</p>
{% end %}
```

There is NO `{% fill %}` tag in Kida. Always use `{% slot name %}` inside `{% call %}`.

### Inline Scripts in Filesystem Pages

Page templates rendered via `render_with_blocks` cannot override layout blocks that
are siblings of the `content` block (e.g. `page_scripts` in `app_shell_layout.html`).
The layout renders its own `page_scripts` block — the page template's version is never reached.

Place `<script>` tags directly inside `page_content` or `page_root`:

```kida
{% block page_content %}
<div class="my-page">
    <h1>My Page</h1>
    <!-- page content -->
</div>

<script>
document.addEventListener("alpine:init", function() {
    Alpine.data("myComponent", function() {
        return { /* ... */ };
    });
});
</script>
{% end %}
```

### Embedding JSON Data for JavaScript

**Large or complex config:** prefer `<script type="application/json">` plus `JSON.parse` in `alpine:init` (clear separation, no attribute size limits):

```kida
{# GOOD — safe, no quoting issues #}
<script id="my-config" type="application/json">{{ config | tojson }}</script>
<div x-data="myComponent()">...</div>
<script>
document.addEventListener("alpine:init", function() {
    var cfg = JSON.parse(document.getElementById("my-config").textContent);
    Alpine.data("myComponent", function() {
        return { ...cfg };
    });
});
</script>
```

**Inline in a double-quoted attribute:** use Kida’s `attr` flag so JSON quotes are entity-encoded (browser decodes before JS runs):

```kida
<div x-data="myComponent({{ config | tojson(attr=true) }})">...</div>
```

**Inline with a single-quoted attribute:** default `tojson` is fine (no `attr` needed):

```kida
<div x-data='myComponent({{ config | tojson }})'>...</div>
```

**Broken** — raw `tojson` inside a double-quoted attribute (unescaped `"` terminate the attribute):

```kida
{# BAD — do not use default tojson here #}
<div x-data="myComponent({{ config | tojson }})">
```

`tojson` wraps output in `Markup()` (skipped by the HTML escaper), which is correct
for `<script>` tags but produces raw `"` inside **double-quoted** HTML attributes unless you use `attr=true` or single quotes around the attribute value.
