# RFC: `{% flush %}` Directive for Streaming

**Status**: ✅ Implemented  
**Created**: 2026-03-02  
**Minimum Python**: 3.14

---

## Executive Summary

Add a `{% flush %}` directive that creates an explicit yield boundary in streaming mode. This enables shell-first streaming: send header/nav immediately, then stream content as it becomes available. In non-streaming mode (`render()`), flush is a no-op.

---

## Motivation

### Current Behavior

Kida's `render_stream()` yields chunks at statement boundaries. Each `{{ expr }}`, `{% for %}` iteration, and control-flow branch produces a chunk. Buffering constructs (`{% capture %}`, `{% spaceless %}`, `{% cache %}`) collect output internally and yield the processed result.

### The Gap

When a template has:

```kida
<header>...</header>
<nav>...</nav>
<main>
  {% for item in expensive_db_query() %}
    <div>{{ item }}</div>
  {% end %}
</main>
```

The client receives chunks as they're produced. But if `expensive_db_query()` blocks for 2 seconds before returning, the client waits for the first `<main>` content. There's no way to say "send header + nav now, before the loop."

### Use Cases

1. **Shell-first streaming** — Send layout (header, nav) immediately; stream main content as data arrives
2. **Inside buffering constructs** — N/A: flush inside `{% capture %}`/`{% spaceless %}`/`{% cache %}` compiles in non-streaming context → no-op (correct)
3. **Explicit boundaries** — Force a chunk boundary where coalescing might otherwise batch adjacent output

---

## Proposed Design

### Syntax

```kida
{% flush %}
```

- Self-closing (no body, no `{% end %}`)
- No arguments

### Semantics

| Mode | Behavior |
|------|----------|
| `render()` (StringBuilder) | No-op |
| `render_stream()` | `yield ""` — creates a chunk boundary |
| `render_stream_async()` | `yield ""` — same |

### Compiler Output

**Streaming mode** (`_streaming=True`):

```python
# {% flush %}
yield ""
```

**Non-streaming mode** (`_streaming=False`):

```python
# {% flush %}
# (nothing — no statement generated)
```

---

## Implementation Plan

### 1. AST Node

**File**: `src/kida/nodes/output.py` (or new `structure.py` entry)

```python
@dataclass(frozen=True, slots=True)
class Flush(Node):
    """Streaming flush boundary: {% flush %}"""
```

- No attributes beyond `lineno`, `col_offset` (inherited from Node)
- Re-export in `kida/nodes/__init__.py`

### 2. Parser

**File**: `src/kida/parser/statements.py`

- Add `"flush": "_parse_flush"` to `_BLOCK_PARSERS`

**File**: `src/kida/parser/blocks/special_blocks.py`

- Add `_parse_flush(self) -> Flush`:
  - Consume `flush` token
  - Expect `BLOCK_END`
  - Return `Flush(lineno=..., col_offset=...)`
  - No block stack (self-closing)

### 3. Compiler

**File**: `src/kida/compiler/core.py`

- Add `"Flush": self._compile_flush` to `_get_node_dispatch()`

**File**: `src/kida/compiler/statements/special_blocks.py` (or `basic.py`)

- Add `_compile_flush(self, node: Flush) -> list[ast.stmt]`:
  - If `self._streaming`: return `[ast.Expr(value=ast.Yield(value=ast.Constant(value="")))]`
  - Else: return `[]`

### 4. Analysis (if applicable)

- **Purity**: Flush has no side effects on template logic; analysis can ignore or treat as pure
- **Block recompile**: Flush is not a block; no changes needed

### 5. Tests

**File**: `tests/test_flush.py` (or add to existing streaming tests)

- `test_flush_noop_in_render` — `render()` with `{% flush %}` produces same output as without
- `test_flush_yields_in_stream` — `render_stream()` yields extra chunk at flush position
- `test_flush_yields_in_stream_async` — same for async
- `test_flush_inside_capture` — flush inside `{% capture %}` is no-op (body compiled non-streaming)
- `test_flush_shell_first` — integration: header/nav before slow loop; verify chunk order

### 6. Documentation

**File**: `site/content/docs/usage/streaming.md`

- Add "Flush boundaries" section
- Example: shell-first pattern with `{% flush %}` before `{% for item in expensive_query() %}`

**File**: `site/content/docs/syntax/control-flow.md` or new `streaming.md`

- Document `{% flush %}` in syntax reference

### 7. Example

**File**: `examples/streaming/` or new `examples/flush/`

- Extend streaming example with flush demo
- Or add `examples/shell_first/` showing header → flush → slow content

---

## Edge Cases

| Case | Behavior |
|------|----------|
| `{% flush %}` in `render()` | No-op |
| `{% flush %}` in `render_stream()` | Yields `""` |
| `{% flush %}` inside `{% capture %}` | No-op (body not streaming) |
| `{% flush %}` inside `{% spaceless %}` | No-op |
| `{% flush %}` inside `{% cache %}` | No-op |
| `{% flush %}` in block (extends) | Same as top-level — block body is compiled with streaming when generating `_block_*_stream` |
| Multiple consecutive `{% flush %}` | Each yields `""` — valid, creates multiple boundaries |

---

## Alternatives Considered

### 1. `yield` with accumulated content

Instead of `yield ""`, flush could yield `"".join(buf)` to force-send buffered output. Kida's streaming doesn't buffer — each statement yields immediately. So there's nothing to "flush" except creating a boundary. Rejected.

### 2. Flush only in streaming mode — parse error otherwise

Could raise a parse error if `{% flush %}` appears in a template that's only ever used with `render()`. Overly restrictive; no-op is harmless. Rejected.

### 3. `{% flush "optional-label" %}`

Allow an optional label for debugging. Adds complexity; not needed for MVP. Can extend later. Deferred.

---

## Checklist

- [ ] Add `Flush` node
- [ ] Parser: `_parse_flush`, dispatch entry
- [ ] Compiler: `_compile_flush`, dispatch entry
- [ ] Tests: render no-op, stream yield, async yield, inside capture
- [ ] Docs: streaming.md, syntax reference
- [ ] Example: shell-first or extend streaming example

---

## References

- templ `templ.Flush()`: https://templ.guide/server-side-rendering/streaming/
- Kida streaming: `site/content/docs/usage/streaming.md`
- Kida compiler: `src/kida/compiler/core.py`, `_emit_output`
- Kida special blocks: `src/kida/compiler/statements/special_blocks.py`
