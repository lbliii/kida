# RFC: Template Helpers Any Reduction

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Created** | 2026-03-07 |
| **Depends On** | `rfc-type-suppression-reduction.md` (Implemented) |
| **Target** | Python 3.14+ |

---

## Summary

Reduce `Any` usage in Kida's template runtime helpers (`helpers.py`, `render_helpers.py`, `environment/filters/_validation.py`) to improve type safety without breaking the polymorphic nature of template context. This RFC complements the completed mixin/type-suppression work by addressing the remaining ~20 `Any` hotspots in runtime code.

---

## Problem Statement

### Current State

The code grade identified `Any` concentration in:

| File | Count | Locations |
|------|-------|-----------|
| `template/helpers.py` | 4 | `_Undefined.get()`, `safe_getattr()`, `getattr_preserve_none()` |
| `template/render_helpers.py` | 4 | `MacroWrapper.__call__`, `_make_macro_wrapper()`, `make_render_helpers()` |
| `template/core.py` | 8 | `render()`, `render_block()`, `_render_func()`, `render_stream()`, `render_async()`, etc. |
| `environment/filters/_validation.py` | 2 | `_filter_default()`, `_filter_require()` |

### Why It Matters

1. **IDE support**: `Any` disables autocomplete and type inference for consumers
2. **Refactoring risk**: Changes to helper signatures won't be caught
3. **Documentation**: Types serve as inline documentation
4. **Consistency**: Parser/compiler/analysis are well-typed; runtime helpers lag

### Constraints

- **Template context is polymorphic**: `render(**kwargs)` accepts arbitrary `str` keys and values (page, site, user, etc.)
- **Filters operate on arbitrary values**: `default`, `require` must accept any template value
- **Macros are user-defined**: `MacroWrapper` wraps arbitrary callables
- **No runtime cost**: All changes are type-only; no behavior change

---

## Proposed Solution

### Design Principles

1. **Prefer `object` over `Any`** where values are truly arbitrary (e.g., filter inputs)
2. **Use `Callable` with explicit params** where signatures are known
3. **Use `TypedDict` or `Mapping`** only where shapes are stable and documented
4. **Accept `Any` where necessary** (e.g., `render(**kwargs)` — template context is inherently dynamic)

### Phase 1: Low-Risk Replacements (Est. 1–2 hours)

#### 1.1 `template/helpers.py`

| Location | Before | After | Rationale |
|----------|--------|-------|-----------|
| `_Undefined.get(key, default)` | `default: Any`, return `Any` | `default: object \| None`, return `object` | Return is default or ""; both are object |
| `_Undefined.keys()` | `list[Any]` | `list[str]` | Keys are always strings in template context |
| `_Undefined.values()` | `list[Any]` | `list[object]` | Values are arbitrary |
| `_Undefined.items()` | `list[tuple[Any, Any]]` | `list[tuple[str, object]]` | Key=str, value=object |
| `safe_getattr(obj, name)` | `obj: Any`, `-> Any` | `obj: object`, `-> object` | Object is arbitrary; return is value or UNDEFINED (both are object) |
| `getattr_preserve_none(obj, name)` | `obj: Any`, `-> Any` | `obj: object`, `-> object` | Same as above |

**Note**: `UNDEFINED` is a singleton instance; its type is `_Undefined`. Using `object` for the return type is accurate (both real values and UNDEFINED are objects) and improves over `Any`.

#### 1.2 `environment/filters/_validation.py`

| Location | Before | After | Rationale |
|----------|--------|-------|-----------|
| `_filter_default(value, default, boolean)` | `value: Any`, `default: Any`, `-> Any` | `value: object`, `default: object`, `-> object` | Filters accept/return arbitrary template values |
| `_filter_require(value, message, field_name)` | `value: Any`, `-> Any` | `value: object`, `-> object` | Same |

**Verification**: `ty check` and `pytest tests/` must pass.

---

### Phase 2: Render Helpers (Est. 2–3 hours)

#### 2.1 `template/render_helpers.py`

| Location | Before | After | Rationale |
|----------|--------|-------|-----------|
| `MacroWrapper._fn` | `Callable[..., Any]` | `Callable[..., object]` | Macros return template-renderable values |
| `MacroWrapper.__call__(*args, **kwargs)` | `*args: Any`, `**kwargs: Any` → `Any` | `*args: object`, `**kwargs: object` → `object` | Match `_fn` signature |
| `_make_macro_wrapper(macro_fn: Any, ...)` | `macro_fn: Any` | `macro_fn: Callable[..., object]` | Macros are callables |
| `make_render_helpers(env_ref: Any)` | `env_ref: Any` | `env_ref: Callable[[], Environment \| None]` | WeakRef callable returns Environment or None |
| `_wrap_blocks_if_cached(blocks)` | `dict[str, Any]` | `dict[str, object]` or keep `BlocksDict` | Blocks dict has string keys, block content as object |

**env_ref typing**: The actual type is `Callable[[], Environment | None]` (WeakRef protocol). We can add:

```python
from typing import Protocol

class EnvRef(Protocol):
    def __call__(self) -> Environment | None: ...
```

Then `make_render_helpers(env_ref: EnvRef)`.

#### 2.2 `template/core.py` — Render Signatures

**Recommendation**: Keep `*args: Any, **kwargs: Any` for `render()`, `render_block()`, etc.

**Rationale**: Template context is inherently dynamic. Callers pass `page=page`, `site=site`, `user=user` — the keys and types vary per template. Using `**kwargs: object` would still require `Any` for the internal `ctx` dict. TypedDict would require a different TypedDict per template, which is impractical.

**Documentation improvement**: Add a docstring note:

```python
def render(self, *args: Any, **kwargs: Any) -> str:
    """Render template with the given context.

    Context is passed as keyword arguments. Common keys include
    ``page``, ``site``, ``user`` — types vary by template.
    """
```

No type change; documentation only.

---

### Phase 3: Optional — TypedDict for Known Helpers (Future)

If we want stricter typing for the *return* of `make_render_helpers()`:

```python
class RenderHelpers(TypedDict, total=False):
    _include: Callable[..., str]
    _extends: Callable[..., str]
    _include_stream: Callable[..., Iterator[str]]
    # ...
```

**Deferred**: The helpers dict is internal; improving the *factory* signature (`env_ref`) gives most of the benefit. Full TypedDict is optional.

---

## Implementation Plan

### Order of Implementation

```yaml
Phase 1 (Low-Risk) - 1-2 hours:
  - [ ] 1.1: helpers.py — object instead of Any for get, safe_getattr, getattr_preserve_none
  - [ ] 1.2: filters/_validation.py — object for _filter_default, _filter_require
  - [ ] 1.3: Run ty check, pytest

Phase 2 (Render Helpers) - 2-3 hours:
  - [ ] 2.1: render_helpers.py — MacroWrapper, _make_macro_wrapper, make_render_helpers
  - [ ] 2.2: core.py — docstring only for render(**kwargs)
  - [ ] 2.3: Run ty check, pytest

Phase 3 (Optional):
  - [ ] 3.1: RenderHelpers TypedDict if desired
```

### Verification

After each phase:

```bash
uv run ty check
uv run pytest tests/ -x
uv run ruff check src/
```

---

## Success Criteria

| Metric | Before | After Phase 1 | After Phase 2 |
|--------|--------|---------------|---------------|
| `Any` in helpers.py | 4 | 0 | 0 |
| `Any` in render_helpers.py | 4 | 4 | 1 (MacroWrapper return if kept) |
| `Any` in filters/_validation.py | 2 | 0 | 0 |
| `Any` in core.py | 8 | 8 | 8 (unchanged; documented) |
| ty check | Pass | Pass | Pass |
| pytest | Pass | Pass | Pass |

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `object` too strict for some call sites | Low | `object` is supertype of all; should be compatible |
| EnvRef Protocol breaks WeakRef | Low | `Callable[[], T]` is structural; WeakRef satisfies it |
| Filter coercion (int/str from YAML) | None | Filters already coerce; types describe runtime values |

---

## Alternatives Considered

### A. Leave as-is

**Rejected**: Code grade identified this as the main improvement area. Low effort, high clarity gain.

### B. Full TypedDict for render context

**Rejected**: Template context is user-defined per template. No single TypedDict fits all.

### C. Generic TypeVar for helpers

```python
def safe_getattr(obj: T, name: str) -> T | _Undefined:
```

**Rejected**: `T` would need to be bound; template values are heterogeneous. `object` is simpler.

---

## References

- `plan/rfc-type-suppression-reduction.md` — Completed type work
- `plan/rfc-mixin-protocol-typing.md` — Parser/compiler protocols
- Kida code grade (2026-03-07) — Identified Any hotspots
