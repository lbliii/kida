# HTMX-Style Partial Rendering

`render_block()` extracts and renders a single block — the pattern for htmx, Turbo, Unpoly.

## Run

```bash
cd examples/htmx_partials && python app.py
```

## Test

```bash
pytest examples/htmx_partials/ -v
```

## What It Shows

- `template.render_block("block_name", **ctx)` — render one block
- Full page vs partial for AJAX swap responses
- Same context shared across full and partial renders
