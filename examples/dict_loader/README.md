# DictLoader — In-Memory Templates

Templates from a dictionary. No filesystem required.

## Use Cases

- Tests (inline template definitions)
- Generated templates
- Single-file applications
- Embedded apps with no template directory

## Run

```bash
cd examples/dict_loader && python app.py
```

## Test

```bash
pytest examples/dict_loader/ -v
```

## What It Shows

- `DictLoader(templates)` — load templates from a dict
- `{% extends %}` and `{% block %}` work with in-memory templates
- No `FileSystemLoader` or template files needed
