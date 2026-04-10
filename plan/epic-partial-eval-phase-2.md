# Epic: Partial Evaluator Phase 2 — Widen the Optimization Surface

**Status**: Complete
**Created**: 2026-04-10
**Target**: 0.4.0
**Estimated Effort**: 18–28h
**Dependencies**: epic-partial-eval-enhancement.md (complete)
**Source**: Code audit of `compiler/partial_eval.py`, `analysis/purity.py`, `analysis/dependencies.py`

---

## Why This Matters

The Phase 1 partial evaluator (epic-partial-eval-enhancement.md) addressed the deepest gaps: assignment propagation, loop unrolling, builtin evaluation, and filter chains. All 5 sprints shipped. But the evaluator still has **6 node types and 2 structural patterns** where static information is available but not exploited.

### Consequences

1. **`With` blocks are opaque** — `{% with title = site.title %}{{ title }}{% end %}` does not propagate `title` into the body when `site` is in static context. `_transform_node` has no `With` handler. With blocks appear in 147 test occurrences and are idiomatic for aliasing expensive expressions.
2. **`Match` statements can't be eliminated** — `{% match config.theme %}{% case "dark" %}...{% end %}` keeps all branches at runtime even when `config.theme` is compile-time known. No DCE or partial eval for Match nodes. 38 match tests exist.
3. **`Test` expressions bail out** — `{% if x is defined %}`, `{% if x is none %}` return `_UNRESOLVED` from `_try_eval`. These are the most common guards in real templates and prevent downstream branch elimination.
4. **`_transform_expr` has 7 fall-through gaps** — UnaryOp, Compare, Concat, FuncCall, List, Tuple, Dict all fall through to `return expr` (line 1505) without attempting sub-expression simplification. A mixed expression like `site.title ~ " | " ~ page_name` where `site.title` resolves but `page_name` doesn't could at least simplify the left operand.
5. **ListComp tuple unpacking bails** — `[name for name, age in users]` returns `_UNRESOLVED` at line 662 because target is not `Name`. Tuple targets are common in dict `.items()` iteration.
6. **Cross-block Set propagation stops at With/For boundaries** — A `{% set x = site.name %}` resolved in outer scope doesn't flow into a `{% with %}` body because `With` isn't traversed.

### Evidence Table

| Finding | Location | Proposal Impact |
|---------|----------|-----------------|
| No `With` handler in `_transform_node` | `partial_eval.py:886-961` (missing) | FIXES — Sprint 1 |
| No `Match` handler in `_transform_node` or DCE | `partial_eval.py:886-961` (missing) | FIXES — Sprint 2 |
| `_try_eval` doesn't handle `Test` nodes | `partial_eval.py:579` (falls through) | FIXES — Sprint 1 |
| `_transform_expr` incomplete for 7 node types | `partial_eval.py:1396-1505` | FIXES — Sprint 3 |
| ListComp tuple unpacking bails at line 662 | `partial_eval.py:662` | FIXES — Sprint 2 |
| `With` body not traversed for propagation | `partial_eval.py:886-961` (missing) | FIXES — Sprint 1 |

---

### Invariants

These must remain true throughout or we stop and reassess:

1. **Partial eval never changes observable behavior** — Every transformation must produce identical rendered output for all inputs. The evaluator is conservative: if resolution is uncertain, preserve the original node.
2. **Compile time stays O(template_size)** — No transformation introduces quadratic or exponential blowup. Depth limits and size guards remain enforced.
3. **All existing 106 partial eval tests pass** — No regressions in Phase 1 behavior.

---

## Target Architecture

After Phase 2, `_transform_node` handles these additional node types:

```
Before (Phase 1):    Output, If, For, Block, Def, CallBlock, SlotBlock, Set, Let
After  (Phase 2): + With, Match, Capture, While (traverse only)
```

`_try_eval` handles these additional expression types:

```
Before (Phase 1):    Const, Name, Getattr, Getitem, BinOp, UnaryOp, Compare,
                     BoolOp, CondExpr, Concat, Filter, Pipeline, NullCoalesce,
                     MarkSafe, List, Tuple, Dict, ListComp, FuncCall, Range
After  (Phase 2): + Test (is defined, is none, is odd, etc.)
```

`_transform_expr` gains sub-expression simplification for:

```
Before (Phase 1):    Const, Name, Getattr, Getitem, BinOp, NullCoalesce,
                     MarkSafe, Filter, Pipeline, BoolOp, CondExpr
After  (Phase 2): + UnaryOp, Compare, Concat, FuncCall, List, Tuple, Dict
```

---

## Sprint Structure

| Sprint | Focus | Effort | Risk | Ships Independently? |
|--------|-------|--------|------|---------------------|
| 0 | Benchmark baseline & design validation | 2h | Low | Yes (metrics only) |
| 1 | `With` propagation + `Test` evaluation | 5–7h | Low | Yes |
| 2 | `Match` elimination + ListComp tuple targets | 5–8h | Medium | Yes |
| 3 | `_transform_expr` sub-expression widening | 4–7h | Low | Yes |
| 4 | Integration benchmarks + coalescing cascade | 2–4h | Low | Yes |

---

## Sprint 0: Benchmark Baseline

**Goal**: Establish measurable baselines before any code changes.

### Task 0.1 — Create benchmark templates exercising the gaps

Write 4 benchmark templates that exercise the specific optimization gaps:
- `bench_with_propagation.html` — nested `{% with %}` aliasing static context values
- `bench_match_static.html` — `{% match %}` on compile-time-known values with 5+ cases
- `bench_test_guards.html` — `{% if x is defined %}` / `{% if x is none %}` guard patterns
- `bench_mixed_expr.html` — expressions mixing static and dynamic operands (`site.title ~ " | " ~ page.name`)

**Files**: `benchmarks/templates/`
**Acceptance**: `pytest benchmarks/ -k "bench_with or bench_match or bench_test or bench_mixed"` runs successfully. Record baseline node counts and render times.

### Task 0.2 — Verify `_try_eval` coverage map

Count which expression types hit the `return _UNRESOLVED` fallback in production-like templates.

**Acceptance**: Document the top 5 unresolved node types by frequency.

---

## Sprint 1: `With` Propagation + `Test` Evaluation

**Goal**: Propagate static values through `{% with %}` blocks and resolve `is defined`/`is none` tests at compile time.

### Task 1.1 — Add `With` handler to `_transform_node`

When `_transform_node` encounters a `With` node:
1. Evaluate each binding's value expression via `_try_eval`
2. For resolved bindings, add them to a sub-evaluator's context
3. Transform the body with the augmented context
4. Reconstruct the `With` node with simplified bindings and body

This mirrors how `_transform_for` creates sub-evaluators for each iteration, but is simpler (no loop properties).

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**:
- `{% with title = site.title %}{{ title }}{% end %}` with `site.title` in static context → `Data("My Blog")`
- `{% with x = dynamic_var %}{{ x }}{% end %}` → unchanged (runtime binding)
- `rg 'isinstance.*With' src/kida/compiler/partial_eval.py` returns at least one hit

### Task 1.2 — Add `Test` expression evaluation to `_try_eval`

Handle `Test` nodes for compile-time-resolvable tests:
- `is defined` → check if name exists in static context
- `is none` / `is not none` → check resolved value
- `is odd` / `is even` → evaluate on resolved integer
- `is string` / `is number` / `is mapping` / `is iterable` / `is sequence` → type checks on resolved values

Only evaluate tests whose semantics are well-defined and side-effect-free.

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**:
- `{% if site is defined %}yes{% end %}` with `site` in static context → `Data("yes")`
- `{% if missing is defined %}yes{% else %}no{% end %}` with no `missing` → `Data("no")`
- `{% if count is odd %}` with `count=3` in static context → branch eliminated

### Task 1.3 — Tests for Sprint 1

Add tests covering:
- With block propagation (simple, nested, mixed static/dynamic bindings)
- With + downstream Output resolution
- Test expression folding (defined, none, odd/even, type tests)
- Test + If branch elimination cascade
- Edge cases: With blocks inside For loops, With blocks referencing other With bindings

**Files**: `tests/test_partial_eval.py`
**Acceptance**: `pytest tests/test_partial_eval.py -v` — all new tests pass, no regressions.

---

## Sprint 2: `Match` Elimination + ListComp Tuple Targets

**Goal**: Eliminate dead match/case branches when subject is compile-time-known, and support tuple unpacking in list comprehensions.

### Task 2.1 — Add `Match` handler to `_transform_node`

When `_transform_node` encounters a `Match` node:
1. Try to evaluate the subject via `_try_eval`
2. If resolved, iterate cases and match against pattern:
   - `Const` patterns: exact equality check
   - `Name("_")` wildcard: always matches
   - Other patterns: bail (leave Match intact)
3. Inline the winning branch body (same `_InlinedBody` pattern as `If`)
4. If subject is unresolved, recurse into each case's body

Also add `Match` support to DCE (`_dce_transform_body`).

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**:
- `{% match "dark" %}{% case "dark" %}dark theme{% case "light" %}light theme{% end %}` → `Data("dark theme")`
- `{% match site.theme %}{% case "dark" %}...{% end %}` with `site.theme = "dark"` in static context → branch inlined
- Wildcard case (`{% case _ %}`) handled correctly as default

### Task 2.2 — Support tuple unpacking in ListComp evaluation

Change `_try_eval_listcomp` (line 662) to handle `Tuple` targets:
1. When target is `Tuple`, extract name list
2. For each iteration item, unpack into the target names
3. Build sub-context with all unpacked names

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**:
- `[name for name, age in [("Alice", 30), ("Bob", 25)]]` → `["Alice", "Bob"]`
- `[x + y for x, y in pairs]` with `pairs` in static context → folded list

### Task 2.3 — Tests for Sprint 2

**Files**: `tests/test_partial_eval.py`
**Acceptance**: All new tests pass. Specifically:
- Match with constant subject, various pattern types
- Match with static context subject
- Match wildcard / default case
- Match with unresolvable subject (recurse only)
- ListComp tuple unpacking (pairs, triples)
- ListComp tuple unpacking with filter conditions

---

## Sprint 3: `_transform_expr` Sub-Expression Widening

**Goal**: When a complex expression can't be fully resolved, simplify its resolvable sub-expressions to Const nodes. This enables more f-string coalescing downstream.

### Task 3.1 — Add sub-expression recursion for UnaryOp, Compare, Concat

Currently these fall through to `return expr` in `_transform_expr`. Add:
- `UnaryOp`: try full eval → if unresolved, transform operand
- `Compare`: try full eval → if unresolved, transform left and comparators
- `Concat`: try full eval → if unresolved, transform each node in `.nodes`

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**:
- `not site.debug` with `site.debug = False` → `Const(True)` (already works via full eval)
- `site.title ~ " | " ~ page.name` with static `site.title` → `Concat(Const("My Blog"), Const(" | "), Name("page.name"))` (sub-expr simplified)
- `rg 'return expr' src/kida/compiler/partial_eval.py | wc -l` decreases

### Task 3.2 — Add sub-expression recursion for FuncCall, List, Tuple, Dict

- `FuncCall`: try full eval → if unresolved, transform args and kwargs
- `List`: try full eval → if unresolved, transform each item
- `Tuple`: try full eval → if unresolved, transform each item
- `Dict`: try full eval → if unresolved, transform each key/value

**Files**: `src/kida/compiler/partial_eval.py`
**Acceptance**:
- `[site.title, page.name]` with static `site.title` → `List(Const("My Blog"), Name("page.name"))`
- `len(items)` with unresolved `items` → unchanged (can't simplify)
- `{"title": site.title, "author": page.author}` with static `site.title` → Dict with simplified key

### Task 3.3 — Tests for Sprint 3

**Files**: `tests/test_partial_eval.py`
**Acceptance**: Tests covering partial simplification for each node type. Verify coalescing benefits by checking that more Data nodes are produced in integration tests.

---

## Sprint 4: Integration Benchmarks + Coalescing Cascade

**Goal**: Measure end-to-end improvements and verify that Phase 2 optimizations cascade into better f-string coalescing.

### Task 4.1 — Run benchmark suite against Sprint 0 baseline

Re-run the benchmark templates from Sprint 0 and compare:
- Node count reduction (Const/Data nodes vs total)
- Render time delta
- Coalesced f-string count (measure via AST inspection)

**Files**: `benchmarks/`
**Acceptance**: At least 3 of 4 benchmark templates show measurable improvement in node count.

### Task 4.2 — Update `kida explain` output

The CLI `kida explain` command should report Phase 2 optimizations (With propagation, Match elimination, Test folding).

**Files**: `src/kida/cli.py`
**Acceptance**: `kida explain template.html --static-context '{"site": ...}'` shows simplified With/Match/Test nodes.

### Task 4.3 — Update purity analysis for new patterns

Ensure `PurityAnalyzer` correctly classifies the new optimized patterns so cache safety analysis remains sound.

**Files**: `src/kida/analysis/purity.py`
**Acceptance**: Templates optimized by Phase 2 still produce correct purity classifications.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `With` propagation leaks variables across scope boundaries | Medium | High | Sprint 1: sub-evaluator pattern (copy context, don't mutate parent). Same pattern as `_try_unroll_for`. |
| `Match` pattern matching has edge cases (nested patterns, guards) | Medium | Medium | Sprint 2: only handle Const and wildcard patterns initially. Complex patterns preserved as-is. |
| `Test` evaluation diverges from runtime semantics | Low | High | Sprint 1: only implement tests with unambiguous semantics (`defined`, `none`, `odd`/`even`). Map to same logic as runtime test functions. |
| Sub-expression simplification increases compile time | Low | Low | Sprint 3: only recurse one level (same depth limit applies). Measure in Sprint 4. |
| Coalescing doesn't benefit from sub-expression Const nodes | Low | Low | Sprint 4 validates. Even if coalescing benefit is small, the Const propagation still reduces runtime lookups. |

---

## Success Metrics

| Metric | Phase 1 Baseline | Target | Actual (Sprint 4) |
|--------|-----------------|--------|-------------------|
| Node types handled by `_transform_node` | 9 | 11 | **11** (+With, +Match) |
| Expression types in `_try_eval` | 20 | 21 | **21** (+Test) |
| Expression types in `_transform_expr` (sub-expr) | 11 | 18 | **18** (+UnaryOp, Compare, Concat, FuncCall, List, Tuple, Dict) |
| `_transform_expr` fall-through count | 9 | 2 | **1** (final catch-all only) |
| Test count in `test_partial_eval.py` | 106 | ~150 | **178** |
| With bench AST nodes | 20 dyn / 20 stat | — / <12 | 20 / **8** (60% reduction) |
| Match bench AST nodes | 8 dyn / 8 stat | — / <4 | 8 / **3** (62.5% reduction) |
| Test guards If count | 5 / 5 | 5 / ≤2 | 5 / **1** |
| Test guards render (μs) | ~102 / ~102 | — / <20 | 50.2 / **8.1** (6.2x speedup) |
| Match node preserved? | Yes (both) | No (static) | **No** (eliminated) |
| Mixed expr render (μs) | 11.0 / 9.6 | — / <8.0 | 11.4 / **7.8** (1.46x speedup) |

---

## Relationship to Existing Work

- **epic-partial-eval-enhancement.md** — prerequisite (complete). Phase 2 builds on the same architecture.
- **rfc-large-template-optimization.md** — parallel. That RFC addresses runtime hot-path optimization (lazy LoopContext, type-aware escaping). Phase 2 is compile-time only.
- **epic-template-framework-gaps.md** — Invariant 3 requires new constructs (scoped slots, error boundaries, i18n) to participate in constant folding. Phase 2's `With` propagation directly helps `{% trans %}` blocks that use `{% with %}` for variable binding.
- **rfc-fstring-code-generation.md** — downstream beneficiary. More Const nodes from `_transform_expr` widening → more coalescing opportunities.

---

## Changelog

- 2026-04-10: Initial draft (Phase 2 plan)
- 2026-04-10: Sprint 0 complete — benchmarks and coverage map verified. Baselines: With 8.3/7.8μs, Match 5.9/6.2μs (no improvement), Test guards 5/5 If nodes (no elimination), Mixed 11.0/9.6μs. All 4 gaps confirmed.
- 2026-04-10: Sprint 1 complete — With propagation + Test evaluation + is/is not Compare support. Test guards: 5→1 If nodes (102.6μs→9.6μs, 10.7x speedup). `is defined` fully folds. 29 new tests (135 total), zero regressions.
- 2026-04-10: Sprint 2 complete — Match elimination (both DCE and partial eval) + ListComp tuple unpacking. Match nodes fully eliminated when subject is compile-time-known (Const patterns + wildcard). DCE `_dce_transform_body` gained `Match()` case with `changed` tracking fix. ListComp handles `Tuple` targets for `[x for x, y in pairs]` patterns. 21 new tests (156 total), zero regressions.
- 2026-04-10: Sprint 3 complete — `_transform_expr` sub-expression widening for 7 node types (UnaryOp, Compare, Concat, FuncCall, List, Tuple, Dict) plus BinOp, MarkSafe, Filter/Pipeline sub-expression recursion. Mixed expressions like `site.title ~ " | " ~ page_title` now fold the static sub-tree to Const. 22 new tests (178 total), full suite 3420 passed, zero regressions.
- 2026-04-10: Sprint 4 complete — Integration benchmarks confirm 4/4 templates improved. With: 60% node reduction, 1.25x speedup. Match: 62.5% node reduction, eliminated entirely. Test guards: 6.2x speedup (50.2→8.1μs), 4/5 If nodes eliminated. Mixed: 28.6% node reduction, 1.46x speedup. `kida explain` updated with Phase 2 sub-capabilities. Purity analysis verified sound (127 tests pass). **Phase 2 complete — all 5 sprints shipped.**
