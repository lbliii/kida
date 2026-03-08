---
name: kida-expression-semantics
description: Understand Kida expression behavior: `+` operator, list vs string, export accumulation. Use when debugging unexpected output or expression behavior.
---

# Kida Expression Semantics

## The `+` Operator

Kida's `add_polymorphic` handles `+` with these rules:

1. **Numeric**: `int + int`, `float + float` → numeric addition
2. **String-like**: If either operand is `str` → `str(left) + str(right)`
3. **Otherwise**: Python native `left + right` — `list + list`, `tuple + tuple`, etc.

## Export Accumulation Pattern

Common pattern for building lists in loops:

```kida
{% for el in all_members %}
{% let m = el | member_view %}
{% if m.is_private %}
{% export internal_members = internal_members + [m] %}
{% else %}
{% export public_members = public_members + [m] %}
{% end %}
{% end %}
```

`members + [m]` must stay **list concatenation**. If `+` incorrectly stringifies:
- `[a, b] + [c]` becomes `"[a, b]c"` (string)
- Iterating over that string yields one output per character
- Result: thousands of empty or garbage entries instead of a few list items

## Why This Matters

A regression that treated `list + list` as string concat caused API docs to explode from 33k to 140k lines — one `<code>` per character instead of per list item.

## Correct Behavior (Current)

- `[a, b] + [c]` → `[a, b, c]` (list)
- `count + " items"` → `"5 items"` (string)
- `"Hello " + name` → `"Hello Alice"` (string)
- `(1, 2) + (3,)` → `(1, 2, 3)` (tuple)

## When to Use `~`

For explicit string concatenation (URLs, paths, IDs), use `~` — always coerces both sides to strings:

```kida
{{ "/path/" ~ id ~ "/action" }}
hx-post="{{ '/chains/' ~ chain_id ~ '/add-step' }}"
```

## Debugging Unexpected Output

If a loop produces far more items than expected, or empty repeated blocks:

1. Check for `{% export x = x + [item] %}` or similar accumulation
2. Verify both operands are lists, not strings
3. Ensure no filter or expression is stringifying the list before `+`
