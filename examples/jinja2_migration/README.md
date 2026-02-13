# Jinja2 Migration Guide

Side-by-side comparison of equivalent Kida and Jinja2 templates.

## Run

```bash
cd examples/jinja2_migration && python app.py
```

## Test

```bash
pytest examples/jinja2_migration/ -v
```

## What It Shows

| Kida | Jinja2 |
|------|--------|
| `{% end %}` | `{% endif %}`, `{% endfor %}`, etc. |
| `{% match x %}{% case "a" %}...{% case _ %}...{% end %}` | `{% if x == "a" %}...{% else %}...{% endif %}` |
| `{{ x ?? "default" }}` | `{{ x \| default("default") }}` |
| `{{ user?.name }}` | `{% if user and user.name %}...{% endif %}` |

Both engines render equivalent output for the same context.
