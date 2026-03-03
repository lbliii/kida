# Error Attribution Follow-Up Investigation

Investigation date: 2025-03-03

## 1. `UndefinedError.template_stack` Empty When Caught

### Finding: **Bug confirmed — root cause identified**

When an error occurs inside an imported macro, `error.template_stack` is empty when the exception is caught, even though the formatted error message correctly shows "Template stack: • caller.html:2".

### Root Cause

**Shared mutable reference + `finally` block mutation:**

1. `lookup()` / `lookup_scope()` pass `template_stack=render_ctx.template_stack` to `UndefinedError`.
2. `UndefinedError` stores `self.template_stack = template_stack or []` — a **reference** to the same list.
3. The exception message is built in `__init__` via `_format_message()`, which reads the list (at that moment it has 1 element).
4. The exception propagates out of the macro.
5. The macro wrapper's `finally` block runs: `render_ctx.template_stack.pop()`.
6. That mutates the **same list** the exception holds a reference to.
7. By the time the caller catches the exception, the list is empty.

### Fix

Pass a **copy** when raising `UndefinedError` so the exception's stack is not mutated:

```python
# In helpers.py lookup() and lookup_scope()
template_stack = list(render_ctx.template_stack) if render_ctx else []
```

**Files to change:** `kida/src/kida/template/helpers.py` (lines 165, 199)

---

## 2. `?[key]` Syntax for Safe Subscript

### Finding: **Supported — suggestion is correct**

Kida supports optional subscript `obj?[key]` (RFC: kida-modern-syntax-features):

- Parser: `src/kida/parser/expressions.py` (line 436) — "Optional subscript: obj?[key]"
- Compiler: `src/kida/compiler/expressions.py` (line 556) — compiles `obj?[key]`
- Analysis: `src/kida/analysis/dependencies.py` (line 236) — "Handle optional subscript access"
- Tests: `tests/analysis/test_analysis_coverage.py` — `{{ data?["key"] }}`

The KeyError suggestion "Use `.get('X')` or `?[X]` for safe access" is accurate.

---

## 3. Source Snippet for Macro Errors

### Finding: **No wrong snippet — but no snippet at all**

When an error occurs inside an imported macro:

- **Location:** Correctly reports `lib.html` (macro source).
- **Template stack:** Correctly shows `caller.html:1` in the formatted message.
- **Source snippet:** **None** — no snippet is shown.

### Why No Snippet

1. The macro wrapper sets `render_ctx.line = 0` when entering the macro.
2. `lookup()` uses `snippet = build_source_snippet(source, lineno) if source and lineno else None`.
3. `lineno` is 0 (falsy), so `snippet = None`.
4. `render_ctx.source` is the **caller's** source (never updated when entering the macro).

So we avoid showing the wrong template's content, but we also don't show the macro's source. The macro template's source is not loaded into `render_ctx` when the macro runs.

### Potential Enhancement

To show the correct snippet for macro errors:

1. In `_make_macro_wrapper`, load the macro template's source (e.g. from `Environment.get_template()` which has `_source`).
2. Set `render_ctx.source` to the macro's source when entering the macro.
3. Ensure the macro's generated code updates `render_ctx.line` as it executes (it likely already does via `_get_render_ctx().line = X`).
4. Restore `render_ctx.source` in the `finally` block.

This requires passing the imported `Template` (or its source) into the wrapper, which adds some complexity.

**Note:** `MacroWrapper` (refactored from function-with-attributes) now holds `_kida_source_template`, `_kida_source_file`, and `_source` as typed fields. When catching exceptions from macro calls, these attributes can be used to enhance error messages with the correct source location.

---

## Summary

| Item                         | Status   | Action                                      |
|-----------------------------|----------|---------------------------------------------|
| `template_stack` empty      | Bug      | Pass `list(render_ctx.template_stack)`      |
| `?[key]` suggestion         | Correct  | None                                        |
| Source snippet in macros    | Missing  | Optional: load macro source in wrapper      |
