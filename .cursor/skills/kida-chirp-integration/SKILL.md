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
