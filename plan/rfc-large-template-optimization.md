# RFC: Large Template Rendering Optimization

**Status**: Implemented (Phase 1 & 2)  
**Created**: 2026-01-12  
**Updated**: 2026-01-12  
**Authors**: @llane  

## Summary

Improve Kida's large template rendering performance through type-aware escaping and lazy LoopContext optimization.

## Problem

Kida was only ~9% faster than Jinja2 for large templates (1000+ loop iterations). Benchmark analysis revealed three optimization opportunities:

| Bottleneck | Impact | Effort | Status |
|------------|--------|--------|--------|
| Type-aware escaping | **1.9x** | Low | ✅ Implemented |
| Lazy LoopContext | **1.80x** | Low | ✅ Implemented |
| f-string code generation | 1.37x | Medium | Deferred |

## Benchmark Evidence

From `benchmarks/test_benchmark_optimization_levers.py`:

```
lever:escaping
  test_escape_smart_numbers:  496µs (2.5x faster)
  test_escape_all:          1,242µs (baseline)

lever:string-building
  test_fstring_generator:     211µs (1.37x faster)
  test_list_append:           288µs (baseline)

lever:loop-context
  test_direct_iteration:      133µs (1.16x faster)
  test_full_loop_context:     155µs (baseline)

lever:combined
  test_optimized_combined:    328µs (1.67x faster)
  test_current_kida_style:    548µs (baseline)
```

## Proposed Changes

### Phase 1: Type-Aware Escaping (Highest Impact)

**File**: `src/kida/utils/html.py`

```python
# Safe types that cannot contain HTML special characters
_SAFE_TYPES = (int, float, bool)

def html_escape(value: Any) -> str:
    """O(n) single-pass HTML escaping with type optimization."""
    # Skip Markup objects - already safe
    if isinstance(value, Markup):
        return str(value)

    # Skip numeric types - cannot contain <>&"'
    if isinstance(value, _SAFE_TYPES):
        return str(value)

    s = str(value)
    return _escape_str(s)
```

**Risk**: Low. Numbers cannot contain `<`, `>`, `&`, `"`, `'`.

**Expected Impact**: 2.0-2.5x faster for number-heavy templates.

### Phase 2: Lazy LoopContext (Low Effort)

**File**: `src/kida/compiler/statements/control_flow.py`

When compiling `{% for %}`, analyze if `loop.*` properties are used:

```python
def _compile_for(self, node: Any) -> list[ast.stmt]:
    # Check if loop.* is referenced in body
    uses_loop_props = self._uses_loop_properties(node.body)

    if uses_loop_props:
        # Full LoopContext (current behavior)
        # loop = _LoopContext(_loop_items)
        # for item in loop: ...
    else:
        # Direct iteration (16% faster)
        # for item in _loop_items: ...
```

**Risk**: Low. Pure optimization, no semantic change.

**Expected Impact**: 10-16% faster for loops not using `loop.*`.

### Phase 3: F-String Code Generation (Medium Effort)

**File**: `src/kida/compiler/statements/basic.py`

When consecutive outputs are all simple expressions (no filters, no conditionals), generate a single f-string:

```python
# Current generated code (multiple appends)
_append('<div id="')
_append(_e(item["id"]))
_append('">')
_append(_e(item["name"]))
_append("</div>\n")

# Optimized generated code (single f-string)
_append(f'<div id="{_e(item["id"])}">{_e(item["name"])}</div>\n')
```

**Risk**: Medium. Requires careful AST analysis.

**Expected Impact**: 30-37% faster for output-heavy templates.

## Implementation Plan

### Phase 1: Type-Aware Escaping (This PR)

1. Update `html_escape()` in `src/kida/utils/html.py`
2. Add tests for numeric type optimization
3. Run benchmarks to verify improvement
4. Update documentation

**Estimated Time**: 1 hour

### Phase 2: Lazy LoopContext

1. Add `_uses_loop_properties()` analysis in compiler
2. Generate direct iteration when safe
3. Add tests for both paths
4. Benchmark verification

**Estimated Time**: 2-3 hours

### Phase 3: F-String Generation

1. Add output coalescing analysis in compiler
2. Generate f-strings for consecutive simple outputs
3. Ensure correct escaping in f-string context
4. Add comprehensive tests
5. Benchmark verification

**Estimated Time**: 4-6 hours

## Results

### Implemented Optimizations

**Type-aware escaping** (`src/kida/utils/html.py`):
- Numeric types (int, float, bool) bypass `.translate()` since they can't contain HTML chars
- **Result**: 1.9x faster for numeric values

**Lazy LoopContext** (`src/kida/compiler/statements/control_flow.py`):
- When `loop.*` properties aren't used, iterate directly over items
- Skips `_LoopContext` wrapper creation and property tracking
- **Result**: 1.80x faster for loops without `loop.*`

### Benchmark Results

| Template Type | Before | After | Improvement |
|--------------|--------|-------|-------------|
| Numeric-heavy (10k ints) | 1.74ms | 0.90ms | **1.9x** |
| Loop without `loop.*` (10k items) | 365.7ms | 202.7ms | **1.80x** |
| Large template (1000 items) | ~2.5ms | ~2.3ms | ~1.09x |

The large template improvement is modest because:
- Only ~75% of values are numeric (3 of 4 interpolations)
- Most time is spent in Python iteration, not escaping/LoopContext

## Success Criteria

| Metric | Before | After | Target | Status |
|--------|--------|-------|--------|--------|
| Type-aware escape overhead | 1.74ms | 0.90ms | <1.0ms | ✅ Met |
| Loop without `loop.*` | 365.7ms | 202.7ms | <250ms | ✅ Met |
| Large template render | ~2.5ms | ~2.3ms | <1.5ms | ❌ Not met |

The large template target was not met because the bottleneck is Python iteration overhead, not escaping or LoopContext. Further optimization would require f-string code generation (Phase 3).

## Risks and Mitigations

### Type-Aware Escaping

**Risk**: Custom `__str__` methods on numeric subclasses could return HTML.

**Mitigation**: Use `type(value) in _SAFE_TYPES` instead of `isinstance()` to exclude subclasses that might override `__str__`.

### Lazy LoopContext

**Risk**: False negative detection (missing `loop.` usage).

**Mitigation**: Conservative analysis - if uncertain, use full LoopContext.

### F-String Generation

**Risk**: Incorrect escaping or broken semantics.

**Mitigation**:
- Extensive test coverage
- Only optimize simple cases initially
- Add debug mode to show generated code

## Alternatives Considered

### StringIO Buffering

Tested: **35% slower** than list.append. Rejected.

### Pre-allocated Lists

Would require knowing output size in advance. Not practical for dynamic templates.

### Cython/Extension Module

Would improve performance but breaks pure-Python goal. Rejected for now.

## Changelog

- 2026-01-12: Initial draft based on benchmark analysis
