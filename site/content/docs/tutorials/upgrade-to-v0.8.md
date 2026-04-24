---
title: Upgrade to 0.8
description: Optional chaining now treats missing Mapping keys like dict.get()
draft: false
weight: 14
lang: en
type: doc
tags:
- migration
- upgrade
- tutorial
- optional-chaining
keywords:
- upgrade
- 0.8
- optional chaining
- ?.
- Mapping
- dict.get
icon: arrow-up-circle
---

# Upgrade to 0.8

Guide for moving a codebase from Kida 0.7.x to 0.8.0.

:::note[Why this tutorial exists]
Kida 0.8.0 changes the semantics of `?.` and `?[...]` on Mapping receivers: missing keys now short-circuit to `None` instead of raising `UndefinedError` under `strict_undefined`. This aligns `?.` with the mental model every TS/Swift/JS user imports (and with Python's own `dict.get()` idiom), at the cost of one breaking semantic. Object-attribute strictness is preserved — `?.nickname` on an object without that attribute still raises.
:::

## TL;DR

```kida
{# v0.7.x — raises UndefinedError when key is missing #}
{{ user?.nickname }}    {# user = {} → UndefinedError #}

{# v0.8.0 — returns None, renders as "" (like dict.get("nickname")) #}
{{ user?.nickname }}    {# user = {} → "" #}

{# Object attribute access is unchanged — still strict #}
{{ user?.nickname }}    {# user = User() without .nickname → UndefinedError #}
```

If this breaks code that **relied on** the v0.7 behavior (catching a missing dict key via `?.`), the migration is one of:

1. Drop the `?.` and use strict access: `{{ user.nickname }}` — raises on missing dict key, explicit.
2. Use the `get` filter: `{{ user | get("nickname") }}` — same soft behavior as new `?.`, more explicit.
3. Pin to 0.7: `pip install 'kida-templates==0.7.*'`.

## What changed

### Old rule (v0.7): receiver-only short-circuit

`?.` short-circuited only when the receiver was `None`. A missing key on a defined receiver raised.

| Expression | Receiver | v0.7 behavior |
|---|---|---|
| `user?.nickname` | `None` | `""` (short-circuit) |
| `user?.nickname` | `{}` | `UndefinedError` |
| `user?.nickname` | `User()` (no attr) | `UndefinedError` |
| `items?[5]` | `[1, 2, 3]` | `IndexError` |

### New rule (v0.8): Mapping-soft, object-strict

| Expression | Receiver | v0.8 behavior |
|---|---|---|
| `user?.nickname` | `None` | `""` (unchanged) |
| `user?.nickname` | `{}` | **`""` (new — Mapping miss → `None`)** |
| `user?.nickname` | `User()` (no attr) | `UndefinedError` (unchanged, strict mode) |
| `items?[5]` | `[1, 2, 3]` | `UndefinedError` (unchanged — Sequence out-of-range) |
| `cfg?["theme"]` | `{}` | **`""` (new — Mapping miss)** |
| `cfg?["theme"]` | `MappingProxyType({})` | **`""` (new)** |

The dispatch rule: `isinstance(obj, collections.abc.Mapping)` decides. This covers `dict`, dict subclasses, `MappingProxyType`, `ChainMap`, and any user-defined `Mapping` ABC. `__missing__` on dict subclasses is still honored (the slow path calls `obj[key]`).

## Why this change

The v0.7 "receiver-only" rule was principled but out of step with every other language's optional-chaining mental model. TypeScript's `foo?.bar` returns `undefined` for a missing property — not because it short-circuits the *access*, but because JS treats missing properties as `undefined`. Swift similarly has no "missing key raises" concept. Users reaching for `?.` in Kida expected TS/Swift semantics on dict-shaped data and got strict errors instead.

The v0.8 split respects both intuitions:

- **Dicts are schema-less** (config, JSON, kwargs). Missing keys are expected. `?.` → `None` matches `dict.get()`.
- **Objects have schemas.** A missing `.nickname` on a `User` object is almost always a typo. `strict_undefined` still catches it.

You still get typo protection where it matters (object attributes, list out-of-range), with none of the `?? ""` noise on every dict lookup.

## Migration

### Most code does not break

If you were following the v0.7 "recommended pattern" of combining `?.` with `??` (e.g. `{{ user?.nickname ?? "" }}`), your code works unchanged in 0.8 — it just became less noisy in its intent.

### Code that relied on the raise

Search for bare `?.` on dict access without a `??` fallback:

```bash
rg '\?\.[a-zA-Z_]+(?!\s*\?\?)' templates/
```

For any hit where the receiver is a dict and you *wanted* a loud error on a missing key, change to strict access:

```kida
{# Before (v0.7 — raised, perhaps intentionally) #}
{{ user?.nickname }}

{# v0.8 explicit strict access #}
{{ user.nickname }}
```

### Pinning

If you're not ready to upgrade:

```toml
# pyproject.toml
dependencies = [
    "kida-templates>=0.7,<0.8",
]
```

## Verification

Your existing `?? "fallback"` patterns still work. Your existing object-attr templates still raise on typos. The only surface-level difference you should see is: dict templates that previously threw under strict mode now render empty string.

Run your test suite. If it passes, you're done.
