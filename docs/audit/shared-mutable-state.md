# Shared Mutable State Audit

Audit of module-level and shared mutable state in Kida for free-threading (PEP 703) compliance. Documents which structures are read-only after init, which are protected by locks, and any violations or recommendations.

---

## 1. Module-Level Mutable State

### 1.1 `kida/template/helpers.py` — `STATIC_NAMESPACE`

| Location | Type | Protection | Notes |
|----------|------|-------------|-------|
| `STATIC_NAMESPACE` | `dict[str, Any]` | Read-only after module load | Contains `__builtins__`, `_Markup`, `_UNDEFINED`, etc. Never mutated after import. Safe for concurrent access. |

### 1.2 `kida/template/helpers.py` — `UNDEFINED`

| Location | Type | Protection | Notes |
|----------|------|-------------|-------|
| `UNDEFINED` | `_Undefined` singleton | Immutable | Singleton; no mutable attributes. Safe. |

### 1.3 `kida/render_context.py` — `_render_context`

| Location | Type | Protection | Notes |
|----------|------|-------------|-------|
| `_render_context` | `ContextVar[RenderContext \| None]` | Thread-local by design | ContextVars provide per-thread/async-task isolation. No shared mutable state. |

---

## 2. RenderContext Usage

### 2.1 ContextVar Isolation

- Each `render()` call runs with a `RenderContext` set via `_render_context.set(ctx)`.
- ContextVars propagate correctly to `asyncio.to_thread()` in Python 3.14.
- No cross-thread sharing of `RenderContext` instances.

### 2.2 `template_stack` Copy-on-Raise

**Status:** Fixed.

When constructing `TemplateRuntimeError` or `UndefinedError`, the code passes a **copy** of `render_ctx.template_stack` so that the exception captures the stack at raise time. The macro wrapper's `finally` block mutates the stack (`pop()`), so without a copy the exception could observe a mutated stack when formatted later.

**Implementation:** `template/core.py` `_enhance_error()` passes `list(render_ctx.template_stack)` to exception constructors.

### 2.3 `import_stack` Copy per Child

**Status:** Compliant.

`child_context()` and `child_context_for_extends()` create a **copy** of `import_stack` for each child:

```python
import_stack = list(self.import_stack)
```

This ensures no shared mutable state across extends/import chains when rendering in parallel.

### 2.4 Shared Across Children (Intentional)

The following are **intentionally shared** between parent and child contexts (document-wide scope):

- `cached_blocks` — block cache for `{% cache %}` optimization
- `cache_stats` — hit/miss tracking (protected by lock in `CachedBlocksDict`)
- `_meta` — framework metadata (HTMX, CSRF, etc.)

---

## 3. Cache Access Patterns

### 3.1 Environment Caches

| Cache | Protection | Notes |
|-------|------------|-------|
| `_cache` (LRUCache) | Internal RLock | `kida.utils.lru_cache.LRUCache` uses RLock for all operations. |
| `_fragment_cache` (LRUCache) | Internal RLock | Same. |
| `_template_hashes` | `_cache_lock` (RLock) | All access under `with self._cache_lock`. |
| `_analysis_cache` | Partial | Writes in `core.py` under `_cache_lock`. Reads/writes in `introspection.py` may occur outside lock (see 3.2). |
| `_structure_manifest_cache` | `_cache_lock` | All access in `get_template_structure()` under lock. |

### 3.2 `_analysis_cache` in Introspection

**Location:** `kida/template/introspection.py` — `_analyze()`

- **Read:** `env_for_cache._analysis_cache.get(self._name)` — no lock.
- **Write:** `env_for_cache._analysis_cache[self._name] = self._metadata_cache` — no lock.

**Risk:** Under concurrent access, two threads could both miss the cache and perform duplicate analysis. The worst case is redundant work, not data corruption. Dict assignment in CPython is atomic for simple types; `TemplateMetadata` is a frozen dataclass. **Recommendation:** Consider holding `_cache_lock` when accessing `_analysis_cache` from introspection for strict consistency. Current behavior is acceptable for correctness.

### 3.3 CachedBlocksDict

**Location:** `kida/template/cached_blocks.py`

- `_cached`, `_cached_names`, `_original` — read during lookup; `_original` is mutated by `setdefault`/`__setitem__` (block registration). Block registration is per-render; each render has its own blocks dict.
- `_stats` — shared when `cache_stats` is passed from `RenderContext`. Protected by `_stats_lock` (threading.Lock) for hit/miss recording.

**Status:** Compliant.

---

## 4. Hot Paths — No Shared Mutable State

- **Template.render():** Uses local `buf` list, `RenderContext` from ContextVar. No global or shared mutable state.
- **Generated code:** Calls `lookup`, `lookup_scope`, `_safe_getattr` — all pure or use ContextVar.
- **Include/extends:** Each child gets its own `RenderContext` with copied `import_stack` and `template_stack`.

---

## 5. Summary

| Area | Status | Action |
|------|--------|--------|
| Module-level dicts | OK | Read-only after load |
| RenderContext | OK | ContextVar isolation; copy-on-raise for template_stack |
| import_stack | OK | Copied per child |
| LRU caches | OK | Internal RLock |
| Environment _cache_lock | OK | Protects _template_hashes, _analysis_cache, _structure_manifest_cache |
| _analysis_cache from introspection | Low risk | Optional: hold _cache_lock for strict consistency |
| CachedBlocksDict | OK | Lock for stats when shared |

No critical violations. The codebase is structured for free-threading compliance.
