# Epic: Partial Evaluator Enhancement — Close the Optimization Gaps

**Status**: In Progress (Sprints 0-3 complete, Sprint 4 pending)
**Created**: 2026-04-10
**Target**: v0.5.0
**Estimated Effort**: 28-40h
**Dependencies**: None (partial_eval.py is self-contained)
**Source**: Codebase analysis of `src/kida/compiler/partial_eval.py` (1,269 lines), `src/kida/analysis/purity.py` (591 lines), and existing RFCs

---

## Why This Matters

The partial evaluator is Kida's most distinctive optimization: it folds static expressions to constants at compile time, enabling near-`str.format()` speed for static template regions. However, it currently leaves significant optimization opportunities on the table.

**Core problem**: The partial evaluator handles expressions well but barely touches control flow, assignment propagation, or loop iteration — meaning templates with static `{% for %}` loops, `{% set %}` chains, or `{% let %}` bindings get no compile-time benefit even when all values are known.

### Consequences

1. **Static `{% for %}` loops re-execute every render**: A nav bar iterating over `site.nav` (5 items, all static) generates 5 dynamic loop iterations per render instead of 5 pre-rendered Data nodes
2. **`{% set %}` / `{% let %}` values are opaque**: `{% set theme = settings.theme %}` followed by `{{ theme }}` can't be folded because the evaluator doesn't track assignment bindings
3. **No partial BoolOp simplification**: `{{ x and config.enabled }}` where `config.enabled` is statically False could be folded to `False`, but the evaluator gives up when *any* operand is unresolved
4. **List/Dict/Tuple literals never fold**: `{% for x in [1, 2, 3] %}` is left as a runtime list construction even though it's fully constant
5. **Purity analysis is disconnected**: The `analysis/purity.py` module classifies 67+ filters as pure, but only feeds into coalescing — the partial evaluator maintains its own separate pure-filter set
6. **FuncCall is always unresolved**: Even `range(5)` or `len(items)` with static args returns `_UNRESOLVED`

### Evidence Table

| Source | Finding | Proposal Impact |
|--------|---------|-----------------|
| `partial_eval.py:844-859` | `_transform_for` only recurses into body; never unrolls static loops | FIXES (Sprint 2) |
| `partial_eval.py:489` | `FuncCall` always returns `_UNRESOLVED` | FIXES (Sprint 3) |
| `partial_eval.py:669-741` | `_transform_node` skips Set/Let entirely | FIXES (Sprint 1) |
| `partial_eval.py:618-635` | `_eval_boolop` returns `_UNRESOLVED` if any operand unresolved | FIXES (Sprint 1) |
| `constants.py:73` | `PURE_FILTERS_ALL` has 67+ filters; partial eval uses same set | Already integrated |
| `purity.py` vs `partial_eval.py` | Two independent purity registries, no cross-feeding | FIXES (Sprint 4) |
| `benchmarks/test_benchmark_partial_eval.py` | Only tests site config folding; no loop unrolling benchmarks | MITIGATES (Sprint 0) |

---

### Invariants

These must remain true throughout or we stop and reassess:

1. **Behavioral equivalence**: `template.render(ctx)` produces identical output with and without partial evaluation for all inputs. Verified by running `test_partial_eval.py` + snapshot tests after every sprint.
2. **No compile-time blowup**: Partial evaluation of a template with N nodes completes in O(N * D) time where D is the static context depth. No unrolling produces > 10,000 nodes.
3. **Conservative default**: If the evaluator cannot prove an optimization is safe, it leaves the AST unchanged. No heuristic guesses.

---

## Target Architecture

```
Template Source
    ↓
Lexer → Parser → Kida AST
    ↓
Dead Code Elimination (const-only, no context)     ← exists today
    ↓
Partial Evaluation (with static_context)            ← enhance here
  ├─ Phase 1: Assignment propagation (Set/Let tracking)
  ├─ Phase 2: Static loop unrolling (For with known iter)
  ├─ Phase 3: Safe builtin evaluation (range, len, etc.)
  └─ Phase 4: Partial boolean simplification
    ↓
Compiler (Kida AST → Python AST)
    ↓
F-String Coalescing                                 ← benefits from more Data nodes
    ↓
exec() → Template
```

The key insight: each phase produces more Const/Data nodes, which cascade into better f-string coalescing downstream. Sprint ordering is designed so each phase amplifies the next.

---

## Sprint Structure

| Sprint | Focus | Effort | Risk | Ships Independently? |
|--------|-------|--------|------|---------------------|
| 0 | Design & benchmark baseline | 4h | Low | Yes (benchmarks only) |
| 1 | Assignment propagation + partial BoolOp | 8h | Low | Yes |
| 2 | Static loop unrolling | 8h | Medium | Yes |
| 3 | Safe builtin evaluation | 6h | Medium | Yes |
| 4 | Purity analysis integration | 4h | Low | Yes |

---

## Sprint 0: Design & Benchmark Baseline

**Goal**: Establish measurable baselines so every subsequent sprint has a concrete target.

### Task 0.1 — Write targeted benchmarks for each gap

Add benchmark templates that isolate each optimization opportunity:

- **Static for-loop**: Nav bar with 5 static items, measure render time
- **Set/Let chain**: `{% set x = config.a %}{% set y = x | upper %}{{ y }}`
- **Static list literal**: `{% for x in [1, 2, 3, 4, 5] %}{{ x }}{% end %}`
- **Partial BoolOp**: `{{ dynamic_val and false }}`, `{{ true or dynamic_val }}`
- **Safe builtins**: `{{ range(5) | list }}`, `{{ len(items) }}`

**Files**: `benchmarks/test_benchmark_partial_eval.py`
**Acceptance**: `pytest benchmarks/test_benchmark_partial_eval.py --benchmark-only -v` runs all new benchmarks and produces baseline numbers.

### Task 0.2 — Design node-count reduction metric

Add a helper that counts Const/Data nodes before and after partial eval, so we can measure optimization effectiveness independent of runtime performance.

**Files**: `tests/test_partial_eval.py`
**Acceptance**: New test class `TestOptimizationMetrics` with assertions like `assert data_count_after > data_count_before`.

---

## Sprint 1: Assignment Propagation + Partial BoolOp

**Goal**: Track `{% set %}` and `{% let %}` bindings so downstream expressions resolve, and simplify boolean expressions where one operand is statically known.

### Task 1.1 — Track Set/Let bindings in PartialEvaluator

When `_transform_node` encounters a `Set` or `Let` where the value resolves:

```python
if isinstance(node, Set):
    val = self._try_eval(node.value)
    if val is not _UNRESOLVED:
        self._ctx[node.name] = val  # propagate to downstream expressions
```

Must handle scoping correctly: `Let` is block-scoped, `Set` is template-scoped.

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**:
- `rg 'isinstance.*Set' src/kida/compiler/partial_eval.py` finds the new handler
- `pytest tests/test_partial_eval.py -k "set or let"` passes with new tests

### Task 1.2 — Partial BoolOp simplification

When evaluating `and`/`or`, if one operand resolves to a short-circuit value, simplify even if other operands are unresolved:

- `false and X` → `False` (regardless of X)
- `true or X` → `True` (regardless of X)
- `X and false` → must still evaluate X for side effects... but in template expressions, there are no side effects, so this is safe.

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**: `pytest tests/test_partial_eval.py -k "boolop"` passes with new partial-resolution tests.

### Task 1.3 — CondExpr partial simplification

When `CondExpr.test` resolves, collapse to just the winning branch even in `_transform_expr` (not just `_try_eval`).

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**: `{{ x if config.enabled else "disabled" }}` with `config.enabled=False` folds to `Data("disabled")`.

---

## Sprint 2: Static Loop Unrolling

**Goal**: When a `{% for %}` loop's iterable resolves to a known sequence, unroll the loop body at compile time.

### Task 2.1 — Implement loop unrolling in `_transform_for`

When `self._try_eval(node.iter)` resolves to an iterable:

1. Check length against `_MAX_UNROLL_ITERATIONS` (default: 50)
2. For each item, create a sub-evaluator with `target=item` in context
3. Transform the body with the sub-evaluator
4. Concatenate all transformed bodies
5. If the loop uses `loop.*` properties, inject them as constants (`loop.index`, `loop.first`, `loop.last`, etc.)

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**:
- Template `{% for x in site.nav %}{{ x.title }}{% end %}` with static `site.nav` produces N Data nodes instead of a For node
- `pytest tests/test_partial_eval.py -k "unroll"` passes
- Benchmark shows measurable improvement for static nav rendering

### Task 2.2 — Handle tuple unpacking in loop targets

Support `{% for key, value in items.items() %}` when `items` is static.

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**: `{% for k, v in {"a": 1, "b": 2}.items() %}{{ k }}={{ v }}{% end %}` folds correctly.

### Task 2.3 — List/Dict/Tuple literal evaluation

Evaluate `[1, 2, 3]`, `{"key": "val"}`, `(1, 2)` in `_try_eval` when all elements resolve.

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**: `{% for x in [1, 2, 3] %}{{ x }}{% end %}` is unrolled.

---

## Sprint 3: Safe Builtin Evaluation

**Goal**: Allow `range()`, `len()`, and other safe builtins to be evaluated at compile time when arguments are static.

### Task 3.1 — Define safe-builtin allowlist

Create a mapping of function names to callables that are safe for compile-time evaluation:

```python
_SAFE_BUILTINS: dict[str, Callable] = {
    "range": range,
    "len": len,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "zip": zip,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
}
```

**Files**: `src/kida/utils/constants.py`, `src/kida/compiler/partial_eval.py`
**Acceptance**: `rg 'SAFE_BUILTINS' src/kida/` finds the constant definition and its usage.

### Task 3.2 — Implement FuncCall evaluation

In `_try_eval`, handle `FuncCall(Name(builtin_name), args, kwargs)` when the function is in the allowlist and all arguments resolve.

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**:
- `{{ range(5) | list }}` with no runtime context evaluates at compile time
- `{{ len(site.nav) }}` with static `site.nav` folds to a Const
- `pytest tests/test_partial_eval.py -k "builtin"` passes

### Task 3.3 — Guard against DoS in builtins

Prevent `range(10**9)` or `sorted(huge_list)` from consuming memory at compile time:

- Max iterable length for `range`: 10,000
- Max input size for `sorted`/`reversed`: 10,000
- Timeout: not needed (Python operations are fast for small inputs)

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**: `range(100000)` returns `_UNRESOLVED` instead of materializing.

---

## Sprint 4: Purity Analysis Integration

**Goal**: Unify the partial evaluator's pure-filter set with the analysis engine's purity analysis, enabling automatic discovery of user-defined pure filters.

### Task 4.1 — Feed purity analysis results into partial evaluation

When `Environment._compile` runs partial evaluation, also run purity analysis on any user-registered filters and merge results into `pure_filters`.

**Files**: `src/kida/environment/core.py`, `src/kida/analysis/purity.py`
**Acceptance**: A user-registered filter decorated with `@pure` is automatically eligible for compile-time evaluation.

### Task 4.2 — Add `@pure` decorator for user filters

Provide a simple API for users to mark their custom filters as pure:

```python
from kida import pure

@pure
def my_filter(value):
    return value.strip().lower()

env.add_filter("clean", my_filter)
```

**Files**: `src/kida/__init__.py`, `src/kida/environment/registry.py`
**Acceptance**: `pytest tests/test_partial_eval.py -k "user_pure"` passes.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Loop unrolling blows up AST size | Medium | High | `_MAX_UNROLL_ITERATIONS` cap (50); Sprint 2 Task 2.1 |
| Assignment propagation changes scoping semantics | Low | High | Conservative: only propagate when value fully resolves; Sprint 1 Task 1.1 |
| Safe builtins allow arbitrary code execution | Low | High | Strict allowlist, no `eval`/`exec`; Sprint 3 Task 3.1 |
| Partial BoolOp changes short-circuit behavior | Low | Medium | Template expressions have no side effects; Sprint 1 Task 1.2 |
| Behavioral divergence between eval'd and non-eval'd templates | Low | High | Invariant #1 enforced by test suite after every sprint |

---

## Success Metrics

| Metric | Current | After Sprint 2 | After Sprint 4 |
|--------|---------|----------------|----------------|
| Static nav (5 items) render time | ~4μs (dynamic for-loop) | ~1μs (pre-rendered Data) | ~1μs |
| Const/Data node count for benchmark template | ~8 (site.title etc.) | ~25 (+ unrolled loops) | ~30 (+ builtin folding) |
| Pure filters available for folding | 67 (hardcoded) | 67 | 67 + user-defined |
| `{% set %}` chain folding | 0% (not tracked) | 100% for static chains | 100% |
| `test_partial_eval.py` test count | ~30 | ~55 | ~70 |

---

## Relationship to Existing Work

- **rfc-performance-optimization.md** — Superseded (closed). This epic addresses a different axis: compile-time optimization depth, not runtime hot-path speed.
- **rfc-large-template-optimization.md** — Implemented (Phase 1 & 2). Complementary: type-aware escaping and lazy LoopContext are runtime optimizations; this epic's compile-time folding stacks on top.
- **rfc-fstring-code-generation.md** — In progress. Direct beneficiary: more Data nodes from partial eval → more f-string coalescing opportunities.
- **epic-i18n-completion.md** — Parallel. No dependency, but `{% trans %}` blocks should be excluded from partial eval (they depend on runtime locale).

---

## Changelog

- 2026-04-10: Initial draft based on codebase analysis of partial_eval.py, purity.py, and existing RFCs
- 2026-04-10: Sprint 0 complete — benchmarks + node-count metrics added
- 2026-04-10: Sprint 1 complete — Set/Let propagation, partial BoolOp, CondExpr simplification
- 2026-04-10: Sprint 2 complete — static loop unrolling, List/Dict/Tuple/ListComp literal evaluation
- 2026-04-10: Sprint 3 complete — safe builtin evaluation (range, len, sorted, etc.) + Range literals
