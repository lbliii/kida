# Template Introspection

Static analysis API for pre-render validation and dependency tracking.

## Run

```bash
cd examples/introspection && python app.py
```

## Test

```bash
pytest examples/introspection/ -v
```

## What It Shows

- `required_context()` — list variables a template needs
- `block_metadata()` — per-block dependencies
- `validate_context()` — catch missing variables before render
- `depends_on()` — all dotted dependency paths
- `template_metadata()` — extends, blocks, includes
