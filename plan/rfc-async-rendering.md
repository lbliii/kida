# RFC: Native Async Template Rendering

**Status**: ✅ Implemented  
**Created**: 2026-02-07  
**Updated**: 2026-02-08  
**Based On**: chirp.ai/chirp.data integration requirements  
**Minimum Python**: 3.14 (async generators, free-threading)

---

## Executive Summary

Chirp's unified data + AI layer reveals a gap in kida: template rendering is
synchronous. When a template context contains async sources — database cursors,
LLM token streams, real-time event feeds — chirp must orchestrate rendering
externally (re-rendering blocks per event, resolving awaitables before render).

Native async rendering in kida would enable:

1. **`{% async for %}` loops** that consume async iterables directly
2. **`{{ await expr }}` expressions** that resolve awaitables inline
3. **Async `render_stream()`** that yields chunks as async data resolves
4. **Block-level progressive rendering** where blocks stream independently

This is an optimization for after the initial chirp.data/chirp.ai launch.
The current pattern (chirp-level orchestration with existing `render_block()`)
works today. This RFC describes the engine-level improvements for v2.

---

## Problem Statement

### Current State

kida has four rendering methods, all fundamentally synchronous:

| Method | Signature | Behavior |
|--------|-----------|----------|
| `render()` | `-> str` | Full render to string (StringBuilder pattern) |
| `render_stream()` | `-> Iterator[str]` | Yields chunks at statement boundaries |
| `render_block()` | `-> str` | Renders a single named block |
| `render_async()` | `-> str` | Runs `render()` in `asyncio.to_thread()` |

`render_async()` is a thread-pool wrapper, not a native async renderer.
Template variables are eagerly evaluated — `{% for %}` calls `list()` on its
iterable before iteration begins.

### The Gap

In chirp's AI streaming pattern, the handler re-renders a block for every
token:

```python
async def generate():
    text = ""
    async for token in llm.stream(prompt):
        text += token
        yield Fragment("chat.html", "response", text=text)
return EventStream(generate())
```

This works but is wasteful: each token triggers a full block render with the
entire accumulated text. For a 2000-token response, that's 2000 renders of
increasing size — roughly O(n^2) total work.

With native async rendering, the template itself could consume the token stream:

```html
{% block response %}
<div id="answer">{% async for token in tokens %}{{ token }}{% endfor %}</div>
{% endblock %}
```

The block streams output as tokens arrive — O(n) total work, one render.

---

## Proposed Design

### Phase 1: `{% async for %}` and `{{ await }}`

**Parser changes** (`parser/blocks/control_flow.py`):

- Add `_parse_async_for()` that accepts `{% async for item in iterable %}`
- Existing `AsyncFor` node in `nodes.py` (line 242) already defines the AST
- Register `"async"` in `_BLOCK_PARSERS` (`parser/statements.py` line 30) with
  two-token lookahead: `async` + `for` dispatches to `_parse_async_for()`

**Compiler changes** (`compiler/statements/control_flow.py`):

- Add `_compile_async_for()` that generates `ast.AsyncFor` instead of
  `ast.For` + `list()` conversion
- Current `_compile_for()` does `_loop_items = list(_iter_source_N)` — the async
  version skips the `list()` call and generates `async for` directly
- Register `"AsyncFor"` in the compiler dispatch table (`compiler/core.py`
  line 738) alongside the existing `"For"` entry
- Flag the compiled function as needing `async def` when async constructs are
  present (propagates to the enclosing `_render_stream_async` function)

**Expression changes** (`compiler/expressions.py`):

- Support `{{ await some_coroutine }}` syntax for inline awaitable resolution
- Compile `Await` nodes (already defined in `nodes.py` line 871) to
  `ast.Await` — wraps the inner expression in an `await`
- See [Await Error Model](#await-error-model) for runtime behavior

### Phase 2: Async `render_stream()`

**Template core changes** (`template/core.py`):

- Add `render_stream_async()` that returns `AsyncIterator[str]`
- The compiler generates `async def _render_stream_async(ctx, blocks)` when
  the template contains any async constructs
- Yields chunks at statement boundaries (same as sync stream) but can also
  yield mid-loop for `{% async for %}` loops

**Key insight**: The compiler already generates two functions per template —
`_render()` (StringBuilder) and `_render_stream()` (generator). Adding a third
(`_render_stream_async()`, async generator) follows the same pattern.

### Phase 3: Block-Level Async Streaming

**Block rendering** (`template/core.py`):

- Add `render_block_stream_async()` that renders a single block as an async
  stream
- Compile async block functions as `_block_name_stream_async()` alongside the
  existing `_block_name()` and `_block_name_stream()` pair
- This enables chirp's Fragment pattern to stream block content as it renders,
  rather than rendering the entire block to a string first

**Integration with chirp**:

```python
# Instead of re-rendering the block per token (O(n^2)):
async for token in llm.stream(prompt):
    yield Fragment("chat.html", "response", text=accumulated)

# The template itself streams (O(n)):
tmpl = env.get_template("chat.html")
async for chunk in tmpl.render_block_stream_async("response", tokens=stream):
    yield SSEEvent(data=chunk, event="fragment")
```

---

## Design Decisions

### Loop Variables in Async For-Loops

The sync `{% for %}` loop calls `list()` on the iterable to enable `LoopContext`
variables that require knowing the collection size upfront:

| Variable | Requires length? | Available in async? |
|----------|-----------------|-------------------|
| `loop.index` / `loop.index0` | No | Yes |
| `loop.first` | No | Yes |
| `loop.last` | **Yes** | **No** |
| `loop.length` | **Yes** | **No** |
| `loop.revindex` / `loop.revindex0` | **Yes** | **No** |
| `loop.cycle()` | No | Yes |
| `loop.depth` | No | Yes |
| `loop.previtem` / `loop.nextitem` | Look-ahead | **No** (`nextitem` requires buffering) |

**Decision**: `{% async for %}` provides a reduced `LoopContext` with
index-forward variables only. Accessing `loop.length`, `loop.last`, or
`loop.revindex` inside an async for-loop raises `TemplateRuntimeError` with
a clear message explaining that async iterables don't support size-dependent
loop variables.

**Rationale**: Buffering the entire async iterable to enable `loop.length`
defeats the purpose of async streaming. The template author should use
`{% for %}` (sync, eagerly materialized) when they need length-dependent
variables, and `{% async for %}` when they need lazy streaming.

`loop.previtem` is available (it only requires remembering the last value).
`loop.nextitem` is unavailable — it requires one-item look-ahead buffering
which adds complexity for marginal benefit.

### AsyncFor Feature Parity

The existing `AsyncFor` node (`nodes.py` line 242) omits two fields present
on the sync `For` node:

| Field | `For` | `AsyncFor` | Decision |
|-------|-------|-----------|----------|
| `target` | Yes | Yes | — |
| `iter` | Yes | Yes | — |
| `body` | Yes | Yes | — |
| `empty` | Yes | Yes | — |
| `recursive` | Yes | **No** | Omit — recursive async iteration is undefined |
| `test` | Yes | **No** | **Add** — inline `if` filtering is useful for async |

**Add `test` to `AsyncFor`**: `{% async for item in stream if item.valid %}`
is a natural filter that avoids yielding output for items that fail the test.
The compiler wraps the loop body in `if test:` — same as sync.

**Omit `recursive`**: Recursive loops (`{% for item in tree recursive %}`)
require re-invoking the loop body as a callable. With async iterables, the
semantics are unclear (does the recursive call also produce an async iterable?).
Defer until a concrete use case emerges.

### Await Error Model

`{{ await expr }}` resolves an awaitable inline during rendering. The key
question is what happens when the expression is not awaitable.

**Strategy: Compile-time detection + runtime fallback.**

1. **Compile time**: The parser emits an `Await` node. The compiler generates
   `ast.Await(expr)`. If the enclosing function is not `async def`, Python
   itself raises `SyntaxError` at compile time. Since `{{ await }}` forces the
   template into async mode, this is handled by the async detection walk.

2. **Runtime**: If the awaited expression is not a coroutine, Python raises
   `TypeError: object X can't be used in 'await' expression`. Kida catches
   this in the standard error enhancement path (`template/core.py` line 673)
   and re-raises as `TemplateRuntimeError` with template context:

   ```
   TemplateRuntimeError: Cannot await 'str' object in template 'chat.html', line 12.
   Expression: {{ await user.name }}
   Hint: {{ await }} is for coroutines and awaitables. Use {{ user.name }} for
   synchronous values.
   ```

3. **Sync render of async template**: Calling `render()` or `render_stream()`
   on a template that contains `{{ await }}` or `{% async for %}` raises
   `TemplateRuntimeError` at call time (not deep in rendering) with a message
   directing the caller to use `render_stream_async()`.

### Template Inheritance and Async Taint

When a child template overrides a block with async content, the async taint
propagates through the inheritance chain.

**Example**:

```html
{# base.html — no async content #}
<body>{% block content %}{% endblock %}</body>
```

```html
{# chat.html — extends base, overrides with async block #}
{% extends "base.html" %}
{% block content %}
  {% async for token in stream %}{{ token }}{% endfor %}
{% endblock %}
```

The parent's render function calls the child's `_block_content()`. If the
child block is async, the parent must `await` it.

**Strategy: Async block dispatch at runtime, not compile time.**

Block functions are stored in a namespace dict and resolved by name at render
time. The compiler generates both sync and async variants for every block in
an async template:

- `_block_content(ctx, _blocks) -> str` — sync version (raises if async
  content is encountered)
- `_block_content_stream_async(ctx, _blocks) -> AsyncIterator[str]` — async
  version

When `render_stream_async()` calls a block, it checks for the async variant
first. When `render_stream()` calls a block, it uses the sync variant. This
avoids compile-time cross-template analysis — each template is compiled
independently, and the dispatch happens at runtime.

**Trade-off**: This means every block in an async template gets compiled twice.
The cost is negligible — block compilation is fast, and the extra code objects
are small.

### Include Across Async Boundaries

`{% include %}` currently uses `yield from included.render_stream()` in the
sync streaming path. `yield from` does not work with async generators.

**Rules**:

| Outer template | Included template | Behavior |
|---------------|-------------------|----------|
| Sync | Sync | `yield from` (unchanged) |
| Async | Sync | `yield from` sync stream (sync generators work inside async) |
| Async | Async | `async for chunk in included.render_stream_async(): yield chunk` |
| Sync | Async | **Error** — sync template cannot consume async include |

The compiler determines at include-time whether to generate `yield from`
(sync-to-sync, async-to-sync) or `async for` delegation (async-to-async).
Since `{% include %}` resolves templates by name at runtime, the dispatch
checks `template.is_async` on the loaded template.

For the sync-includes-async error case, the runtime raises:

```
TemplateRuntimeError: Sync template 'page.html' cannot include async template
'chat_widget.html'. Use render_stream_async() to render templates with async
includes.
```

### Cancellation and Cleanup

Async generators have specific cleanup semantics that matter for long-lived
streams (LLM token streams, database cursors, SSE connections).

**Problem**: A client disconnects mid-stream. The ASGI server calls `aclose()`
on the response async generator. This must propagate through kida's async
render generator to the underlying async iterable (the LLM stream, DB cursor,
etc.).

**Strategy**:

1. **`aclose()` propagation**: Python's async generator protocol already
   handles this. When `aclose()` is called on `render_stream_async()`, any
   `async for` loop inside receives `GeneratorExit`, and the underlying
   async iterable's `aclose()` is called by Python's `async for` cleanup.
   No special kida code needed — this is built into the language.

2. **`finally` blocks in templates**: If a template uses `{% try/finally %}`
   (not currently supported, and not proposed here), cleanup would be
   automatic. Since kida doesn't have try/finally in templates, cleanup
   is limited to Python's async generator protocol.

3. **RenderContext cleanup**: The `render_context()` context manager uses
   `finally` for ContextVar token reset. For async rendering, add an async
   variant `async_render_context()` that uses the same `finally` pattern
   (ContextVar reset is synchronous, so no async cleanup needed — just an
   async context manager wrapper).

4. **Timeout protection**: Consider an optional `timeout` parameter on
   `render_stream_async()` that wraps the entire render in
   `asyncio.timeout()`. This prevents a stalled async iterable from holding
   a render context open indefinitely. Default: no timeout (caller controls).

**What we get for free from Python**: `aclose()` on async generators, `async
for` cleanup of underlying iterables, `GeneratorExit` propagation. Kida does
not need to implement custom cancellation — it needs to not _block_ the
cancellation that Python already provides.

---

## Compiler Implementation Notes

### Detecting Async Templates

The compiler needs to know at compile time whether a template uses async
constructs. Strategy:

1. Walk the AST after parsing
2. If any `AsyncFor` or `Await` nodes exist, flag the template as async
3. Set `template.is_async = True` on the compiled `Template` object
4. Generate both sync and async render functions (backward compatible)
5. `render_stream()` continues to work for sync templates
6. `render_stream_async()` is available for all templates (sync templates
   get a trivial async wrapper; async templates get native async code)

### Generated Code Shape

**Current (sync stream)**:
```python
def _render_stream(ctx, _blocks):
    yield "<div>"
    _loop_items = list(ctx["items"])
    if _loop_items:
        _loop = LoopContext(_loop_items)
        for item in _loop:
            yield f"<li>{item}</li>"
    yield "</div>"
```

**Proposed (async stream)**:
```python
async def _render_stream_async(ctx, _blocks):
    yield "<div>"
    _loop = AsyncLoopContext()
    async for item in ctx["items"]:
        _loop.advance(item)
        yield f"<li>{item}</li>"
    yield "</div>"
```

Key differences:
- `async for` instead of `for item in list(...)`
- No `list()` materialization — iterates lazily over the async source
- `AsyncLoopContext` tracks index-forward variables only (no `length`,
  `revindex`, `last`)
- The `{% empty %}` clause uses a boolean flag set after the first iteration,
  checked after the loop completes

### Backward Compatibility

- `render()` and `render_stream()` continue to work unchanged
- Templates without async constructs behave identically
- `render_async()` remains available as a thread-pool wrapper for sync templates
- New methods (`render_stream_async()`, `render_block_stream_async()`) are
  additive — no breaking changes
- Calling `render()` / `render_stream()` on an async template raises a clear
  error directing the caller to the async methods

---

## Performance Expectations

| Pattern | Current | With Async Rendering |
|---------|---------|---------------------|
| AI chat (2000 tokens) | 2000 block renders, O(n^2) | 1 async stream, O(n) |
| Dashboard (3 async sections) | 3 awaits + 1 sync render | 1 async stream, sequential resolution* |
| DB cursor (10K rows) | `list()` then iterate | Async iterate, yield per batch |
| Static template | No change | No change |

*Dashboard sections render sequentially within a single template — `async for`
in section A completes before section B starts. True parallel resolution of
independent sections would require `asyncio.TaskGroup` integration at the
compiler level, which is out of scope for this RFC. Chirp-level orchestration
(rendering sections as separate blocks in parallel) remains the pattern for
concurrent dashboard rendering.

The biggest win is AI streaming: O(n^2) → O(n) for token-by-token rendering.

---

## Dependencies

- No new external dependencies
- Requires Python 3.14+ (async generators are stable since 3.6, but
  free-threading + async generators benefit from 3.14t optimizations)
- kida's compiler already generates Python AST — adding `ast.AsyncFor` and
  `ast.Await` nodes is mechanical
- New `AsyncLoopContext` class (~50 lines, mirrors `LoopContext` without
  size-dependent variables)

---

## Implementation Order

1. **AST nodes**: Add `test` field to `AsyncFor`, verify `Await` node shape
2. **Parser**: `{% async for %}` support (register `async` keyword, add
   `_parse_async_for()` with two-token lookahead)
3. **Compiler**: `_compile_async_for()` (generate `ast.AsyncFor`, register in
   dispatch table) + `_compile_await()` for `Await` nodes
4. **Runtime**: `AsyncLoopContext` with index-forward variables only
5. **Template core**: `render_stream_async()` (async generator rendering)
6. **Template core**: `render_block_stream_async()` (async block streaming)
7. **Async detect**: AST walk to flag templates as async, dual function
   generation
8. **Include async dispatch**: Runtime `is_async` check for include delegation
9. **Error paths**: Sync-render-of-async-template error, await-non-awaitable
   error, size-dependent loop variable error
10. **Tests**: Async rendering test suite (pytest-asyncio already in dev deps)
11. **Chirp integration**: Update `Stream()` negotiation to use async stream

**Estimated scope**: ~800-1200 lines of new code across parser, compiler,
template core, and runtime. The sync streaming infrastructure is the blueprint,
but async-specific concerns (loop variables, inheritance taint, include
dispatch, error model) add scope beyond a mechanical port.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Complexity of async compiler output | Follow existing sync stream pattern; `ast.AsyncFor` mirrors `ast.For` |
| Performance regression for sync templates | New methods are additive; sync path is completely unchanged |
| Testing async generators | kida already has pytest-asyncio in dev deps |
| Compile-time detection of async | Simple AST walk post-parse, not type inference |
| Inheritance taint (child async → parent must handle) | Runtime dispatch: check for async block variant, fall back to sync |
| Include across async boundaries | Runtime `is_async` check; sync-includes-async raises clear error |
| `loop.length`/`loop.last` in async loops | Reduced `AsyncLoopContext`; clear error for unsupported variables |
| `{{ await }}` on non-awaitable | Runtime `TypeError` caught and re-raised as `TemplateRuntimeError` with context |
| Stalled async iterable holds render open | Optional `timeout` parameter on `render_stream_async()` |
| `aclose()` not propagating on disconnect | No custom code needed — Python's async generator protocol handles this |

---

## Open Questions

1. **Should `render_stream_async()` be available on sync templates?** A thin
   async wrapper (`async for chunk in sync_stream: yield chunk`) would let
   callers use a single code path. Trade-off: slight overhead vs API
   simplicity. **Leaning yes.**

2. **Should we support `{% async for ... if test %}`?** The `test` field is
   proposed for `AsyncFor`, but it adds parser complexity. The same result is
   achievable with `{% if %}` inside the loop body. **Leaning yes** — it's a
   one-line compiler change and matches sync `for` parity.

3. **Future: `asyncio.TaskGroup` for parallel blocks?** A `{% parallel %}`
   construct could render independent blocks concurrently. This is explicitly
   out of scope but worth noting as a future direction.

---

## Decision

**Defer until after chirp.data/chirp.ai launch.** The current pattern
(chirp-level orchestration with `render_block()`) is correct and works
today. Native async rendering is an optimization that eliminates the O(n^2)
re-rendering pattern for AI streaming. Ship the framework integration first,
validate the patterns with real usage, then optimize the engine.

**Priority**: After chirp 0.2.0 (data + AI launch). Target kida 0.2.0.
