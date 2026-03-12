# Kida Template Error Handling Proposal

## 1. Executive Summary

Kida's filters and error enhancement currently include several scenarios that produce silent wrong output or confusing errors. This proposal defines improvements to fail fast with actionable messages, following the pattern established by the `format` filter's %-style detection.

## 2. Problem Statement

- **Silent fallbacks** — Filters like `decimal`, `format_number`, `join`, `reverse`, `classes` catch exceptions and return `str(value)` or empty, hiding type errors.
- **Unguarded conversions** — `pluralize` calls `int(value)` without try/except; non-numeric input yields generic `ValueError`.
- **Missing error enhancement** — `ValueError` from date format, int/float in pluralize, and similar cases lack template-specific suggestions.
- **Type coercion gaps** — `replace` filter's `count` param from YAML may arrive as string; no coercion per filter-type-coercion rule.

## 3. Scope

| Area | Change Type | Risk |
|------|-------------|------|
| `pluralize` | Add try/except + clearer error or default | Low |
| `date` | Add error_enhancement for strftime ValueError | Low |
| `replace` | Coerce `count` to int (YAML/config) | Low |
| `reverse` | Raise on non-iterable instead of `str(value)[::-1]` | Medium (behavior change) |
| `join` | Raise on non-iterable instead of `str(value)` | Medium (behavior change) |
| `decimal` / `format_number` | Add optional `strict` mode | Low |
| `error_enhancement` | Add generic ValueError handler for common patterns | Low |

## 4. Proposed Changes (by component)

### 4.1 Filter: `pluralize` (`src/kida/environment/filters/_string.py`)

- Wrap `int(value)` in try/except.
- On `ValueError`: raise `ValueError` with message: `"pluralize expects a number, got {type(value).__name__}: {value!r}. Use | int or ensure numeric value."`
- Add error_enhancement branch for `"pluralize"` in error message.

### 4.2 Filter: `replace` (`src/kida/environment/filters/_string.py`)

- Coerce `count` before calling `str.replace`: `count = int(count) if count != -1 else -1` (handle default).
- If coercion fails, raise with suggestion to use `| int` on the count value.

### 4.3 Filter: `reverse` (`src/kida/environment/filters/_collections.py`)

- Remove `except TypeError: return str(value)[::-1]`.
- Let `TypeError` propagate (or raise with clear message: "reverse expects a sequence").
- Add error_enhancement suggestion: "reverse expects an iterable. Use `list(value) | reverse` if needed."

### 4.4 Filter: `join` (`src/kida/environment/filters/_collections.py`)

- Remove `except TypeError, ValueError: return str(value)`.
- Let `TypeError` propagate.
- Add error_enhancement suggestion: "join expects a sequence. Use `items | join(', ')`."

### 4.5 Filters: `decimal` and `format_number` (`src/kida/environment/filters/_numbers.py`)

- Add `strict: bool = False` parameter.
- When `strict=True` and conversion fails, raise `TemplateRuntimeError` with suggestion (mirror `int`/`float`).
- Default `strict=False` preserves current behavior.

### 4.6 Error Enhancement (`src/kida/template/error_enhancement.py`)

- **ValueError + "pluralize"** — Suggestion: "pluralize expects a number. Use `| int` or ensure numeric value."
- **ValueError + "Invalid format" or "strftime"** — Suggestion: "date filter uses strftime format (e.g. %Y, %m, %d). See strftime directives."
- **ValueError + "invalid literal"** — Generic: "Conversion failed. Use `| int` or `| float` for numeric coercion, or ensure correct type at data source."
- **TypeError + "join" or "reverse"** — Suggestion for sequence-expected filters.

## 5. Backward Compatibility

- `reverse` and `join` behavior change: `42 | reverse` and `42 | join(", ")` will raise instead of returning `"24"` / `"42"`. Document as breaking change; consider deprecation period or `strict` flag if needed.
- All other changes are additive (new params, new suggestions) or tighten behavior in ways that surface bugs rather than hide them.

## 6. Implementation Order

1. **Phase 1 (low risk):** pluralize, replace coercion, date/ValueError enhancement, decimal/format_number strict.
2. **Phase 2 (behavior change):** reverse and join — raise on non-iterable; add tests and update docs.

## 7. Testing

- Add tests for each new error path.
- Add tests for `strict` mode on decimal/format_number.
- Add tests for replace with string count (coerced).
- Regression tests for reverse/join with non-iterable (expect raise).

## 8. Documentation

- Update filter docs for new `strict` params.
- Document breaking change for reverse/join in changelog.
- Add "Common Errors" section referencing new suggestions.
