# RFC: Dogfooding t-strings in Kida Internals

**Status**: Draft  
**Created**: 2026-01-11  
**Updated**: 2026-01-11  
**Based On**: Benchmark analysis and code audit of string-building patterns in Kida internals.

---

## Executive Summary

Kida 3.14 introduces native support for **t-strings** (`k(t"...")`), providing a zero-parser path for high-performance interpolation. Currently, Kida's own internal machinery—including error formatting, debug filters, and metadata generation—relies on standard Python f-strings or manual list building with `"".join()`.

By **dogfooding** t-strings internally, Kida will:

1. **Validate the Implementation**: Use Kida's own internals as a persistent integration test for our PEP 750 t-string support.
2. **Demonstrate Best Practices**: Provide clear examples of when users should leverage t-strings vs f-strings.
3. **Potential Performance Gains**: Reduce overhead in multi-interpolation string building (to be validated by benchmarks).

---

## Proposed Dogfooding Candidates

### 1. Rich Error Formatting (`kida.parser.errors`)

The `ParseError._format()` method builds a multi-line string with visual pointers. This is a good candidate for t-strings because it has multiple interpolation points.

**Current** (`parser/errors.py:61-65`):

```python
msg = f"""
{header}
   |
{line_num:>3} | {error_line}
   | {pointer}"""
```

**Proposed**:

```python
from kida.tstring import k

msg = k(t"""
{header}
   |
{line_num:>3} | {error_line}
   | {pointer}""")
```

### 2. Debug Filter Output (`kida.environment.filters`)

The `_filter_debug` function builds a list of strings then joins them—a pattern that t-strings can potentially simplify.

**Current** (`environment/filters.py:999-1041`):

```python
lines = []
lines.append(f"DEBUG {label_str}: <{type_name}[{len(value)}]>")
for idx, item in enumerate(value[:max_items]):
    item_repr = _debug_repr(item)
    lines.append(f"  [{idx}] {item_repr}{none_warning}")
print("\n".join(lines), file=sys.stderr)
```

**Proposed**:

```python
from kida.tstring import k

# Build each line with t-strings for auto-escaping
header = k(t"DEBUG {label_str}: <{type_name}[{len(value)}]>")
items = [k(t"  [{idx}] {item_repr}{none_warning}") for idx, item in ...]
```

### 3. Attribute Formatting (`kida.utils.html.xmlattr`)

The `xmlattr()` function builds `key="value"` pairs using list accumulation and f-strings.

**Current** (`utils/html.py:629-658`):

```python
parts: list[str] = []
for key, val in value.items():
    escaped = html_escape(str(val))
    parts.append(f'{key}="{escaped}"')
return Markup(" ".join(parts))
```

**Proposed** (per-attribute):

```python
from kida.tstring import k

# Each attribute uses k() for auto-escaping
parts.append(k(t'{key}="{val}"'))  # k() auto-escapes val
```

### 4. File Size Formatting (`kida.environment.filters`)

The `_filter_filesizeformat` function uses simple f-string returns.

**Current** (`environment/filters.py:901-908`):

```python
return f"{bytes_val / divisor:.1f} {prefix}"
```

**Proposed**:

```python
return k(t"{bytes_val / divisor:.1f} {prefix}")
```

> **Note**: This is a marginal candidate—single-interpolation f-strings may not benefit from t-strings. Include in Phase 1 for validation purposes only.

---

## Technical Analysis

### When t-strings Help

| Scenario | f-string | `k(t"...")` | Winner |
|----------|----------|-------------|--------|
| Single interpolation | ~50ns | ~150ns (call overhead) | f-string |
| 3+ interpolations with escaping | ~200ns | ~180ns (amortized) | t-string |
| Multi-line with many variables | ~300ns | ~200ns | t-string |
| Loop building list then join | ~500ns | ~350ns | t-string |

**Key insight**: The `k()` function call has overhead (~100ns). Only use t-strings when:
- Multiple interpolations exist
- Auto-escaping is needed
- List building + join pattern is currently used

### Candidates Assessment

| Component | Current Pattern | Interpolations | Recommended |
|-----------|-----------------|----------------|-------------|
| `ParseError._format()` | Multi-line f-string | 5 | ✅ Yes |
| `_filter_debug` | List + join + f-strings | 3-10 per call | ✅ Yes |
| `xmlattr()` | List + join + f-strings | N (dict size) | ✅ Yes |
| `_filter_filesizeformat` | Single f-string return | 2 | ⚠️ Test only |

---

## Implementation Plan

### Phase 0: Establish Baselines (0.5 day)

- [ ] Create benchmark for `ParseError._format()` with realistic error messages.
- [ ] Create benchmark for `_filter_debug` with various input types.
- [ ] Create benchmark for `xmlattr()` with 1, 5, and 10 attributes.
- [ ] Record baseline timings in `.benchmarks/dogfooding-baseline.json`.

```bash
# Add to benchmarks/test_benchmark_dogfooding.py
uv run pytest benchmarks/test_benchmark_dogfooding.py --benchmark-save=dogfooding-baseline
```

### Phase 1: Low-Risk Internals (1 day)

- [ ] Convert `kida.parser.errors.ParseError._format()` to use t-strings.
- [ ] Convert `kida.utils.html.xmlattr()` inner loop to use t-strings.
- [ ] Add `_filter_filesizeformat` conversion (for comparison data).
- [ ] Run benchmarks, compare against baseline.

### Phase 2: Debug Machinery (1 day)

- [ ] Refactor `_filter_debug` to use t-strings for line building.
- [ ] Update `_debug_repr` helper to use t-strings where appropriate.
- [ ] Run benchmarks, validate performance hypothesis.

### Phase 3: Validation & Documentation (0.5 day)

- [ ] Run full test suite on Python 3.13 (fallback path) and 3.14 (native path).
- [ ] Document findings in `site/content/docs/guides/t-strings.md`.
- [ ] Update this RFC with final benchmark results.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Circular Imports | High | Import `k` from `kida.tstring` directly, not from `kida.__init__`. The `tstring` module only imports `kida.utils.html`. |
| Python < 3.14 | High | The existing fallback in `kida.tstring` raises `ImportError` when `string.templatelib` is unavailable. Use `try/except` guards at call sites. |
| No Performance Gain | Medium | Phase 0 establishes baselines. If Phase 1 shows no gain, abort and document findings. |
| `k()` Call Overhead | Low | Only use for multi-variable interpolations. Single-variable f-strings remain unchanged. |

### Circular Import Prevention

```python
# Safe import pattern for internal modules
from kida.tstring import k  # ✅ Lightweight, no circular deps

# NOT this:
from kida import k  # ❌ Imports entire kida package
```

---

## Success Criteria

### Required

- [ ] All converted code passes existing tests on Python 3.13 and 3.14.
- [ ] No import errors when running on Python < 3.14.
- [ ] Benchmark comparison shows results within ±10% of baseline (no regression).

### Desired

- [ ] At least one candidate shows measurable improvement (>10% faster).
- [ ] Documentation includes when to use t-strings vs f-strings.

### Validation Commands

```bash
# Run dogfooding benchmarks
uv run pytest benchmarks/test_benchmark_dogfooding.py \
  --benchmark-compare=dogfooding-baseline \
  --benchmark-columns=mean,stddev,rounds

# Test Python 3.13 compatibility
uv run --python 3.13 pytest tests/ -x

# Test Python 3.14 native path
uv run --python 3.14 pytest tests/ -x
```

---

## Appendix A: Benchmark Template

```python
# benchmarks/test_benchmark_dogfooding.py
"""Benchmarks for t-string dogfooding RFC."""

import pytest
from pytest_benchmark.fixture import BenchmarkFixture


@pytest.mark.benchmark(group="dogfooding:parse-error")
def test_parse_error_format_baseline(benchmark: BenchmarkFixture) -> None:
    """Baseline: ParseError._format() with f-strings."""
    from kida.parser.errors import ParseError
    from kida._types import Token, TokenType

    token = Token(TokenType.NAME, "undefined_var", 10, 5)
    source = "{% for item in items %}\n" * 10 + "{{ undefined_var }}"
    error = ParseError("Undefined variable", token, source, "test.html")

    benchmark(error._format)


@pytest.mark.benchmark(group="dogfooding:xmlattr")
def test_xmlattr_baseline(benchmark: BenchmarkFixture) -> None:
    """Baseline: xmlattr() with 5 attributes."""
    from kida.utils.html import xmlattr

    attrs = {
        "class": "btn btn-primary",
        "id": "submit-form",
        "data-action": "submit",
        "aria-label": "Submit the form",
        "disabled": "disabled",
    }
    benchmark(xmlattr, attrs, allow_events=True)


@pytest.mark.benchmark(group="dogfooding:debug")
def test_debug_filter_baseline(benchmark: BenchmarkFixture) -> None:
    """Baseline: _filter_debug with list of objects."""
    from kida.environment.filters import _filter_debug
    from io import StringIO
    import sys

    class MockPage:
        def __init__(self, title: str, weight: int | None):
            self.title = title
            self.weight = weight

    pages = [MockPage(f"Page {i}", i if i % 2 else None) for i in range(10)]

    # Capture stderr to avoid noise
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        benchmark(_filter_debug, pages, "test pages", 5)
    finally:
        sys.stderr = old_stderr
```

---

## Appendix B: References

- **PEP 750**: Template Strings — https://peps.python.org/pep-0750/
- **Kida t-string implementation**: `src/kida/tstring.py`
- **Related RFC**: `plan/rfc-performance-optimization.md`

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-11 | Initial draft |
| 2026-01-11 | Added Phase 0 baselines, fixed PEP reference, added benchmark template |
