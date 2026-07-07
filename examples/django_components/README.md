# Django Components

Add typed Kida components to an existing Django app on Python 3.14+:

```bash
uv add django kida-templates
uv run python app.py
```

Open <http://127.0.0.1:8000>. The `TEMPLATES` setting registers Kida as a
normal Django backend; the GET route uses `django.shortcuts.render`, and the
POST route renders only the `preview` block.

Run the non-network smoke path with:

```bash
uv run python app.py --smoke
```
