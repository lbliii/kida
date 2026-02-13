# Modern Syntax Features

Pattern matching, pipeline operator, null coalescing, optional chaining. No Jinja2 equivalent.

## Run

```bash
cd examples/modern_syntax && python app.py
```

## Test

```bash
pytest examples/modern_syntax/ -v
```

## What It Shows

- `{% match x %}{% case "a" %}...{% case _ %}...{% end %}` — pattern matching
- `{{ x |> filter }}` — pipeline operator
- `{{ x ?? "default" }}` — null coalescing
- `{{ obj?.attr }}` — optional chaining
