# Provide / Consume

Implicit state passing across component boundaries using `{% provide %}` and `consume()`.

## Run

```bash
cd examples/provide_consume && python app.py
```

## Test

```bash
pytest examples/provide_consume/ -v
```

## What It Shows

- `{% provide key = expr %}...{% endprovide %}` -- push state for descendants
- `consume("key")` -- read the nearest provided value
- `consume("key", default)` -- fallback when no provider exists
- Nested providers shadow outer ones and restore on exit
- Works across slot boundaries, imported macros, and includes
