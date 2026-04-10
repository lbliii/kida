# List Comprehensions — Inline Data Transformation

Transform iterables directly in templates using Python-style list comprehensions.

## Run

```bash
cd examples/list_comprehensions && python app.py
```

## Test

```bash
pytest examples/list_comprehensions/ -v
```

## What It Shows

- `[x * 2 for x in numbers]` — basic transformation
- `[n | title for n in names]` — with filters
- `[item.name for item in products if item.in_stock]` — with condition
- `[{"value": s, "label": s | capitalize} for s in styles]` — shaping data for components
- `[k for k, v in pairs if v > 10]` — tuple unpacking
