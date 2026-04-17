# Design Note: Render Surface Hardening (Sprint 0)

**Epic**: [epic-render-surface-hardening.md](./epic-render-surface-hardening.md)
**Status**: Design (paper only)
**Created**: 2026-04-17
**Author**: Lawrence Lane

Three decisions must land before Sprints 1–3 ship code. This note records them.

---

## Decision 1 — Parity Matrix Corpus

**Question**: Which templates must round-trip identically across render surfaces?

### Dimensions

| Dimension                  | Values                                                            |
| -------------------------- | ----------------------------------------------------------------- |
| Preamble                   | none, `{% let %}`, `{% def %}`, `{% region %}`, `{% from … import %}`, all-four |
| Inheritance depth          | 0, 1, 2                                                           |
| Block style                | `{% block %}`, `{% fragment %}`, `{% region %}`                   |
| `{% globals %}` block      | absent, present                                                   |
| Nested block               | none, `{% region %}` containing `{% block %}`                     |

### Chosen corpus (32 tuples)

Full cartesian is ~120 combinations. We select 32 that cover every dimension pair at least once, weighted toward the failure modes exposed by the `render_block_stream_async` bug (region + top-level preamble).

| #  | Preamble  | Depth | Block style           | Target block name    |
| -- | --------- | ----- | --------------------- | -------------------- |
| 1  | none      | 0     | block                 | `content`            |
| 2  | let       | 0     | block                 | `content`            |
| 3  | def       | 0     | block                 | `content`            |
| 4  | import    | 0     | block                 | `content`            |
| 5  | all       | 0     | block                 | `content`            |
| 6  | none      | 0     | region                | `sidebar`            |
| 7  | let       | 0     | region                | `sidebar`            |
| 8  | def       | 0     | region                | `sidebar`            |
| 9  | import    | 0     | region                | `sidebar`            |
| 10 | all       | 0     | region                | `sidebar`            |
| 11 | none      | 0     | fragment              | `oob`                |
| 12 | let       | 0     | fragment              | `oob`                |
| 13 | import    | 0     | fragment              | `oob`                |
| 14 | none      | 0     | `{% globals %}`+block | `content`            |
| 15 | all       | 0     | region nested in block| `content`, `sidebar` |
| 16 | none      | 1     | block (overridden)    | `content`            |
| 17 | let       | 1     | block (overridden)    | `content`            |
| 18 | def-child | 1     | block (inherits def)  | `content`            |
| 19 | import-ch | 1     | block                 | `content`            |
| 20 | none      | 1     | region (parent-only)  | `sidebar`            |
| 21 | let       | 1     | region (parent-only)  | `sidebar`            |
| 22 | all       | 1     | block + region        | `content`, `sidebar` |
| 23 | none      | 2     | block (deepest wins)  | `content`            |
| 24 | let       | 2     | block                 | `content`            |
| 25 | all       | 2     | block + region        | `content`, `sidebar` |
| 26 | let+def   | 0     | region + let shadow   | `sidebar`            |
| 27 | def       | 0     | region calling def    | `nav`                |
| 28 | import    | 0     | region calling import | `crumbs`             |
| 29 | let       | 1     | fragment              | `oob`                |
| 30 | all       | 1     | fragment              | `oob`                |
| 31 | none      | 0     | block with for-loop   | `list`               |
| 32 | let       | 0     | block with if-branch  | `gate`               |

### Parity assertions per tuple

```python
# Sync-compatible template T, block b, context C:
full     = T.render(C)                                     # if T has a reachable full-render
block    = T.render_block(b, C)
stream   = "".join(T.render_stream(C))
stream_b = "".join(
    chunk async for chunk in T.render_block_stream_async(b, C)
)
assert stream == full
assert stream_b == block
```

### Runtime budget

32 tuples × 4 surfaces × ~2 ms render ≈ 250 ms. With pytest overhead, target **< 2 s**. Measured with `-q --durations=5` during Sprint 1.

---

## Decision 2 — Fragment-Render Scaffold Signature

**Question**: Extract a new helper, or extend `_render_scaffold`?

### Option A — Dedicated scaffolds

```python
@contextmanager
def _fragment_scaffold(self, args, kwargs, method_name):
    ctx = self._build_context(args, kwargs, method_name)
    with render_context(...) as render_ctx:
        render_ctx.declared_definitions = self._declared_definitions
        self._run_globals_setup_chain(ctx)
        yield ctx, render_ctx

@asynccontextmanager
async def _fragment_scaffold_async(self, args, kwargs, method_name):
    ctx = self._build_context(args, kwargs, method_name)
    async with async_render_context(...) as render_ctx:
        render_ctx.declared_definitions = self._declared_definitions
        self._run_globals_setup_chain(ctx)
        yield ctx, render_ctx
```

### Option B — Extend `_render_scaffold(fragment=True)`

```python
@contextmanager
def _render_scaffold(self, args, kwargs, method_name, *,
                    use_cached_blocks=False, enhance_errors=True,
                    fragment=False):
    ...
    with render_context(...) as render_ctx:
        if fragment:
            render_ctx.declared_definitions = self._declared_definitions
            self._run_globals_setup_chain(ctx)
        ...
```

### Tradeoff table

| Criterion                            | Option A                          | Option B                                     |
| ------------------------------------ | --------------------------------- | -------------------------------------------- |
| Sync/async split                     | Natural (two helpers)             | Still needs async variant — flag gets copied |
| Call-site legibility                 | `with self._fragment_scaffold(...)` signals intent | `_render_scaffold(..., fragment=True)` — boolean trap |
| Lines of code                        | ~30 new                           | ~10 new (but bloats an already-busy helper)  |
| Error-enhancement path reuse         | Duplicate (or call into helper)   | Reused via existing try/except               |
| Risk of omitting `declared_definitions` or globals setup in a future method | Low — helpers own it | Low — flag owns it, but easy to pass `fragment=False` by accident |

### Decision: **Option A**

Reasoning:
- The async path already requires a separate `@asynccontextmanager`. Option B still forks on sync/async, so the "single helper" argument is illusory.
- Boolean parameters that toggle structural behavior are a code smell (the classic "flag argument" anti-pattern). Named helpers communicate intent at the call site.
- Error enhancement is wanted for `render_block` and `render_with_blocks` but **not** for `render_block_stream*` (stream methods currently do not wrap exceptions; see existing `enhance_errors=False` usage). Separate helpers let each fragment method choose; a boolean forces one behavior per path.

The pattern family here is closest to **Template Method** (stable scaffold with a variable step), but Python's contextmanager style is the idiomatic expression. Naming: `_fragment_scaffold` + `_fragment_scaffold_async`.

---

## Decision 3 — Sandbox Fuzz Strategy

**Question**: What does hypothesis generate, and what does it assert?

### Name pool

| Source                                   | Count | Example                                           |
| ---------------------------------------- | ----- | ------------------------------------------------- |
| `_SAFE_COLLECTION_METHODS` (safe)        | ~30   | `items`, `keys`, `split`, `join`, `strip`         |
| `_BLOCKED_ATTRS` (must raise)            | ~40   | `__class__`, `__mro__`, `__globals__`, `f_locals` |
| Stdlib dunders NOT in blocklist          | ~8    | `__doc__`, `__name__`, `__qualname__`, `__repr__` |
| Random identifiers                       | ∞     | `st.text(ascii_letters, min_size=1, max_size=8)`  |

The non-blocked stdlib dunders are deliberate: they are neither blocked nor on the safe list, so the property must describe what happens (current behavior: allowed via `safe_getattr` unless `allowed_attributes` restricts). If fuzzing surfaces that one of these leaks a capability, that is a finding.

### Chain shape

Hypothesis strategy: expression tree of depth 1–4.

```python
name       = st.sampled_from(safe_names + blocked_names + other_dunders) | st.identifiers()
attr_chain = st.recursive(name, lambda c: st.tuples(c, name), max_leaves=4)
# Renders to "obj.a.b.c" or "obj.a.method()" at max depth 4.
```

Distribution biased toward depth 2–3 (typical SSTI attack surface — one or two hops into the object model).

### Properties

| # | Property                          | Assertion                                                                                  |
| - | --------------------------------- | ------------------------------------------------------------------------------------------ |
| 1 | **Blocklist is honored**          | Any chain containing a name in `_BLOCKED_ATTRS` raises `SecurityError` before the chain completes. Assert on the exception, never on the value. |
| 2 | **Allowlist mode is closed**      | With `SandboxPolicy(allowed_attributes=frozenset({"name"}))`, any chain whose first attribute is not `"name"` raises. |
| 3 | **Default ≠ Sandboxed**           | A curated corpus of 6–10 expressions that succeed under default `Environment` must fail under `SandboxedEnvironment`. Guards against accidental weakening. |
| 4 | **`max_range` enforced**          | `{% for x in range(N) %}...{% end %}` raises `SecurityError` iff `N > policy.max_range`. Fuzz N over the full int64 range. |
| 5 | **`max_output_size` enforced**    | A template producing `N` characters raises iff `N > policy.max_output_size`. Fuzz N and the per-chunk size. |

Property 3 gets a fixed corpus (not hypothesis-generated) because it encodes the **differential** between modes — hypothesis would generate noise. A handful of hand-picked escapes (`"".__class__`, `[].__class__.__mro__[-1].__subclasses__()`, `().__class__.__base__`) is enough.

### Hypothesis settings

```python
from hypothesis import settings, seed, HealthCheck

common = settings(
    max_examples=200,
    deadline=None,                        # CI variance
    suppress_health_check=[HealthCheck.too_slow],
)
```

- `@seed(0)` for reproducibility in CI logs.
- No shared state across properties — each builds its own `SandboxedEnvironment`.
- Wall-time budget: < 5 s total for `tests/test_sandbox_fuzz.py`.

### Handling a real finding

If a property fails on hypothesis-shrunk input, the test **must not be hot-fixed** by suppressing the example. Protocol:

1. Capture the shrunken input in the hypothesis cache (automatic).
2. Open a private security advisory per `SECURITY.md` (do not post the repro in a public PR).
3. Patch the blocklist or helper, re-run the fuzz, confirm green.

---

## Acceptance

- [ ] This file exists at `plan/design-render-surface-hardening.md` (✓ with this commit).
- [ ] Reviewed by the Sprint 1 implementer before code starts.
- [ ] Any deviation in Sprint 1–3 execution is recorded as an amendment to this note, not as silent drift.
