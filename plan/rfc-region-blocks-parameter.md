# RFC: Region `_blocks` Parameter

**Status:** Implemented  
**Date:** 2025-03

## Summary

Region callables must receive `_blocks` so that `{% block %}` dispatch inside region bodies works correctly with template inheritance. Without `_blocks`, child template block overrides are not dispatched when the region is invoked from a parent block.

## Root Cause

Region callables were defined with only `_outer_ctx` as a kw-only parameter. Block wrappers and expression call sites forwarded `_outer_ctx` but not `_blocks`. When a region body contains `{% block name %}`, dispatch to `_blocks["name"]` failed because `_blocks` was never passed.

## Gaps Addressed

### Gap 1: Streaming Block Wrappers

`_make_region_block_function_stream` built the same call pattern as the non-streaming wrapper — forwarding `_outer_ctx` but not `_blocks`. The async variant delegates to the sync version, so fixing sync fixes async.

### Gap 2: `{% def %}` Guard in Expression Calls

The expression call site unconditionally emitted `_blocks=_blocks` when the target is a Region. Calling a region from inside a `{% def %}` body — where `_blocks` is NOT in scope — would produce `NameError`. Mitigation: check `self._def_caller_stack`; if non-empty, pass `_blocks={}`.

## Files Modified

| File | Method | Change |
|------|--------|--------|
| `compiler/statements/functions.py` | `_make_region_function` | Add `_blocks` to `kwonlyargs` |
| `compiler/core.py` | `_make_region_block_function` | Forward `_blocks` keyword |
| `compiler/core.py` | `_make_region_block_function_stream` | Forward `_blocks` keyword |
| `compiler/expressions.py` | `_compile_Call` | Add `_blocks` keyword with def-context guard |

## Implementation

1. **Region signature** — `kwonlyargs=[_outer_ctx, _blocks]`, `kw_defaults=[None, None]`
2. **StringBuilder block wrapper** — `keywords.append(ast.keyword(arg="_blocks", value=ast.Name(id="_blocks", ...)))`
3. **Streaming block wrapper** — Same keyword append
4. **Expression call site** — `blocks_value = ast.Dict(keys=[], values=[]) if self._def_caller_stack else ast.Name(id="_blocks", ...)`

## Regression Tests

- `test_region_with_block_and_child_override` — Region body with `{% block %}` receives `_blocks`; child override with `{% let %}` renders correctly
- `test_region_with_block_streaming` — Block wrapper forwards `_blocks` (via `render_block`; full `render_stream` with region+blocks needs separate RFC for yield-from semantics)

## Deferred

- **Task 8:** Re-enable explorer layout in Bengal `endpoint.html` (optional, separate PR)
