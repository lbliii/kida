# Design System — Component Library

`{% def %}`, `{% slot %}`, and `{% call %}` composed into a design system.

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
