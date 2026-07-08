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

**Risk:** Under concurrent access, two threads could both miss the cache and perform duplicate analysis. The worst case is redundant work, not data corruption. Individual dict operations are memory-safe on the supported free-threaded CPython runtime, but the compound miss/compute/store sequence is intentionally not atomic; each stored `TemplateMetadata` is complete before publication. **Recommendation:** Consider holding `_cache_lock` when accessing `_analysis_cache` from introspection if single-computation behavior becomes a requirement. Current behavior is acceptable for correctness.

### 3.3 CachedBlocksDict

**Location:** `kida/template/cached_blocks.py`

- `_cached`, `_cached_names`, `_original` — read during lookup; `_original` is mutated by `setdefault`/`__setitem__` (block registration). Block registration is per-render; each render has its own blocks dict.
- `_stats` — shared when `cache_stats` is passed from `RenderContext`. Protected by `_stats_lock` (threading.Lock) for hit/miss recording.

**Status:** Compliant.

### 3.4 Concurrent Miss, Invalidation, And Eviction Contract

**Owners and mechanisms:**

- The environment template cache is an `LRUCache`; `_cache_lock` also protects
  its source hashes, mtimes, analysis results, and structure manifests.
  `clear_template_cache()` uses the same environment lock as miss compilation
  and publication.
- The fragment cache and standalone `LRUCache` protect get, set, delete, clear,
  LRU ordering, TTL metadata, and size eviction with an internal `RLock`.
  `get_or_set()` deliberately computes the factory outside the lock, then
  rechecks the key before publishing a complete value.
- `BytecodeCache` writes to a unique same-directory temporary file and uses an
  atomic replace. Source and static-context hashes select distinct cache files;
  `clear()` is best-effort file invalidation and may race with a new atomic
  publication.

**Invalidation semantics:** Clear operations remove entries visible at the time
they acquire/enumerate their cache. They are not generation barriers and do not
cancel an already-running template compilation, fragment factory, LRU factory,
or bytecode write. An in-flight reader may therefore publish a valid entry after
clear returns. Callers that require a quiescent empty cache must first stop
producers. Concurrent consumers may observe either a valid hit or a miss; they
must never observe a partial value, torn bytecode file, cross-key output, or a
size above an in-memory cache's configured maximum after an operation completes.

**Proof:**

- `TestSharedEnvironmentStress.test_concurrent_template_misses_clear_and_eviction`
- `TestSharedEnvironmentStress.test_concurrent_fragment_misses_clear_and_eviction`
- `TestLRUCacheConcurrency.test_concurrent_misses_clear_and_eviction`
- `TestBytecodeCacheConcurrency.test_concurrent_misses_clear_and_source_hash_invalidation`

All four tests use per-round barriers rather than sleeps. They run in the
required `PYTHON_GIL=0` safety jobs and validate exact rendered/cache values,
bounded eviction, source-hash isolation, executable bytecode hits, and absence
of leaked temporary bytecode files.

---

## 4. Hot Paths — No Shared Mutable State

- **Template.render():** Uses local `buf` list, `RenderContext` from ContextVar. No global or shared mutable state.
- **Generated code:** Calls `lookup`, `lookup_scope`, `_safe_getattr` — all pure or use ContextVar.
- **Include/extends:** Each child gets its own `RenderContext` with copied `import_stack` and `template_stack`.

### 4.1 Shared `Template` Read Contract

**Owner:** The `Environment`/loader creates the compiled `Template`; callers may
share that object across threads for read-only rendering and introspection.

**State and mutation protocol:**

- Generated render functions, the optimized AST, block functions, and template
  identity are read-only after compilation.
- Full, block, and streaming renders allocate their output buffers and
  `RenderContext` per invocation. The current context is isolated by
  `ContextVar`; it is not stored on the shared `Template`.
- `_metadata_cache` and `_def_metadata_cache` are lazy publication caches. Two
  readers may compute the same value concurrently, but each publishes a
  complete metadata result. Metadata records are frozen, and their contained
  mappings are treated as read-only by contract. Duplicate computation is
  allowed; partial metadata is never exposed.
- The related `Environment._analysis_cache` behavior and its redundant-work
  limitation remain documented in section 3.2.

**Proof:**
`TestMixedRenderConcurrency.test_shared_template_render_block_stream_and_introspection`
uses a barrier to start 12 workers together and repeatedly mixes `render`,
`render_stream`, `render_block`, and first-use metadata/list operations on one
compiled template. Every render uses a unique context marker to detect leakage.
The test uses futures and synchronization rather than sleeps and runs in the
required `PYTHON_GIL=0` thread-safety job.

**Unsupported mutation:** Callers must not mutate private compiled functions,
AST fields, or metadata cache attributes while reads are in flight. Registry or
loader mutation follows the separate `Environment` copy-on-write/cache contract;
it is not a `Template` mutation API.

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
| Cache miss/invalidation/eviction | OK | RLock or atomic file publication; clear is not a generation barrier; synchronized no-GIL proof |
| Shared Template reads | OK | Local/ContextVar render state; complete metadata publication; synchronized no-GIL proof |

No critical violations. The codebase is structured for free-threading compliance.
