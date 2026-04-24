---
title: Refactor-Safe Templates
description: Move folders without breaking a single include — relative paths and namespace aliases
draft: false
weight: 16
lang: en
type: doc
tags:
- tutorial
- refactoring
- includes
- aliases
- relative-paths
keywords:
- relative includes
- template aliases
- refactor
- folder move
- "@components"
- "./"
- "../"
icon: folder-tree
---

# Refactor-Safe Templates

Move a folder of templates without touching a single reference inside it.

:::note[Why this tutorial exists]
Hard-coded, root-relative include paths are brittle: rename `skills/` to `library/skills/` and every `{% include "skills/_status.html" %}` breaks silently at authoring time and loudly at render time. Kida 0.9 ships two resolution modes that eliminate the problem — relative paths (`./`, `../`) for co-located partials, and namespace aliases (`@components/`) for shared libraries. Pick the right tool for each reference and folder moves become zero-edit refactors.
:::

## TL;DR

| Reference style | Use when | Survives folder move? |
|---|---|---|
| `{% include "./_card.html" %}` | Partial lives next to the caller | **Yes** — the pair moves together |
| `{% include "../shared/nav.html" %}` | Partial lives one folder up | **Yes** — as long as the subtree moves as a unit |
| `{% include "@components/card.html" %}` | Shared component library (cross-cutting) | **Yes** — alias root changes, call sites don't |
| `{% include "components/card.html" %}` | Only if the root path is truly stable | Only while `components/` stays put |

Rule of thumb: if a partial is **owned by the caller's folder**, use `./` or `../`. If it belongs to a **shared library** used from many folders, use an alias.

## The Problem

Consider this layout:

```
templates/
├── skills/
│   ├── page.html
│   ├── _status.html
│   └── _trust.html
```

`skills/page.html` includes its co-located partials:

```kida
{# skills/page.html #}
{% include "skills/_status.html" %}
{% include "skills/_trust.html" %}
```

Now move `skills/` to `library/skills/`. Every include breaks:

```
TemplateNotFoundError: Template 'skills/_status.html' not found
```

You reach for `ripgrep`, sweep every reference, and hope no dynamic `{% include "skills/" + name %}` slipped through. Meanwhile the partials still live right next to `page.html` — the relationship never changed, only the absolute prefix did.

## Fix A: Relative Paths for Co-Located Partials

Use `./` when the partial is a sibling, `../` when it's one folder up. The caller references its neighbors the way it would in any filesystem:

```kida
{# skills/page.html — before #}
{% include "skills/_status.html" %}
{% include "skills/_trust.html" %}

{# skills/page.html — after #}
{% include "./_status.html" %}
{% include "./_trust.html" %}
```

Now move `skills/` → `library/skills/`. **Zero edits.** The co-located partials move as a unit; their relative relationship is unchanged.

Relative paths resolve against the caller's directory at the time `{% include %}` / `{% extends %}` / `{% embed %}` / `{% from ... import ... %}` is evaluated — so they also work inside nested includes. A partial that includes its own neighbor keeps working no matter who included it.

```kida
{# pages/post.html #}
{% include "./partials/card.html" %}

{# pages/partials/card.html #}
{% include "./_tag.html" %}   {# → pages/partials/_tag.html #}
```

### Edge cases

- **Path traversal still fires.** `{% include "../../../etc/passwd" %}` from a shallow caller raises `TemplateNotFoundError` — the resolved path must still land inside a loader search root.
- **Python callers need absolute names.** `env.get_template("./card.html")` from Python raises a clear error. Relative resolution only makes sense from inside a template.
- **Interior `..` is fine** as long as the final resolved path stays within a search root: `./foo/../card.html` from `pages/about.html` resolves to `pages/card.html`.

## Fix B: Namespace Aliases for Shared Libraries

Relative paths are perfect for partials owned by one folder. But a shared component library — a card, a nav, a button — is used from everywhere. Writing `../../../ui/components/card.html` from a deeply nested page is just as brittle as a hard-coded absolute path.

Configure an alias once on the `Environment`, then reference it by short name from anywhere:

```python
from kida import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader("templates/"),
    template_aliases={
        "components": "ui/components",
        "layouts": "ui/layouts",
    },
)
```

```kida
{# Any template, any depth: #}
{% extends "@layouts/base.html" %}        {# → ui/layouts/base.html #}
{% include "@components/card.html" %}      {# → ui/components/card.html #}
{% from "@components/nav.html" import nav %}
{% embed "@layouts/shell.html" %}{% end %}
```

Move `ui/components/` to `shared/ui/components/`? Change one line of Python:

```python
template_aliases={
    "components": "shared/ui/components",
    "layouts": "shared/ui/layouts",
}
```

No template edits. Every `@components/` reference keeps working.

### Alias rules

- **Prefix is `@name/`.** `@` was picked specifically because it's not a legal leading character in common template filenames, so it can't collide with a real path.
- **Aliases resolve before loader lookup.** `{% include "@components/card.html" %}` becomes `{% include "ui/components/card.html" %}` internally, then the normal loader pipeline runs.
- **Unknown aliases fail loudly** with a list of configured aliases:
  ```
  TemplateNotFoundError: Unknown template alias '@widgets/'.
  Configured aliases: @components/, @layouts/
  ```
- **Aliases and relative paths don't compose.** `@components/./foo` resolves via the alias first (`ui/components/./foo`), then `./` is a no-op segment. Keep the two modes orthogonal — if you find yourself wanting composition, the component probably belongs in a different alias.

## Which Fix for Which Reference

```
templates/
├── pages/
│   ├── about.html              # caller
│   ├── _hero.html              # → ./_hero.html        (Fix A)
│   └── partials/
│       └── _card.html          # → ./partials/_card.html (Fix A)
├── shared/
│   └── nav.html                # → ../shared/nav.html  (Fix A)
└── ui/
    └── components/
        └── button.html         # → @components/button.html (Fix B)
```

Rules of thumb:

1. **Partial only makes sense inside this caller's folder?** Use `./`.
2. **Partial is a couple folders away but moves as part of the same subtree?** Use `../`.
3. **Partial is a cross-cutting primitive used from many unrelated pages?** Make it an alias.
4. **Can't decide?** Start with relative. Promote to an alias once three or more unrelated callers reference it.

## Migration Recipe

Use this to sweep an existing project in one pass.

### 1. Inventory every cross-template reference

Let Kida find the easy wins for you first:

```bash
kida check templates/ --lint-fragile-paths
```

That flags every `{% include %}` / `{% extends %}` / `{% embed %}` / `{% import %}` / `{% from %}` whose target lives in the same folder as the caller and suggests the refactor-safe `./` form. Fix those in one pass — no thinking required.

For a broader sweep, scan every cross-template reference by hand:

```bash
rg --pcre2 '\{% (include|extends|embed|from\s+") "[^"]+' templates/ -o -N
```

That lists every absolute reference. You're looking for two patterns:

- **Same-folder or near-sibling paths** — candidates for `./` / `../`.
- **Paths rooted at a shared library prefix** (e.g. `ui/components/...`, `layouts/...`, `partials/...`) — candidates for aliases.

### 2. Convert same-folder references to `./`

For each page file, find references whose target lives in the same folder. Example sweep for `skills/`:

```bash
rg '\{% include "skills/' templates/skills/
```

Rewrite:

```diff
- {% include "skills/_status.html" %}
+ {% include "./_status.html" %}
```

### 3. Promote shared libraries to aliases

If you see three or more folders referencing `ui/components/*`, alias it:

```python
env = Environment(
    loader=FileSystemLoader("templates/"),
    template_aliases={"components": "ui/components"},
)
```

Then sweep:

```bash
rg '\{% include "ui/components/' templates/ -l
```

Rewrite:

```diff
- {% include "ui/components/card.html" %}
+ {% include "@components/card.html" %}
```

### 4. Test that nothing moved

Existing absolute paths are **guaranteed byte-identical** after the upgrade — no template that keeps hard-coded paths needs a change. Run your test suite; nothing should shift.

### 5. Actually move a folder

The whole point. Pick a folder that only uses `./` / `../` internally and rename it:

```bash
git mv templates/skills templates/library/skills
```

Render a page. It should just work.

## When Not to Refactor

- **Dynamic includes** — `{% include "components/" + widget_type + ".html" %}` can't be converted to `./` without losing the dynamic part. Leave these absolute, or alias the prefix.
- **One-off paths that are unlikely to move** — `{% include "templates/404.html" %}` in a single error handler is fine as-is. The migration is opt-in per reference.
- **Generated templates** — if another tool writes include paths, upgrade that tool, not the output.

## See Also

- [[docs/syntax/includes|Includes]] — Full include syntax including `Relative Paths` and `Namespace Aliases` sections.
- [[docs/syntax/inheritance|Inheritance]] — `{% extends %}` accepts the same relative and alias forms.
- `plan/rfc-relative-template-resolution.md` — Design document for the resolution system.
