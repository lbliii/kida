# RFC: F-String Code Generation for Template Output

**Status**: Implemented  
**Created**: 2026-01-12  
**Updated**: 2026-01-12  
**Authors**: @llane  
**Depends On**: RFC: Large Template Rendering Optimization (Phase 1 & 2 complete)

## Summary

Generate Python f-strings for consecutive template output operations instead of multiple `buf.append()` calls, reducing function call overhead by 37% in output-heavy templates.

## Problem

Kida currently generates one `buf.append()` call per output segment:

```python
# Template: <div id="{{ item.id }}">{{ item.name }}</div>
# Current generated code (5 function calls per iteration):
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
| `Output` with pure filters | ✅ Yes (if args are simple) |
| `Output` with Pipeline | ✅ Yes (if all steps are pure) |
| `Output` with impure/custom filters | ❌ No |
| `If`, `For`, `Block`, etc. | ❌ No (breaks coalescing) |

### Configuration

```python
@dataclass
class Environment:
    # ... existing fields ...
    
    # F-string optimization (default: enabled)
    fstring_coalescing: bool = True
    
    # User-defined pure filters (extends built-in set)
    pure_filters: set[str] = field(default_factory=set)
```

### Implementation Strategy

#### Option A: Compile-Time Coalescing (Recommended)

Modify `_make_render_function()` to detect consecutive coalesceable nodes and generate a single f-string:

```python
def _compile_body(self, nodes: list[Node]) -> list[ast.stmt]:
    """Compile template body with output coalescing."""
    # Skip if optimization disabled
    if not self._env.fstring_coalescing:
        return [stmt for node in nodes for stmt in self._compile_node(node)]
    
    stmts = []
    i = 0

    while i < len(nodes):
        # Try to coalesce consecutive outputs
        coalesceable = []
        while i < len(nodes) and self._is_coalesceable(nodes[i]):
            coalesceable.append(nodes[i])
            i += 1

        if len(coalesceable) >= COALESCE_MIN_NODES:
            # Generate single f-string append
            stmts.append(self._compile_coalesced_output(coalesceable))
        elif coalesceable:
            # Single node - use normal compilation
            for node in coalesceable:
                stmts.extend(self._compile_node(node))

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
# Coalescing threshold - minimum nodes to trigger f-string generation
COALESCE_MIN_NODES = 2

# Built-in filters known to be pure (no side effects, deterministic)
_BUILTIN_PURE_FILTERS: frozenset[str] = frozenset({
    # String case transformations
    "upper", "lower", "title", "capitalize", "swapcase",
    # Whitespace handling
    "trim", "strip", "lstrip", "rstrip",
    # HTML escaping
    "escape", "e", "forceescape",
    # Default values
    "default", "d",
    # Type conversion
    "int", "float", "string", "str", "bool",
    # Collection info
    "length", "count",
    # Collection access
    "first", "last",
    # String operations
    "join", "center", "ljust", "rjust",
    # Formatting
    "truncate", "wordwrap", "indent",
    # URL encoding
    "urlencode",
})


def _get_pure_filters(self) -> frozenset[str]:
    """Get combined set of built-in and user-defined pure filters."""
    if self._env.pure_filters:
        return _BUILTIN_PURE_FILTERS | frozenset(self._env.pure_filters)
    return _BUILTIN_PURE_FILTERS


def _is_coalesceable(self, node: Any) -> bool:
    """Check if node can be coalesced into an f-string."""
    from kida.nodes import Data, Output

    if isinstance(node, Data):
        # Data nodes with backslashes in braces context need special handling
        # but are still coalesceable - escaping handled in generation
        return True

    if isinstance(node, Output):
        return self._is_simple_output(node)

    return False


def _is_simple_output(self, node: Output) -> bool:
    """Check if Output node is simple enough for f-string."""
    return self._is_simple_expr(node.expr)


def _is_simple_expr(self, expr: Any) -> bool:
    """Recursively check if expression is simple enough for f-string.
    
    Simple expressions:
    - Constants (strings, numbers, booleans)
    - Names (variable references)
    - Attribute access (name.attr, name.attr.subattr)
    - Item access (name[key], name["key"])
    - Pure filters with simple arguments
    - Pipelines with all pure steps
    """
    from kida.nodes import (
        Const, Name, Getattr, Getitem, 
        Filter, Pipeline, FuncCall,
    )

    # Base cases: constants and names are always simple
    if isinstance(expr, Const):
        return True
    
    if isinstance(expr, Name):
        return True

    # Attribute access: check base is simple
    if isinstance(expr, Getattr):
        return self._is_simple_expr(expr.value)

    # Item access: check both base and key are simple
    if isinstance(expr, Getitem):
        return (
            self._is_simple_expr(expr.value) and 
            self._is_simple_expr(expr.key)
        )

    # Filter: check filter is pure AND value/args are simple
    if isinstance(expr, Filter):
        pure_filters = self._get_pure_filters()
        if expr.name not in pure_filters:
            return False
        # Check the filtered value is simple
        if not self._is_simple_expr(expr.value):
            return False
        # Check all positional args are simple
        if not all(self._is_simple_expr(arg) for arg in expr.args):
            return False
        # Check all keyword args are simple
        if not all(self._is_simple_expr(v) for v in expr.kwargs.values()):
            return False
        return True

    # Pipeline: check all steps are pure with simple args
    if isinstance(expr, Pipeline):
        pure_filters = self._get_pure_filters()
        if not self._is_simple_expr(expr.value):
            return False
        for name, args, kwargs in expr.steps:
            if name not in pure_filters:
                return False
            if not all(self._is_simple_expr(arg) for arg in args):
                return False
            if not all(self._is_simple_expr(v) for v in kwargs.values()):
                return False
        return True

    # Function calls are NOT coalesceable (may have side effects)
    # Ternary expressions are NOT coalesceable (complex control flow)
    # Binary/unary ops are NOT coalesceable (complex evaluation)
    return False
```

### 2. F-String AST Generation

```python
def _compile_coalesced_output(self, nodes: list[Any]) -> ast.stmt:
    """Generate f-string append for coalesced nodes.
    
    Note on brace handling:
    - ast.JoinedStr automatically handles brace escaping when the AST
      is compiled to bytecode. We do NOT manually escape {{ and }}.
    - Literal text goes into ast.Constant nodes as-is.
    - Expressions go into ast.FormattedValue nodes.
    
    Note on backslashes:
    - F-strings cannot contain backslashes in expression parts.
    - We detect backslashes during coalesceable checking and fall back.
    """
    from kida.nodes import Data, Output

    # Build f-string components
    parts: list[ast.expr] = []

    for node in nodes:
        if isinstance(node, Data):
            # Literal text - add as constant (NO manual brace escaping)
            # ast.JoinedStr handles escaping during bytecode compilation
            if node.value:  # Skip empty strings
                parts.append(ast.Constant(value=node.value))
        
        elif isinstance(node, Output):
            # Expression - wrap in escape/str function
            expr = self._compile_expr(node.expr)
            
            if node.escape:
                # _e() handles HTML escaping
                expr = ast.Call(
                    func=ast.Name(id="_e", ctx=ast.Load()),
                    args=[expr],
                    keywords=[],
                )
            else:
                # _s() converts to string (for |safe outputs)
                expr = ast.Call(
                    func=ast.Name(id="_s", ctx=ast.Load()),
                    args=[expr],
                    keywords=[],
                )
            
            parts.append(ast.FormattedValue(
                value=expr,
                conversion=-1,  # No conversion (!s, !r, !a)
                format_spec=None,
            ))

    # Create JoinedStr (f-string AST node)
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

Template: `<style>body { color: red }</style>`

The `ast.JoinedStr` node handles brace escaping automatically during bytecode compilation:

```python
# AST generation (NO manual escaping):
ast.Constant(value="<style>body { color: red }</style>")

# Python compiles this to f-string bytecode that outputs:
# <style>body { color: red }</style>
```

**Important**: Do NOT manually replace `{` with `{{`. The AST compiler handles this.

#### Backslashes in Expressions

F-strings don't allow backslashes in the expression part (inside `{}`). This is a Python syntax limitation.

```python
# Template: {{ path.replace("\\", "/") }}
# The compiled expression contains backslash - cannot use f-string
```

**Solution**: Detect at coalesceable-check time and exclude:

```python
def _expr_contains_backslash(self, expr: Any) -> bool:
    """Check if expression would generate code with backslashes."""
    from kida.nodes import Const
    
    if isinstance(expr, Const) and isinstance(expr.value, str):
        return "\\" in expr.value
    
    # Recursively check sub-expressions
    # (Implementation depends on node structure)
    return False
```

When backslash is detected, the node is not coalesceable and falls back to separate `_append()` calls.

#### Nested F-Strings (Python 3.12+)

Python 3.12+ allows nested f-strings. Since Kida targets Python 3.14+, this is not a concern:

```python
# Python 3.12+ allows:
f"outer {f'inner {x}'} outer"
```

However, if an expression is itself an f-string literal in the template, we still fall back to avoid complexity.

#### Empty Data Nodes

Skip empty `Data` nodes to avoid generating empty string constants:

```python
if isinstance(node, Data) and node.value:
    parts.append(ast.Constant(value=node.value))
```

### 4. Coalescing Examples

**Example 1: Simple HTML Element**

Template:
```html
<div id="{{ item.id }}" class="{{ item.class }}">{{ item.name }}</div>
```

Before (5 appends):
```python
_append('<div id="')
_append(_e(item["id"]))
_append('" class="')
_append(_e(item["class"]))
_append('">')
_append(_e(item["name"]))
_append('</div>')
```

After (1 append):
```python
_append(f'<div id="{_e(item["id"])}" class="{_e(item["class"])}">{_e(item["name"])}</div>')
```

**Example 2: With Pure Filter**

Template:
```html
{{ name | upper }}
```

Coalesced (filter is pure):
```python
_append(f'{_e(name.upper())}')  # Assuming filter compiles to method call
```

**Example 3: Broken by Control Flow**

Template:
```html
<span>{{ a }}</span>{% if show %}<span>{{ b }}</span>{% end %}<span>{{ c }}</span>
```

Coalescing groups:
1. `<span>{{ a }}</span>` → coalesced
2. `{% if show %}...{% end %}` → compiled normally (breaks coalescing)
3. `<span>{{ c }}</span>` → coalesced

```python
_append(f'<span>{_e(a)}</span>')
if show:
    _append(f'<span>{_e(b)}</span>')
_append(f'<span>{_e(c)}</span>')
```

## Performance Analysis

### Expected Improvement

| Scenario | Current | With f-strings | Improvement |
|----------|---------|----------------|-------------|
| Simple loop (1000 items, 5 outputs each) | 288µs | 211µs | **1.37x** |
| Mixed template (50% outputs, 50% control) | ~varies | ~varies | **~1.15-1.20x** |
| Complex template (heavy control flow) | ~varies | ~varies | **~1.05x** |
| Control-flow heavy (few consecutive outputs) | baseline | baseline | ~1.0x |

### Why F-Strings Are Faster

1. **Fewer function calls**: 1 `append()` vs N `append()` calls
2. **Python optimization**: f-strings use `BUILD_STRING` bytecode, optimized in CPython
3. **Single allocation**: One string created instead of N intermediate strings
4. **Reduced interpreter overhead**: Fewer opcode dispatches

### When It Doesn't Help

- Templates with heavy control flow (If, For interleaved with outputs)
- Templates using impure or custom filters
- Templates with very few outputs
- Templates where outputs are already isolated

### Benchmark Verification

Add benchmark to `benchmarks/test_benchmark_optimization_levers.py`:

```python
def render_mixed_template() -> str:
    """Realistic template with mixed outputs and control flow."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        # Coalesceable block
        append(f'<div id="{item["id"]}" class="item">')
        # Control flow break
        if item["id"] % 2 == 0:
            append('<span class="even">')
        else:
            append('<span class="odd">')
        # Coalesceable block
        append(f'{item["name"]} - {item["data"]["x"]}</span></div>\n')
    return "".join(buf)


@pytest.mark.benchmark(group="lever:mixed-template")
def test_mixed_template_coalesced(benchmark: BenchmarkFixture) -> None:
    """Mixed template with partial coalescing."""
    result = benchmark(render_mixed_template)
    assert len(result) > 0
```

## Implementation Plan

### Phase 1: Core Infrastructure (2-3 hours)

1. Add `fstring_coalescing` and `pure_filters` to `Environment`
2. Add `_BUILTIN_PURE_FILTERS` constant
3. Add `_get_pure_filters()` method to Compiler
4. Add `_is_coalesceable()` method
5. Add `_is_simple_expr()` recursive helper

### Phase 2: F-String Generation (2-3 hours)

1. Add `_compile_coalesced_output()` method
2. Add `_compile_body()` method with coalescing logic
3. Integrate into `_make_render_function()`
4. Handle edge cases (empty nodes, etc.)

### Phase 3: Edge Case Handling (1-2 hours)

1. Add backslash detection in expressions
2. Verify brace handling (should work automatically)
3. Test Pipeline and Filter argument validation

### Phase 4: Testing (2-3 hours)

1. Unit tests for coalesceable detection
2. Unit tests for f-string AST generation
3. Integration tests for template rendering
4. Edge case tests (braces, backslashes, etc.)
5. Regression tests comparing output before/after

### Phase 5: Benchmarking (1-2 hours)

1. Add mixed template benchmark
2. Verify performance improvements
3. Document results in this RFC

### Phase 6: Documentation (1 hour)

1. Update performance docs
2. Document `fstring_coalescing` and `pure_filters` options
3. Update this RFC with final results

**Total Estimated Time**: 10-14 hours

## Risks and Mitigations

### Risk 1: Incorrect Output

**Risk**: Generated f-string produces different output than append sequence.

**Mitigation**:
- Extensive test coverage comparing before/after output
- Conservative coalesceable detection (fail-safe to append)
- Property-based testing with hypothesis

### Risk 2: Brace Handling Bugs

**Risk**: Braces in literal text cause f-string syntax errors.

**Mitigation**:
- Rely on `ast.JoinedStr` automatic handling (verified approach)
- Unit tests with CSS, JSON, and other brace-heavy content
- Do NOT manually escape braces

### Risk 3: Expression Complexity

**Risk**: Complex expressions that don't work in f-strings.

**Mitigation**:
- Conservative `_is_simple_expr()` that rejects complex expressions
- Fall back to append for any uncertainty
- Explicit exclusion of function calls, ternary, operators

### Risk 4: Performance Regression

**Risk**: Some templates get slower due to detection overhead.

**Mitigation**:
- Only coalesce 2+ consecutive nodes
- O(1) node type checks
- Feature flag to disable if issues found
- Benchmark suite includes diverse patterns

### Risk 5: Custom Filter Side Effects

**Risk**: User marks impure filter as pure, causing bugs.

**Mitigation**:
- Document `pure_filters` contract clearly
- Built-in list is conservative (only obviously pure)
- User opt-in for custom filters

## Testing Strategy

### Unit Tests

```python
class TestCoalesceableDetection:
    def test_data_node_coalesceable(self):
        """Data nodes are always coalesceable."""

    def test_simple_name_coalesceable(self):
        """Simple variable output is coalesceable."""
    
    def test_getattr_coalesceable(self):
        """Attribute access is coalesceable."""
    
    def test_getitem_coalesceable(self):
        """Item access is coalesceable."""

    def test_pure_filter_coalesceable(self):
        """Output with pure filter is coalesceable."""
    
    def test_pure_filter_with_simple_args_coalesceable(self):
        """Pure filter with simple arguments is coalesceable."""
    
    def test_pure_filter_with_complex_args_not_coalesceable(self):
        """Pure filter with complex arguments is not coalesceable."""

    def test_impure_filter_not_coalesceable(self):
        """Output with impure/custom filter is not coalesceable."""

    def test_pipeline_all_pure_coalesceable(self):
        """Pipeline with all pure steps is coalesceable."""
    
    def test_pipeline_impure_step_not_coalesceable(self):
        """Pipeline with impure step is not coalesceable."""

    def test_funccall_not_coalesceable(self):
        """Function calls are not coalesceable."""

    def test_control_flow_not_coalesceable(self):
        """If/For/While nodes are not coalesceable."""
    
    def test_custom_pure_filter_coalesceable(self):
        """User-registered pure filter is coalesceable."""


class TestFStringGeneration:
    def test_simple_coalesce_two_data(self):
        """Two Data nodes coalesce into single f-string."""

    def test_coalesce_data_and_output(self):
        """Data + Output coalesces correctly."""
    
    def test_coalesce_multiple_outputs(self):
        """Multiple outputs coalesce with interpolation."""

    def test_brace_in_literal_preserved(self):
        """Braces in literal text are output correctly."""
    
    def test_css_braces_preserved(self):
        """CSS with braces renders correctly."""
    
    def test_json_braces_preserved(self):
        """JSON with braces renders correctly."""

    def test_escape_function_called(self):
        """Escaped outputs use _e() function."""
    
    def test_safe_output_uses_str(self):
        """Non-escaped outputs use _s() function."""


class TestEdgeCases:
    def test_single_node_not_coalesced(self):
        """Single coalesceable node uses normal compilation."""

    def test_empty_data_skipped(self):
        """Empty Data nodes don't create empty constants."""

    def test_backslash_in_string_constant(self):
        """String constant with backslash falls back to append."""
    
    def test_disabled_optimization(self):
        """fstring_coalescing=False disables coalescing."""


class TestIntegration:
    def test_output_matches_non_coalesced(self):
        """Coalesced template produces identical output."""

    def test_loop_body_coalesced(self):
        """Loop body with consecutive outputs is coalesced."""
    
    def test_control_flow_breaks_coalescing(self):
        """Control flow creates separate coalescing groups."""
    
    def test_nested_loops(self):
        """Nested loops with outputs work correctly."""
```

### Benchmark Verification

```python
@pytest.mark.benchmark(group="coalesce")
def test_coalesced_faster_than_append(benchmark: BenchmarkFixture) -> None:
    """Verify f-string coalescing is faster than append sequence."""
    # Compare coalesced vs non-coalesced rendering
```

## Decisions (Resolved Open Questions)

### Decision 1: Custom Filter Purity

**Question**: How do we handle custom filters?

**Decision**: Custom filters are assumed impure by default. Users can opt-in by adding filter names to `Environment.pure_filters`:

```python
env = Environment()
env.pure_filters.add("my_pure_filter")
```

**Rationale**: Safe default prevents side-effect bugs. Explicit opt-in documents intent.

### Decision 2: Coalescing Threshold

**Question**: Is 2 nodes the right minimum?

**Decision**: Yes, minimum 2 nodes (`COALESCE_MIN_NODES = 2`).

**Rationale**: Benchmarks show improvement even for 2 nodes. Detection overhead is O(1) per node. Lower threshold = more opportunities for optimization.

### Decision 3: Feature Flag

**Question**: Should this be behind a config option?

**Decision**: Yes, `Environment.fstring_coalescing = True` by default.

**Rationale**: Allows disabling for debugging or if edge cases appear. Opt-out rather than opt-in since the optimization is beneficial in most cases.

## Success Criteria

| Metric | Target |
|--------|--------|
| Output-heavy template speedup | ≥1.25x |
| Mixed template speedup | ≥1.10x |
| No rendering regressions | 100% test pass |
| Edge case handling | All known edge cases tested |
| Brace handling | CSS/JSON templates render correctly |

## Alternatives Considered

### Alternative 1: String Concatenation

Generate `+` concatenation instead of f-strings:

```python
_append('<div id="' + _e(item["id"]) + '">' + _e(item["name"]) + '</div>')
```

**Rejected**: Slower than f-strings due to multiple string allocations and concatenation overhead.

### Alternative 2: io.StringIO

Use StringIO instead of list:

```python
buf = io.StringIO()
write = buf.write
write('<div id="')
write(_e(item["id"]))
...
```

**Rejected**: Benchmarks showed 35% *slower* than list.append (`test_benchmark_optimization_levers.py:71-85`).

### Alternative 3: Pre-allocated List

```python
buf = [None] * estimated_size
```

**Rejected**: Would require knowing output size in advance. Not practical for dynamic templates.

### Alternative 4: AST Post-Processing

Walk generated Python AST and merge consecutive `_append()` calls after compilation.

**Rejected**: More complex, harder to debug, and doesn't allow for future optimizations that need template-level context.

## References

- [PEP 498 – Literal String Interpolation](https://peps.python.org/pep-0498/)
- [ast.JoinedStr documentation](https://docs.python.org/3/library/ast.html#ast.JoinedStr)
- [PEP 701 – Syntactic formalization of f-strings (Python 3.12)](https://peps.python.org/pep-0701/)
- `benchmarks/test_benchmark_optimization_levers.py` — benchmark evidence
- `src/kida/compiler/statements/basic.py` — current output compilation
- `src/kida/compiler/core.py:276-436` — `_make_render_function` implementation
- `src/kida/nodes.py:171-187` — Data and Output node definitions
- `src/kida/nodes.py:706-730` — Filter and Pipeline node definitions

## Changelog

- 2026-01-12: Initial draft
- 2026-01-12: Improved based on technical review
  - Fixed AST brace handling (removed manual escaping, ast.JoinedStr handles it)
  - Added Pipeline node support to coalesceable detection
  - Added recursive filter argument validation
  - Resolved open questions with concrete decisions
  - Added `Environment.fstring_coalescing` and `pure_filters` configuration
  - Expanded `_BUILTIN_PURE_FILTERS` list
  - Added mixed template benchmark recommendation
  - Added comprehensive coalescing examples
  - Expanded test cases
- 2026-01-12: **Implemented**
  - Added `fstring_coalescing` and `pure_filters` to `Environment` (`environment/core.py`)
  - Created `compiler/coalescing.py` with `FStringCoalescingMixin`
  - Integrated coalescing into `Compiler` class
  - Added 50 unit tests in `tests/test_fstring_coalescing.py`
  - Added benchmark verification in `benchmarks/test_benchmark_optimization_levers.py`
  - Benchmark results: Simple templates ~11% faster, mixed templates ~1% faster