---
title: Upgrade to 0.7
description: Migrate to strict-by-default variable access and the new null-safe idioms
draft: false
weight: 15
lang: en
type: doc
tags:
- migration
- upgrade
- tutorial
- strict-undefined
keywords:
- upgrade
- 0.7
- strict_undefined
- migration
- null-safe
icon: arrow-up-circle
---

# Upgrade to 0.7

Guide for moving a codebase from Kida 0.6.x to 0.7.x.

:::note[Why this tutorial exists]
Kida 0.7.0 flipped `strict_undefined` to `True` by default and added a parse-time check (K-TPL-004) that rejects templates which rely on the old silent-empty-string behavior. This is a breaking change in a 0.x series — this tutorial collects the migration patterns in one place so downstream libraries do not each have to rediscover them.
:::

## TL;DR

- `Environment(strict_undefined=True)` is now the default. Missing variables, attributes, and keys raise `UndefinedError`.
- Fix each site with one of: `is defined`, `??` (null-coalescing), `| default(...)`, `?.` (optional chaining), or `| get("key", default)`.
- Need to unblock first, fix later? Pass `strict_undefined=False` on the `Environment` as a transitional shim.

## Prerequisites

- Python 3.14+
- Kida 0.6.x codebase with templates that run today

## What changed

### `strict_undefined=True` is now the default

In 0.6.x, `Environment(strict_undefined=...)` defaulted to `False`. Missing attributes rendered as `""` silently — which contradicted the documented "strict-by-default" stance.

In 0.7.x, the default is `True`:

```python
from kida import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))
# strict_undefined=True — missing vars/attrs/keys raise UndefinedError
```

`UndefinedError` now carries a kind (`variable`, `attribute`, or `key`) so error messages point at the right layer.

### Parse-time check K-TPL-004

Templates that previously relied on global variables being silently-present-but-missing now fail at parse time with a targeted hint. See the error-code reference for details.

## The three fix patterns

All three patterns work under `strict_undefined=True`. Pick the one that reads best at each site.

### Pattern 1 — `is defined`

```kida
{# Before (relied on silent empty string) #}
{% if user.nickname %}Hello, {{ user.nickname }}!{% end %}

{# After #}
{% if user.nickname is defined and user.nickname %}
    Hello, {{ user.nickname }}!
{% end %}
```

`is defined` works on attribute chains, not just top-level variables — if any part of the chain is missing, the result is treated as undefined.

### Pattern 2 — `??` (null-coalescing)

```kida
{# Before #}
<meta name="description" content="{{ page.description }}">

{# After #}
<meta name="description" content="{{ page.description ?? '' }}">
```

The `??` operator is short-circuit: it evaluates the right side only when the left is undefined or `None`.

### Pattern 3 — `| default(...)`

```kida
{# Before #}
<title>{{ page.title }}</title>

{# After #}
<title>{{ page.title | default("Untitled") }}</title>
```

Use `| default` when you want a named fallback value that reads as documentation at the call site.

## Escape hatch

If you need to unblock an upgrade now and fix sites over time:

```python
env = Environment(
    loader=FileSystemLoader("templates/"),
    strict_undefined=False,
)
```

Lenient mode is a transitional shim. Missing attributes return an `_Undefined` sentinel that stringifies to `""`, is falsy, and is iterable as empty. This is the 0.6.x behavior.

:::tip[Recommended path]
Flip `strict_undefined=False` once to unblock the release, then fix sites one at a time and flip it back (or just delete the kwarg). Keeping the escape hatch long-term defeats the point of the upgrade.
:::

## Preferred idioms going forward

0.7.x ships with first-class null-safe operators. Prefer these over `.get("key", "")` chains:

### `?.` — optional attribute access (receiver-only)

`?.` short-circuits when the **receiver** is `None` or undefined. It does **not** suppress `UndefinedError` for a missing attribute/key on a *defined* receiver — strict mode still raises, by design.

```kida
{# Receiver is None — yields "" #}
{{ config?.theme }}       {# config = None → ""  #}

{# Defined receiver, missing key — still raises under strict mode #}
{{ config?.theme }}       {# config = {} → UndefinedError #}

{# Safe-in-both-directions forms: #}
{{ config?.theme ?? "" }}         {# catch missing key with ?? #}
{{ config | get("theme", "") }}   {# or the get filter #}
```

Chains short-circuit at the first `None`:

```kida
{{ page?.author?.avatar }}        {# any None in the chain → "" #}
{{ page?.author?.avatar ?? "/default.png" }}  {# with a named fallback #}
```

### `?[...]` — optional item access (receiver-only)

Mirror of `?.`. Short-circuits only on a `None`/undefined receiver:

```kida
{{ settings?["theme"] }}             {# settings is None → "" #}
{{ settings?["theme"] ?? "light" }}  {# also handles missing key #}
{{ items?[0] }}                      {# items is None → "" #}
```

### `| get(key, default)` — filter form (closest to `dict.get`)

```kida
{# Drop-in replacement for dict.get("key", default) #}
{{ config | get("theme", "light") | upper }}
```

The `get` filter handles dicts, objects, and `None` uniformly, and — unlike `?.` alone — also catches missing keys. Prefer it when the value is a key lookup that may be missing, rather than a variable that may be `None`.

### Combining operators

```kida
{# Null-safe chain with a named fallback #}
{{ user?.profile?.bio ?? "No bio yet" }}

{# Pipeline form #}
{{ config ?| get("theme") ?? "light" }}
```

## Common surprises

:::{dropdown} "My `{% if x %}` guard stopped working"
:icon: alert-circle

Under strict mode, `{% if x %}` raises if `x` is not defined. Use `is defined`:

```kida
{# Before (worked in 0.6.x lenient mode) #}
{% if user.nickname %}...{% end %}

{# After (0.7.x strict mode) #}
{% if user.nickname is defined and user.nickname %}...{% end %}
```
:::

:::{dropdown} "I was relying on empty-string fallback in attributes"
:icon: tag

```kida
{# Before — rendered as "" when missing #}
<img src="{{ user.avatar }}">

{# After #}
<img src="{{ user.avatar ?? '/default-avatar.png' }}">
```
:::

:::{dropdown} "K-TPL-004 fires on my template"
:icon: code

The parse-time check catches templates that would have silently rendered empty under 0.6.x lenient mode. The error message names the variable and suggests a fix. Apply one of the three fix patterns above at the reported line.
:::

:::{dropdown} "My test suite prints ~1000 `from_string()` warnings"
:icon: terminal

Fixed in 0.7.1. The warning now fires once per distinct source per `Environment` instead of on every call. If you are still on 0.7.0, you can also pass `name=` explicitly to `from_string()` to silence it and enable bytecode caching.
:::

## Where to go next

- [[docs/troubleshooting/undefined-variable|Troubleshooting `UndefinedError`]] — per-error debugging
- [[docs/reference/tests|Tests Reference]] — full `is defined` / `is none` / etc. list
- [[docs/syntax/variables|Variables & Operators]] — `?.`, `?[`, `??`, `?|`, `|>`
- [CHANGELOG 0.7.0](https://github.com/lbliii/kida/blob/main/CHANGELOG.md#070---2026-04-20) — full release notes
