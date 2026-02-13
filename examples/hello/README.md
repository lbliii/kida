# Hello — The Basics

Compile a template from a string, render with context. Kida in ~10 lines.

## Run

```bash
cd examples/hello && python app.py
```

## Test

```bash
pytest examples/hello/ -v
```

## What It Shows

- `Environment()` — create environment
- `env.from_string()` — compile from string
- `template.render(**ctx)` — render with context
