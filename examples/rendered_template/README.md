# RenderedTemplate — Lazy Streaming Wrapper

`RenderedTemplate(template, context)` wraps a template + context pair for lazy rendering.

## Run

```bash
cd examples/rendered_template && python app.py
```

## Test

```bash
pytest examples/rendered_template/ -v
```

## What It Shows

- `str(rt)` — full render (calls `template.render()`)
- `for chunk in rt` — iterate over `render_stream()` chunks
- Use case: pass to `StreamingResponse` without pre-consuming

## Usage

```python
from kida import Environment, RenderedTemplate

template = env.from_string("...")
rt = RenderedTemplate(template, {"items": ["a", "b", "c"]})

# Full output
html = str(rt)

# Stream chunks
for chunk in rt:
    send_to_client(chunk)
```
