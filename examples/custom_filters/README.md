# Custom Filters and Tests

Extend Kida with domain-specific filters and tests.

## Run

```bash
cd examples/custom_filters && python app.py
```

## Test

```bash
pytest examples/custom_filters/ -v
```

## What It Shows

- `add_filter(name, func)` — register a filter
- `@env.filter()` — decorator for filter registration
- `add_test(name, func)` — register a custom test
- Filters: `money`, `pluralize`
- Test: `is prime` for `{% if n is prime %}`

## Template Usage

```kida
{{ total | money }}
{{ total | money(currency="€") }}
{{ count | pluralize("item", "items") }}
{% if count is prime %}...{% end %}
```
