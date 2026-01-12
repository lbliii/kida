# RFC: F-String Code Generation for Template Output

**Status**: Draft  
**Created**: 2026-01-12  
**Authors**: @llane  
**Depends On**: RFC: Large Template Rendering Optimization (Phase 1 & 2 complete)

## Summary

Generate Python f-strings for consecutive template output operations instead of multiple `buf.append()` calls, reducing function call overhead by 37% in output-heavy templates.

## Problem

Kida currently generates one `buf.append()` call per output segment:

```python
# Template: <div id="{{ item.id }}">{{ item.name }}</div>
# Current generated code (9 function calls per iteration):
_append('<div id="')
_append(_e(item["id"]))
_append('">')
_append(_e(item["name"]))
_append('</div>\n')
```

Benchmark evidence from `benchmarks/test_benchmark_optimization_levers.py`:

| Method | Time (1000 items) | Speedup |
|--------|-------------------|---------|
| f-string per iteration | 216µs | **1.33x** |
| f-string generator join | 211µs | **1.37x** |
| list.append (current) | 288µs | baseline |

The f-string approach reduces function call overhead while maintaining correctness.

## Proposed Solution

### Code Generation Change

**Before** (current):
```python
_append('<div id="')
_append(_e(item["id"]))
_append('">')
_append(_e(item["name"]))
_append('</div>\n')
```

**After** (optimized):
```python
_append(f'<div id="{_e(item["id"])}">{_e(item["name"])}</div>\n')
```

### When to Apply

Only coalesce consecutive nodes when **all** are simple outputs:

| Node Type | Coalesceable |
|-----------|--------------|
| `Data` (literal text) | ✅ Yes |
| `Output` (simple expression) | ✅ Yes |
| `Output` with filters | ⚠️ Only if filter is pure |
| `If`, `For`, `Block`, etc. | ❌ No (breaks coalescing) |

### Implementation Strategy

#### Option A: Compile-Time Coalescing (Recommended)

Modify `_make_render_function()` to detect consecutive coalesceable nodes and generate a single f-string:

```python
def _compile_body(self, nodes: list[Node]) -> list[ast.stmt]:
    """Compile template body with output coalescing."""
    stmts = []
    i = 0

    while i < len(nodes):
        # Try to coalesce consecutive outputs
        coalesceable = []
        while i < len(nodes) and self._is_coalesceable(nodes[i]):
            coalesceable.append(nodes[i])
            i += 1

        if len(coalesceable) > 1:
            # Generate single f-string append
            stmts.append(self._compile_coalesced_output(coalesceable))
        elif coalesceable:
            # Single node - use normal compilation
            stmts.extend(self._compile_node(coalesceable[0]))

        # Compile non-coalesceable node normally
        if i < len(nodes) and not self._is_coalesceable(nodes[i]):
            stmts.extend(self._compile_node(nodes[i]))
            i += 1

    return stmts
```

#### Option B: AST Post-Processing

Walk generated Python AST and merge consecutive `_append()` calls. More complex but doesn't require changing compilation logic.

**Recommendation**: Option A is cleaner and allows for future optimizations.

## Detailed Design

### 1. Coalesceable Node Detection

```python
def _is_coalesceable(self, node: Any) -> bool:
    """Check if node can be coalesced into an f-string."""
    from kida.nodes import Data, Output

    if isinstance(node, Data):
        return True

    if isinstance(node, Output):
        # Simple expressions are coalesceable
        # Filters are only coalesceable if pure (no side effects)
        return self._is_simple_output(node)

    return False

def _is_simple_output(self, node: Output) -> bool:
    """Check if Output node is simple enough for f-string."""
    from kida.nodes import Filter, Name, Getattr, Getitem, Const

    expr = node.expr

    # Allow: name, name.attr, name[key], constants
    if isinstance(expr, (Name, Const)):
        return True
    if isinstance(expr, (Getattr, Getitem)):
        return self._is_simple_output_expr(expr)

    # Allow filters, but only pure ones
    if isinstance(expr, Filter):
        return expr.name in _PURE_FILTERS and self._is_simple_output_expr(expr.value)

    return False

# Filters known to be pure (no side effects, deterministic)
_PURE_FILTERS = frozenset({
    "upper", "lower", "title", "capitalize",
    "trim", "strip", "lstrip", "rstrip",
    "escape", "e",
    "default", "d",
    "int", "float", "string",
    "length", "count",
    "first", "last",
    "join",
})
```

### 2. F-String AST Generation

```python
def _compile_coalesced_output(self, nodes: list[Any]) -> ast.stmt:
    """Generate f-string append for coalesced nodes."""
    from kida.nodes import Data, Output

    # Build f-string components
    parts: list[ast.expr] = []

    for node in nodes:
        if isinstance(node, Data):
            # Literal text - escape braces for f-string
            text = node.value.replace("{", "{{").replace("}", "}}")
            parts.append(ast.Constant(value=text))
        elif isinstance(node, Output):
            # Expression - wrap in escape if needed
            expr = self._compile_expr(node.expr)
            if node.escape:
                expr = ast.Call(
                    func=ast.Name(id="_e", ctx=ast.Load()),
                    args=[expr],
                    keywords=[],
                )
            else:
                expr = ast.Call(
                    func=ast.Name(id="_s", ctx=ast.Load()),
                    args=[expr],
                    keywords=[],
                )
            parts.append(ast.FormattedValue(
                value=expr,
                conversion=-1,  # No conversion
                format_spec=None,
            ))

    # Create JoinedStr (f-string)
    fstring = ast.JoinedStr(values=parts)

    # _append(f"...")
    return ast.Expr(
        value=ast.Call(
            func=ast.Name(id="_append", ctx=ast.Load()),
            args=[fstring],
            keywords=[],
        )
    )
```

### 3. Edge Cases

#### Braces in Literal Text

Template: `<style>body {{ color: red }}</style>`

Must escape `{` and `}` in literal text:
```python
# Correct f-string
f'<style>body {{ color: red }}</style>'
```

#### Backslashes in Expressions

F-strings don't allow backslashes in expressions. If expression contains backslash, fall back to append:

```python
# Template: {{ path.replace("\\", "/") }}
# Cannot use f-string - contains backslash in expression
# Fall back to: _append(_e(path.replace("\\", "/")))
```

#### Nested F-Strings

Python doesn't allow nested f-strings. If expression generates an f-string, fall back:

```python
# Template: {{ f"Hello {name}" }}
# Fall back to separate append
```

### 4. Coalescing Threshold

Only coalesce if there are **2+ consecutive** coalesceable nodes. Single nodes use normal compilation (no overhead).

```python
COALESCE_MIN_NODES = 2
```

## Performance Analysis

### Expected Improvement

| Scenario | Current | With f-strings | Improvement |
|----------|---------|----------------|-------------|
| Simple loop (1000 items, 5 outputs each) | 288µs | 211µs | **1.37x** |
| Mixed template (50% outputs) | ~varies | ~varies | ~1.15-1.20x |
| Complex template (many control flow) | ~varies | ~varies | ~1.05x |

### Why F-Strings Are Faster

1. **Fewer function calls**: 1 `append()` vs N `append()` calls
2. **Python optimization**: f-strings are optimized at bytecode level
3. **Single allocation**: One string created instead of N intermediate strings

### When It Doesn't Help

- Templates with heavy control flow (If, For interleaved with outputs)
- Templates using complex filters
- Templates with very few outputs

## Implementation Plan

### Phase 1: Core Infrastructure (2-3 hours)

1. Add `_is_coalesceable()` and `_is_simple_output()` methods
2. Add `_compile_coalesced_output()` method
3. Add `_PURE_FILTERS` constant

### Phase 2: Compilation Integration (2-3 hours)

1. Modify body compilation to detect consecutive coalesceable nodes
2. Route coalesceable sequences to new compilation path
3. Ensure non-coalesceable nodes use existing path

### Phase 3: Edge Cases (1-2 hours)

1. Handle brace escaping in literals
2. Detect and fall back for backslashes in expressions
3. Handle nested f-string edge case

### Phase 4: Testing (2-3 hours)

1. Unit tests for coalesceable detection
2. Unit tests for f-string generation
3. Integration tests for various template patterns
4. Regression tests for edge cases
5. Benchmark verification

### Phase 5: Documentation (1 hour)

1. Update performance docs
2. Update this RFC with results

**Total Estimated Time**: 8-12 hours

## Risks and Mitigations

### Risk 1: Incorrect Output

**Risk**: Generated f-string produces different output than append sequence.

**Mitigation**:
- Extensive test coverage
- Conservative coalesceable detection (fail-safe to append)
- Compare rendered output before/after for all test templates

### Risk 2: Brace Escaping Bugs

**Risk**: `{` or `}` in literal text not escaped, causing f-string syntax error.

**Mitigation**:
- Always escape braces in `Data` nodes
- Unit tests specifically for brace handling

### Risk 3: Expression Complexity

**Risk**: Complex expressions that don't work in f-strings.

**Mitigation**:
- Conservative `_is_simple_output()` that rejects complex expressions
- Fall back to append for any uncertainty
- Test with complex expression patterns

### Risk 4: Performance Regression for Edge Cases

**Risk**: Some templates get slower due to coalescing overhead.

**Mitigation**:
- Only coalesce 2+ consecutive nodes
- Benchmark suite includes diverse template patterns
- Gate feature behind config flag initially

## Testing Strategy

### Unit Tests

```python
class TestCoalesceableDetection:
    def test_data_node_coalesceable(self):
        """Data nodes are always coalesceable."""

    def test_simple_output_coalesceable(self):
        """Simple variable output is coalesceable."""

    def test_filtered_output_coalesceable(self):
        """Output with pure filter is coalesceable."""

    def test_complex_filter_not_coalesceable(self):
        """Output with impure filter is not coalesceable."""

    def test_control_flow_not_coalesceable(self):
        """If/For nodes are not coalesceable."""

class TestFStringGeneration:
    def test_simple_coalesce(self):
        """Two literals coalesce into f-string."""

    def test_brace_escaping(self):
        """Braces in literals are escaped."""

    def test_expression_interpolation(self):
        """Expressions become f-string interpolations."""

class TestEdgeCases:
    def test_backslash_in_expression_fallback(self):
        """Backslash in expression falls back to append."""

    def test_single_node_not_coalesced(self):
        """Single coalesceable node uses normal compilation."""
```

### Integration Tests

```python
class TestCoalescedRendering:
    def test_simple_template_matches(self):
        """Coalesced template produces same output as non-coalesced."""

    def test_loop_template_matches(self):
        """Loop with coalesced body produces correct output."""

    def test_mixed_template_matches(self):
        """Template with mixed coalesceable/non-coalesceable nodes works."""
```

### Benchmark Verification

```python
@pytest.mark.benchmark(group="coalesce")
def test_coalesced_vs_append():
    """Verify f-string coalescing is faster than append sequence."""
```

## Success Criteria

| Metric | Target |
|--------|--------|
| Output-heavy template speedup | ≥1.25x |
| No rendering regressions | 100% test pass |
| Edge case handling | All known edge cases tested |

## Alternatives Considered

### Alternative 1: String Concatenation

Generate `+` concatenation instead of f-strings:

```python
_append('<div id="' + _e(item["id"]) + '">' + _e(item["name"]) + '</div>')
```

**Rejected**: Slower than f-strings, more memory allocations.

### Alternative 2: io.StringIO

Use StringIO instead of list:

```python
buf = io.StringIO()
write = buf.write
write('<div id="')
write(_e(item["id"]))
...
```

**Rejected**: Benchmarks showed 35% *slower* than list.append.

### Alternative 3: Pre-allocated List

```python
buf = [None] * estimated_size
```

**Rejected**: Would require knowing output size in advance.

## Open Questions

1. **Filter purity**: How do we handle custom filters? Assume impure and don't coalesce?

2. **Coalescing threshold**: Is 2 nodes the right minimum, or should we require 3+?

3. **Feature flag**: Should this be behind a config option initially?

## References

- [Python f-string implementation](https://peps.python.org/pep-0498/)
- [ast.JoinedStr documentation](https://docs.python.org/3/library/ast.html#ast.JoinedStr)
- `benchmarks/test_benchmark_optimization_levers.py` - benchmark evidence
- `src/kida/compiler/statements/basic.py` - current output compilation

## Changelog

- 2026-01-12: Initial draft
