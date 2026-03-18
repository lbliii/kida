# Regions — Parameterized Blocks

`{% region %}` blocks are parameterized fragments that work as both blocks (for
`render_block()`) and callables (for `{{ name(args) }}`). Use them for HTMX
partials, OOB updates, or layout composition.

## Run

```bash
cd examples/regions && python app.py
```

## Test

```bash
pytest examples/regions/ -v
```

## What It Shows

- **Regions as blocks** — `template.render_block("sidebar", section="API")`
- **Regions as callables** — `{{ sidebar(section="API") }}` in templates
- **Simple defaults** — `current_page=page` (variable name)
- **Complex defaults** — `meta=page.metadata`, `count=items | length` (expressions)
- **Outer context** — Region bodies read from caller's context
- **Metadata** — `template_metadata().regions()` and `depends_on` for static analysis
