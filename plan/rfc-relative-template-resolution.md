# RFC: Relative Template Resolution — Refactor-Safe Includes & Imports

**Status**: Draft
**Created**: 2026-04-23
**Target**: v0.9.0
**Estimated Effort**: 14–22 hours
**Dependencies**: None (pure-Python, additive)
**Source**: Dashboard-migration DX feedback (K-TPL-001 path breakage on folder move); Kida include/def/from-import architecture audit (2026-04-23)

---

## Why This Matters

**Core problem**: Every template-to-template reference in Kida is a hard-coded, root-relative path string. When a folder moves, every reference breaks — silently at authoring time, loudly at render time with `K-TPL-001`. There is no compile-time check, no IDE refactor, no locality of reference. Components are not portable across folders; refactors require mass regex find-and-replace.

**Surface symptom** (user feedback): moving `skills/` → `library/skills/` broke every `{% include "skills/_status.html" %}`. The fix requested: relative includes like `{% include "./_status.html" %}`.

**Deeper problem** (the ask behind the ask): *paths and strings are brittle contracts between templates*. The same complaint appears in four places:
1. `{% include "path" %}` — brittle
2. `{% from "path" import def %}` — brittle (feature already exists)
3. `{% extends "path" %}` — brittle
4. `{% embed "path" %}` — brittle

All four route through a single chokepoint: `Loader.get_source(name: str)`. The loader has **no awareness of the calling template**, so it can only resolve against the root. Fix the chokepoint once, and all four cite-sites become refactor-safe.

**The fix** (one sentence): Thread the calling template's logical name through `Loader.get_source()`, teach `FileSystemLoader` to resolve `./` and `../` prefixes against it, and — in a second sprint — add configurable namespace prefixes (`@components/`) for cross-cutting shared components that shouldn't be path-coupled at all.

### Evidence Table

| Source | Finding | This Proposal |
|--------|---------|---------------|
| User feedback (dashboard migration) | Moving `skills/` → `library/skills/` broke every `{% include %}`; required regex-level sweep | **FIXES** — Sprint 1 relative includes (`./x`, `../x`) make within-folder moves zero-edit |
| `src/kida/environment/loaders.py:101` | `get_source(name)` accepts only `name` — no caller context, so relative resolution is impossible | **FIXES** — Sprint 0 extends protocol to `get_source(name, *, caller=None)` with opt-in backward compat |
| `src/kida/environment/loaders.py:105-111` | `_resolved.relative_to(base_resolved)` security check rejects any path traversal outside the search root | **MITIGATES** — Sprint 0 preserves the constraint (resolved path must still fall inside a search base) while allowing `..` *relative to caller* |
| Architecture audit | `{% from "x" import y %}` already exists (`src/kida/parser/blocks/template_structure.py:352`); its import machinery (`_import_macros` at `src/kida/template/render_helpers.py:420`) routes through the same loader | **FIXES** — same loader fix makes `{% from "./card.html" import card %}` work without new syntax |
| Architecture audit | `{% include %}`, `{% extends %}`, `{% embed %}`, `{% from…import %}` all call `env.get_template(name)` directly at render-time with only the *target* name | **FIXES** — Sprint 1 threads caller through every call site in `render_helpers.py` |
| `src/kida/environment/loaders.py` (PrefixLoader) | Prior art for prefix-based namespace resolution exists but requires registering per-loader, not a lightweight config | **UNRELATED** (Sprint 2 extends this pattern with a leaner `@alias/` shorthand) |

Any "UNRELATED" row signals scope not addressed here. `url_for`-style named-route reversing for HTMX (feedback items 2–5) is Chirp's problem, not Kida's — explicitly out of scope.

### Invariants

1. **Existing templates never break** — any template using absolute paths (`"components/card.html"`) renders byte-identical before and after. This is P0 because Kida has downstream consumers (Bengal, Chirp, chirp-ui) with thousands of call sites.
2. **Path traversal protection holds** — resolved paths must still land inside a loader search root. Relative resolution cannot be a sandbox escape.
3. **Zero runtime deps stays zero** — no new dependencies; this is a resolver-layer change only.
4. **Custom loaders keep working** — the `Loader` protocol extension is backward-compatible: old loaders that accept only `(name,)` continue to work; new loaders can opt into caller-aware resolution.

---

## Target Architecture

### Before (current)

```
Template A (pages/about.html)
  {% include "components/card.html" %}
        │
        ▼
  env.get_template("components/card.html")
        │
        ▼
  loader.get_source("components/card.html")   ← caller identity lost
        │
        ▼
  resolves root-relative → templates/components/card.html
```

Moving `components/` anywhere breaks every caller. No way to express "the card next to me."

### After

```
Template A (pages/about.html)
  {% include "./card.html" %}      ← relative to caller
  {% include "../shared/foo.html" %}
  {% include "@components/card" %} ← namespace alias (Sprint 2)
  {% include "components/card.html" %} ← absolute still works
        │
        ▼
  env.get_template("./card.html", caller="pages/about.html")
        │
        ▼
  loader.get_source("./card.html", caller="pages/about.html")
        │
        ├── starts with "./" or "../" → resolve relative to caller's dirname
        ├── starts with "@alias/" → resolve via alias_map
        └── else → resolve root-relative (current behavior)
```

### Types

```python
# src/kida/environment/loaders.py
class Loader(Protocol):
    def get_source(
        self,
        name: str,
        *,
        caller: str | None = None,  # new, keyword-only, optional
    ) -> tuple[str, str | None]: ...
```

Keyword-only + default `None` means:
- Old loaders (positional-only) keep working (runtime adapter wraps them).
- Old call sites that pass only `name` keep working.
- New behavior is strictly additive.

### Resolution rules (in order)

1. Name starts with `./` or `../` and `caller` is provided → resolve against `Path(caller).parent`, then look up the resulting root-relative name through the loader's normal search paths. Traversal check still applies to the *final* resolved path.
2. Name starts with `@<alias>/` and alias is configured → substitute alias root, then root-relative lookup. (Sprint 2)
3. Otherwise → root-relative (current behavior, byte-identical).

### Error semantics

- Relative path with no caller (e.g. `env.get_template("./x")` from Python code) → raise `TemplateNotFoundError` with message: *"Relative paths require a caller template. Use an absolute name or call via `{% include %}` / `{% from %}` / `{% extends %}`."*
- Relative path that escapes above caller's tree but lands inside a search root → allowed (matches current traversal protection).
- Unknown `@alias/` → `TemplateNotFoundError` with message listing available aliases.

---

## Sprint Structure

| Sprint | Focus | Effort | Risk | Ships Independently? |
|--------|-------|--------|------|---------------------|
| 0 | Design & RFC freeze — protocol, security, alias syntax, error messages | 2–3h | Low (paper only) | Yes (this doc) |
| 1 | Relative path resolution (`./`, `../`) for all four loader call sites | 8–12h | Medium (loader protocol change, wide blast radius but guarded by default-`None`) | **Yes** — full user value. Sprint 2 optional. |
| 2 | Namespace aliases (`@components/`, `@layouts/`) via `Environment(template_aliases={...})` | 3–5h | Low (additive, single-file config) | Yes |
| 3 | Docs, migration tutorial, `kida check` warning for hardcoded-move-risk paths (stretch) | 1–2h | Low | Yes |

**Rules being applied**: Sprint 0 solves hard questions on paper. Each sprint ships independently (Sprint 1 alone resolves the user's feedback; Sprint 2 is a power-user upgrade). Effort in hours, not days.

---

## Sprint 0: Design & RFC Freeze

**Goal**: Lock the loader protocol shape, security model, and alias syntax before touching code.

### 0.1 — Loader protocol extension

Decide and document:

- **Signature**: `get_source(name, *, caller=None)` — keyword-only so positional `(name,)` callers are unaffected.
- **Adapter**: `Environment` wraps loaders and detects via `inspect.signature` whether they accept `caller`. Old loaders called with `(name,)`. New loaders called with `(name, caller=…)`. Benchmark: signature introspection happens once at loader registration, not per-call.
- **Deprecation policy**: Old signature is *not* deprecated. It's a supported variant forever; loader authors opt in.

**Acceptance**: Protocol change documented in `plan/rfc-relative-template-resolution.md` (this doc) and a code sketch in the RFC body. PR review on this RFC alone.

### 0.2 — Security model for `..` traversal

Decide:

- **Allowed**: `..` that stays within a loader search root, even if it crosses the caller's subtree.
- **Forbidden**: `..` that resolves outside every search root.
- **Mechanism**: Reuse existing `resolved.relative_to(base_resolved)` check. Apply *after* relative resolution, so security is path-of-record, not syntactic.

**Acceptance**: Threat model documented: "A malicious template can reach any sibling template in any search root via `../`, but nothing outside it. This matches current absolute-path behavior — no new capability granted." Sign-off in RFC.

### 0.3 — Alias syntax

Pick one for Sprint 2 (don't build yet):

- **Option A**: `@components/card.html` — terse, visually distinctive, no collision with valid filenames on any OS.
- **Option B**: `components::card.html` — Rust-style, but `::` is not a path-ish prefix and reads oddly.
- **Option C**: Registered PrefixLoader with empty prefix — already works, but verbose and per-loader.

**Decision**: Option A. `@` is not a legal leading char in any common template filename; visually flags "this is a symbol, not a path."

**Acceptance**: Decision documented; alias config API sketched:

```python
env = Environment(
    loader=FileSystemLoader("templates/"),
    template_aliases={"components": "ui/components", "layouts": "ui/layouts"},
)
```

### 0.4 — Caller-name format

The caller name passed through is the **logical template name** (what `get_source` was originally called with), not the filesystem path. This means:

- Works with non-`FileSystemLoader` loaders (`DictLoader`, `PackageLoader`).
- `Path(caller).parent` operates on the logical name — valid because names are POSIX-style.
- Relative resolution in `DictLoader`: joins caller parent + relative part, normalizes, looks up in dict.

**Acceptance**: `DictLoader` relative-resolution semantics spec'd: `{"pages/about.html": ..., "pages/card.html": ...}` + caller `"pages/about.html"` + name `"./card.html"` → resolves to `"pages/card.html"` → found. Test case drafted (not implemented).

### 0.5 — Error message catalog

Draft messages for:
- `K-TPL-002` (new): *"Relative path `./x` requires a caller template. If calling from Python, use the absolute name `pages/x.html`."*
- `K-TPL-003` (new): *"Relative path `../../../x` escapes all loader search roots. Resolved to `/absolute/path` which is outside: `templates/`."*
- `K-TPL-004` (new): *"Unknown template alias `@foo/`. Configured aliases: `@components/`, `@layouts/`."*

**Acceptance**: All error messages + reproduction scenarios listed in RFC. Existing `K-TPL-001` unchanged.

---

## Sprint 1: Relative Path Resolution

**Goal**: Ship `./` and `../` for all four caller sites. Zero behavior change for absolute paths. This sprint alone resolves the user's feedback.

### 1.1 — Extend `Loader` protocol + `FileSystemLoader` / `DictLoader`

Update `src/kida/environment/loaders.py`:
- Add keyword-only `caller: str | None = None` to `get_source` on `FileSystemLoader`, `DictLoader`, `ChoiceLoader`, `PrefixLoader`, `PackageLoader`, `FunctionLoader`.
- `ChoiceLoader` / `PrefixLoader` forward `caller` to children.
- `FunctionLoader`: `inspect.signature` of the user-supplied callable; pass `caller` only if the callable accepts it.

**Files**: `src/kida/environment/loaders.py` (all six loader classes)
**Acceptance**:
- `rg 'def get_source\(' src/kida/environment/loaders.py` shows caller param on every built-in loader.
- Full test suite passes (invariant 1).

### 1.2 — Add resolution layer in `FileSystemLoader.get_source`

Before the existing search-path loop:

```python
if caller and (name.startswith("./") or name.startswith("../")):
    parent = PurePosixPath(caller).parent
    name = str((parent / name).as_posix())
    # Normalize (resolve `..` in the logical name) without hitting the filesystem
    name = str(PurePosixPath(name).resolve())  # pseudo — use os.path.normpath
```

Then proceed with existing search-path loop; traversal check on resolved path still gates the final filesystem read.

**Files**: `src/kida/environment/loaders.py`
**Acceptance**:
- New test file `tests/environment/test_relative_includes.py` with cases:
  - `{% include "./sibling.html" %}` resolves correctly.
  - `{% include "../other/x.html" %}` resolves correctly.
  - `{% include "../../../etc/passwd" %}` raises `TemplateNotFoundError` (traversal).
  - Relative with no caller raises clear error.
- `DictLoader` behaves identically for matching test cases.

### 1.3 — Thread `caller` through render-time helpers

Update `src/kida/template/render_helpers.py`:
- `_include(template_name, ctx, ignore_missing, *, caller=None)` — pass through.
- `_import_macros(template_name, with_context, ctx, names, *, caller=None)` — pass through.
- `_extends` machinery — pass through.
- `_embed` machinery — pass through.

Each helper passes `caller = render_ctx.template_name` when calling `env.get_template(...)`.

**Files**: `src/kida/template/render_helpers.py`, `src/kida/environment/core.py` (`Environment.get_template` forwards `caller` to loader).
**Acceptance**:
- `rg 'env\.get_template\(' src/kida/template/render_helpers.py` — every call passes `caller=`.
- `rg 'loader\.get_source\(' src/kida/environment/core.py` — every call passes `caller=` when available.

### 1.4 — Update compiler to pass caller to helpers

Update `src/kida/compiler/statements/template_structure.py`:
- `_compile_include` generates `_include(name, ctx, ignore_missing, caller=_render_ctx.template_name)`.
- `_compile_from_import` generates `_import_macros(..., caller=_render_ctx.template_name)`.
- Same for `_compile_extends`, `_compile_embed`.

**Files**: `src/kida/compiler/statements/template_structure.py`
**Acceptance**:
- Integration tests: compile a template with `{% include "./x" %}`, inspect generated Python source for the `caller=` keyword argument. (One test per statement type.)

### 1.5 — Test matrix

Create `tests/environment/test_relative_resolution.py` with the full combinatorial matrix:

| Statement | Relative form | Expected |
|-----------|---------------|----------|
| `include` | `./x` | Resolves to sibling |
| `include` | `../x` | Resolves up one |
| `include` | `../../x` | Resolves up two (if in search root) |
| `from…import` | `./x` | Imports def from sibling |
| `extends` | `./x` | Inherits from sibling |
| `embed` | `./x` | Embeds sibling |
| `include` | `x` | Root-relative (unchanged) |
| `include` | `./x` with no caller (Python-side call) | Error |

**Acceptance**: 8+ test cases pass. Full existing test suite passes (invariant 1).

### 1.6 — Loader protocol back-compat adapter

In `src/kida/environment/core.py`, when calling a custom `Loader`:

```python
sig = inspect.signature(loader.get_source)
accepts_caller = "caller" in sig.parameters
# cached at loader registration
```

If `accepts_caller` is False, call `loader.get_source(name)` (omit kwarg). Old loaders keep working — they just can't resolve relative paths (they get pre-resolved absolute names in Sprint 1.2 via a fallback: `Environment.get_template` resolves `./` / `../` itself before calling old-style loaders, using loader-agnostic path math).

**Files**: `src/kida/environment/core.py`
**Acceptance**:
- Test: a custom loader defined without `caller` still works.
- Test: relative paths resolve correctly even when using a legacy loader (pre-resolution in Environment, not in loader).

---

## Sprint 2: Namespace Aliases (Optional)

**Goal**: Give users a clean way to reference cross-cutting components that aren't locality-bound.

### 2.1 — Alias config on `Environment`

Add `template_aliases: dict[str, str] | None = None` to `Environment.__init__`.

**Files**: `src/kida/environment/core.py`
**Acceptance**:
- `env = Environment(loader=..., template_aliases={"components": "ui/components"})` constructs without error.
- `env.get_template("@components/card.html")` resolves to `"ui/components/card.html"`.

### 2.2 — Alias resolution in `Environment.get_template`

Before loader lookup: if `name.startswith("@")`, split on first `/`, look up alias root, substitute, proceed. Unknown alias → `K-TPL-004`.

**Acceptance**:
- Tests for: valid alias, unknown alias, alias + relative path (interaction: aliases always resolve to absolute; `@components/./x` is invalid — flag at parse? or just fail at resolution with clear error? Document in RFC.)
- Design decision for RFC: aliases do NOT compose with relative. Keep two resolution modes orthogonal.

### 2.3 — Alias syntax in all four statements

Make sure `@alias/x` works in `{% include %}`, `{% from %}`, `{% extends %}`, `{% embed %}`. Should be free — all four go through `Environment.get_template`.

**Acceptance**: One test per statement, using `@components/card.html`.

---

## Sprint 3: Docs & Lint (Stretch)

### 3.1 — Docs: tutorial for refactor-safe templates

Add `site/content/docs/tutorials/refactor-safe-templates.md`:
- Problem: moving folders breaks absolute includes.
- Fix A: relative includes for co-located components.
- Fix B: aliases for shared libraries.
- Migration recipe: `rg '\{% include "' site/content/` to find candidates.

**Acceptance**: New doc exists; referenced from `site/content/docs/syntax/` index.

### 3.2 — `kida check` warning for likely-fragile paths (stretch)

Optional: `kida check --lint` flags `{% include "x/y.html" %}` if `x/` exists as a sibling to the caller (suggesting `./y.html`). Low priority; can be deferred.

**Acceptance**: Opt-in lint flag; no change to default `kida check` behavior.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Custom loaders break from protocol change | Medium | High | Sprint 1.6: signature introspection + pre-resolution adapter. Old loaders keep receiving `(name,)`. |
| Path traversal sandbox escape via `..` | Low | High | Sprint 0.2: existing `.relative_to(base_resolved)` check gates final filesystem read. Relative resolution changes *what* gets resolved, not *whether* the security check runs. |
| Performance regression from signature introspection per call | Low | Medium | Cache `accepts_caller` bool at loader registration time (one `inspect.signature` per loader, not per call). Benchmark before/after in Sprint 1. |
| Ambiguous semantics when `caller` has odd form (e.g. no extension, absolute-looking) | Medium | Low | Sprint 0.4: caller is always the *logical name* as passed to `get_source`. Document and test edge cases. |
| Users expect absolute paths starting with `/` | Low | Low | Document: Kida names are POSIX-like but always relative-to-root. `/x` raises a clear error. |
| Alias syntax collides with future templating needs | Low | Low | Sprint 0.3: `@` chosen specifically because it's not valid in common template filenames on any OS. |

---

## Success Metrics

| Metric | Current | After Sprint 1 | After Sprint 2 |
|--------|---------|----------------|----------------|
| Folder-move edit count (user feedback scenario: `skills/` → `library/skills/` with 5 includes) | 5 path edits | **0 edits** (all `./` relative) | 0 edits |
| Loader protocol breakage for custom loaders | N/A | 0 (adapter) | 0 |
| Performance regression on absolute-path rendering | N/A | <1% (one dict lookup per call) | <1% |
| New test cases | 0 | ≥8 | ≥12 |
| Docs coverage | 0 references to relative paths | Syntax reference updated | Tutorial added |

---

## Relationship to Existing Work

- **`plan/rfc-scoped-slots.md`** — parallel — both are "make Kida a real framework" DX improvements; no resolution-layer overlap.
- **`plan/epic-template-framework-gaps.md`** (complete) — precedent for additive framework-completion work.
- **Chirp `url_for` feedback (items 2–5 from user)** — out of scope here; belongs in Chirp repo. Cross-link from this RFC to the Chirp ticket once filed.
- **Bengal SSG** — downstream consumer; invariant 1 means no migration needed. Bengal templates keep working.
- **chirp-ui** — downstream consumer with heavy `{% def %}` / `{% call %}` use; will benefit from Sprint 1 immediately if it adopts relative imports in new components.

---

## Changelog

- **2026-04-23** — Initial draft. Key insight from audit: `{% from … import … %}` already exists. Primary scope is loader-layer (caller threading + relative resolution), not language-layer.
