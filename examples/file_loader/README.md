# File-Based Templates

Load templates from disk with `FileSystemLoader`. Use inheritance and includes.

## Run

```bash
cd examples/file_loader && python app.py
```

## Test

```bash
pytest examples/file_loader/ -v
```

## What It Shows

- `FileSystemLoader` — load from `templates/` directory
- `{% extends %}` and `{% block %}` — template inheritance
- `{% include %}` — include partials
