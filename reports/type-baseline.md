# Type Refinement Baseline

**Date**: 2026-02-08
**Tool**: ty (Astral) v0.0.11+
**Python**: 3.14t

## ty Status

| Metric | Count | Notes |
|--------|-------|-------|
| Total diagnostics | 116 | Full codebase (src + tests + benchmarks) |
| src/ diagnostics | ~28 | Library code only |
| benchmarks/ diagnostics | ~77 | Benchmark scripts (excluded from ty scope) |
| tests/ diagnostics | ~11 | Test files |
| Checked files | 65 | `src/kida/` |

### Error Distribution by Rule

| Rule | Count | Root Cause |
|------|-------|------------|
| `unresolved-attribute` | 35 | Mixin cross-references in compiler/parser |
| `invalid-argument-type` | 32 | Mostly benchmarks; some real type mismatches |
| `not-subscriptable` | 22 | Benchmark files using generics ty can't resolve |
| `unsupported-operator` | 5 | Operator overload issues |
| `invalid-return-type` | 5 | Return type mismatches |
| `unknown-argument` | 2 | Unexpected keyword arguments |
| `not-iterable` | 1 | Iteration over non-iterable |
| `invalid-assignment` | 1 | Type mismatch in assignment |
| `call-non-callable` | 1 | Calling non-callable object |

### Error Hotspots (by file)

| File | Errors | Category |
|------|--------|----------|
| `benchmarks/test_benchmark_optimization_levers.py` | 46 | benchmark |
| `benchmarks/test_benchmark_escape.py` | 27 | benchmark |
| `src/kida/compiler/core.py` | 10 | src (mixin) |
| `tests/test_tstring_r.py` | 6 | test |
| `src/kida/compiler/statements/functions.py` | 5 | src (mixin) |
| `tests/test_kida_bytecode_cache.py` | 4 | test |
| `src/kida/template/loop_context.py` | 4 | src |
| `benchmarks/benchmark_cold_start.py` | 4 | benchmark |
| `src/kida/template/core.py` | 3 | src |
| `src/kida/environment/core.py` | 2 | src |

## Type Annotation Counts

| Metric | Count | Target |
|--------|-------|--------|
| `: Any` annotations | ~298 | <100 |
| `-> Any` returns | ~39 | <10 |
| `dict[str, Any]` | ~44 | <20 |
| `type: ignore` comments | ~13 | <5 |
| `noqa: ANN` suppressions | 4 | 0 |

### Top `: Any` Files

| File | `: Any` Count |
|------|---------------|
| `analysis/dependencies.py` | 63 |
| `analysis/purity.py` | 49 |
| `environment/filters.py` | 46 |
| `environment/tests.py` | 17 |
| `utils/html.py` | 12 |
| `compiler/statements/control_flow.py` | 10 |
| `compiler/statements/variables.py` | 10 |
| `template/core.py` | 9 |
| `compiler/expressions.py` | 8 |

### Top `-> Any` Files

| File | `-> Any` Count |
|------|----------------|
| `environment/filters.py` | 19 |
| `template/loop_context.py` | 8 |
| `template/helpers.py` | 4 |
| `template/cached_blocks.py` | 4 |
| `template/core.py` | 2 |
| `utils/html.py` | 1 |
| `environment/protocols.py` | 1 |

## Existing Type Infrastructure

- 60 files use `from __future__ import annotations`
- 35 files use `TYPE_CHECKING` imports
- 0 `TypedDict` definitions
- 7 `Protocol` definitions (across 4 files)
- `py.typed` marker present

## Prior Type Work

- **Pyright → mypy migration** (RFC implemented, Jan 2026)
- **mypy → ty migration** (completed, pyproject.toml updated)
- **Type suppression reduction** (Phase 1+2 complete under mypy; Phase 3 pending)
- **Mixin protocol typing RFC** (Draft, not started)

## Configuration

Current `[tool.ty]` in pyproject.toml:
```toml
[tool.ty.environment]
python-version = "3.14"

[tool.ty.src]
exclude = ["dist/", "build/"]

[[tool.ty.overrides]]
include = ["src/kida/utils/html.py"]
[tool.ty.overrides.rules]
invalid-method-override = "ignore"
```
