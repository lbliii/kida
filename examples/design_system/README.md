# Design System — Component Library

`{% def %}`, `{% slot %}`, and `{% call %}` composed into a design system.

This example demonstrates composition mechanics. Apply the
[App-Owned Component Authoring Contract](https://lbliii.github.io/kida/docs/usage/components/#app-owned-authoring-contract)
before promoting application-local markup into a shared component boundary.

## Run

```bash
cd examples/design_system && python app.py
```

## Test

```bash
pytest examples/design_system/ -v
```

## What It Shows

- Reusable cards, buttons, alerts
- Components accept parameters with defaults
- Content projection through slots
- Nested composition: buttons inside cards, cards inside pages
