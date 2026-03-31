# Modern Syntax Features

Pattern matching, pipeline operator, null coalescing, optional chaining, safe pipeline, optional filter, nullish assignment, and promote. No Jinja2 equivalent.

## Run

```bash
cd examples/modern_syntax && python app.py
```

## Test

```bash
pytest examples/modern_syntax/ -v
```

## What It Shows

- `{{ x |> filter }}` — pipeline operator
- `{{ x ?? "default" }}` — null coalescing
- `{{ obj?.attr }}` — optional chaining
- `{{ x ?|> filter1 ?|> filter2 ?? "fallback" }}` — safe pipeline (None-propagating)
- `{{ x ?| upper ?? "N/A" }}` — optional filter (skip on None)
- `{% let x ??= "default" %}` — nullish assignment (set only if undefined/None)
- `{% promote x = value %}` — scope promotion (alias for export)
- `{% promote x ??= value %}` — capture first value in a loop
- `{% match x %}{% case "a" %}...{% case _ %}...{% end %}` — pattern matching
