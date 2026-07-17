# Reusable Components

Kida's `{% def %}` / `{% call %}` / `{% slot %}` pattern for building reusable UI components.

Boundary and ownership guidance lives in the
[App-Owned Component Authoring Contract](https://lbliii.github.io/kida/docs/usage/components/#app-owned-authoring-contract).

## Run

```bash
cd examples/components && python app.py
```

## Test

```bash
pytest examples/components/ -v
```

## What It Shows

- `{% def name(params) %}` — define a component
- `{% call name(args) %}` — invoke with content
- `{% slot %}` — content projection (default slot)
- `{% slot name %}` inside `{% call %}` — named slot content blocks
