# Epic: t-string Dogfooding — Eat Our Own Cooking

**Status**: Complete (Sprint 0-4 delivered)
**Created**: 2026-04-12
**Completed**: 2026-04-12
**Target**: v0.5.0
**Estimated Effort**: 8–14 hours
**Dependencies**: Python 3.14+ (already in use — `.python-version` is `3.14.2t`)
**Source**: `plan/rfc-tstring-dogfooding.md`, codebase audit of string-building patterns

---

## Why This Matters

Kida ships t-string support (`k(t"...")`) to users but doesn't use it internally, leaving the implementation undertested by real-world patterns and missing an opportunity to validate the feature's ergonomics.

1. **Undertested integration surface** — `k()` in `tstring.py` (282 lines) is only exercised by dedicated unit tests, not by the engine's own hot paths. Internal dogfooding would catch edge cases (circular imports, performance cliffs, format-spec interactions) that synthetic tests miss.
2. **No credible "when to use t-strings" guidance** — the RFC identifies that single-interpolation f-strings are ~3x faster than `k(t"...")` due to call overhead (~100ns). Without benchmark data from real internal conversions, documentation advice is theoretical.
3. **Missed escaping consistency** — `xmlattr()` (`utils/html.py:564`) manually calls `html_escape(str(val))` then wraps in an f-string. `k(t"...")` auto-escapes, which would eliminate the manual escape call and reduce the chance of a missed-escape bug.
4. **`_filter_debug` builds 6–12 f-strings then joins** — this is the exact pattern where t-strings should win on both clarity and performance.

By converting 3 internal candidates and benchmarking the results, we produce hard data for users and harden `k()` against real patterns.

### Evidence

| Layer/Source | Key Finding | Proposal Impact |
|-------------|-------------|-----------------|
| `parser/errors.py:58-97` | `_format()` builds header with 2 f-strings, then a multi-line f-string with 5 interpolations, plus conditional appends | FIXES — 5+ interpolation case where t-strings should break even or win |
| `utils/html.py:537-566` | `xmlattr()` loop: `html_escape(str(val))` + `f'{key}="{escaped}"'` — manual escape before f-string | FIXES — `k(t'{key}="{val}"')` auto-escapes `val`, eliminating manual escape call |
| `environment/filters/_debug.py:37-108` | `_filter_debug` accumulates 6–12 f-strings into `lines[]` then `"\n".join(lines)` | FIXES — classic list+join pattern that t-strings target |
| `tstring.py:241-281` | `k()` uses `getattr(interp, "value", interp)` for PEP 750 compatibility, plus `html_escape(str(val))` per interpolation | MITIGATES — dogfooding exercises the real `k()` code path, not test doubles |
| `.python-version` | `3.14.2t` (free-threaded) — native t-string support available | FIXES — no fallback path needed; native t-strings are the production path |

### Invariants

These must remain true throughout or we stop and reassess:

1. **Zero regression on Python 3.14**: All existing tests pass identically before and after conversion. No new failures.
2. **No circular imports**: `from kida.tstring import k` must not trigger transitive imports of the module being converted (parser, filters, utils).
3. **Performance within ±15%**: Converted code must not regress >15% vs baseline on its benchmark. If any candidate regresses >15%, revert that candidate and document the finding.

---

## Target Architecture

**Before** (current):
```
parser/errors.py   →  f-strings + manual string concat
utils/html.py      →  html_escape() + f-strings in loop
filters/_debug.py  →  f-strings → list → join
```

**After**:
```
parser/errors.py   →  k(t"...") for multi-interpolation format blocks
utils/html.py      →  k(t'{key}="{val}"') with auto-escape (no manual html_escape call)
filters/_debug.py  →  k(t"...") for each line, then join
```

**Verification**: `rg 'from kida.tstring import k' src/kida/` returns exactly 3 new import sites (parser/errors.py, utils/html.py, environment/filters/_debug.py).

---

## Sprint Structure

| Sprint | Focus | Effort | Risk | Ships Independently? |
|--------|-------|--------|------|---------------------|
| 0 | Establish baselines — benchmark the 3 candidates | 2h | Low | Yes (data only) |
| 1 | Convert `xmlattr()` — simplest candidate, auto-escape benefit | 2–3h | Low | Yes |
| 2 | Convert `_filter_debug` — list+join pattern, most interpolations | 2–3h | Low | Yes |
| 3 | Convert `ParseError._format()` — multi-line f-string, conditional blocks | 2–3h | Medium | Yes |
| 4 | Compare benchmarks, document findings, update RFC | 1–2h | Low | Yes |

---

## Sprint 0: Establish Baselines

**Goal**: Create benchmarks for the 3 candidates so we can measure whether t-string conversion helps, hurts, or is neutral.

### Task 0.1 — Create dogfooding benchmark file

Create `benchmarks/test_benchmark_dogfooding.py` with benchmarks for:
- `ParseError._format()` with a realistic multi-line error
- `xmlattr()` with 1, 5, and 10 attributes
- `_filter_debug()` with a list of 10 objects

**Files**: `benchmarks/test_benchmark_dogfooding.py` (new)
**Acceptance**: `uv run pytest benchmarks/test_benchmark_dogfooding.py --benchmark-only` runs and reports timings for all 3 groups.

### Task 0.2 — Save baseline

Run benchmarks and save baseline for comparison.

**Acceptance**: `uv run pytest benchmarks/test_benchmark_dogfooding.py --benchmark-save=dogfooding-baseline` succeeds and produces a baseline JSON.

---

## Sprint 1: Convert `xmlattr()`

**Goal**: Replace manual `html_escape()` + f-string with `k(t"...")` auto-escaping in the attribute loop. This is the highest-value candidate because it eliminates a manual escape call.

### Task 1.1 — Verify import safety

Confirm `from kida.tstring import k` in `utils/html.py` doesn't create a circular import. `tstring.py` imports `from kida.utils.html import html_escape`, so this is the same module — likely circular.

**Mitigation**: If circular, use late import inside `xmlattr()` or restructure. This must be resolved before proceeding.

**Files**: `src/kida/utils/html.py`, `src/kida/tstring.py`
**Acceptance**: `python -c "from kida.utils.html import xmlattr"` succeeds without ImportError.

### Task 1.2 — Convert the attribute formatting loop

Replace:
```python
escaped = html_escape(str(val))
parts.append(f'{key}="{escaped}"')
```
With:
```python
parts.append(k(t'{key}="{val}"'))
```

Note: `key` is the attribute name (already validated, should not be escaped). `val` is user data (must be escaped). Need to verify `k()` escapes `val` but passes `key` through. Since `k()` escapes all non-Markup interpolations, `key` will also be escaped — which is wrong for attribute names. This requires either:
- Using a hybrid: `f'{key}="{k(t"{val}")}"'` (only escape val)
- Wrapping `key` in `Markup` to skip escaping

**Files**: `src/kida/utils/html.py:537-566`
**Acceptance**:
- `uv run pytest tests/ -k "xmlattr"` passes
- `uv run pytest benchmarks/test_benchmark_dogfooding.py -k xmlattr --benchmark-compare=dogfooding-baseline` shows ±15% or better

### Task 1.3 — Tests

Verify existing xmlattr tests pass unchanged. Add one test confirming t-string path produces identical output to the previous f-string path.

**Acceptance**: `uv run pytest tests/ -k "xmlattr" -v` — all green, no new failures.

---

## Sprint 2: Convert `_filter_debug`

**Goal**: Replace the list+join+f-string pattern in `_filter_debug` with `k(t"...")` per line. This exercises the multi-interpolation case.

### Task 2.1 — Convert line building

Replace f-string lines like:
```python
lines.append(f"DEBUG {label_str}: <{type_name}[{len(value)}]>")
lines.append(f"  [{idx}] {item_repr}{none_warning}")
```
With:
```python
lines.append(k(t"DEBUG {label_str}: <{type_name}[{len(value)}]>"))
lines.append(k(t"  [{idx}] {item_repr}{none_warning}"))
```

Note: `_filter_debug` writes to stderr, not to HTML output. Auto-escaping is **unwanted** here — `<list[5]>` should stay as-is, not become `&lt;list[5]&gt;`. This means `k()` is the wrong tag for this use case. Options:
- Create a plain `t()` tag that concatenates without escaping
- Skip this candidate entirely
- Use `str.join` with format_map instead

**Decision needed in Sprint 0**: If `k()` always escapes, `_filter_debug` is NOT a valid candidate. Document this as a finding.

**Files**: `src/kida/environment/filters/_debug.py`
**Acceptance**: `uv run pytest tests/ -k "debug" -v` passes; benchmark within ±15%.

---

## Sprint 3: Convert `ParseError._format()`

**Goal**: Replace the multi-line f-string in error formatting with `k(t"...")`. This is the most complex candidate due to conditional blocks.

### Task 3.1 — Verify import safety

`parser/errors.py` → `from kida.tstring import k`. Check that `tstring.py` doesn't import anything from `parser/`.

**Files**: `src/kida/parser/errors.py`
**Acceptance**: `python -c "from kida.parser.errors import ParseError"` succeeds.

### Task 3.2 — Convert `_format()` method

The current method (lines 58-97) has:
- A 2-line f-string for `header`
- A multi-line f-string for `msg` (5 interpolations)
- Conditional appends for suggestion and docs URL

Convert the multi-line f-string block. Keep conditional appends as-is (they're single-interpolation).

Note: Same escaping concern — error messages should NOT be HTML-escaped. `k()` auto-escapes, which would corrupt error output (`<template>` → `&lt;template&gt;`). This means `k()` is also wrong here.

**Files**: `src/kida/parser/errors.py:58-97`
**Acceptance**: `uv run pytest tests/ -k "parse_error or parser" -v` passes; benchmark within ±15%.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Circular import: `html.py` ↔ `tstring.py` | High | High | Sprint 1, Task 1.1: test import chain before converting. If circular, use late import or extract `_escape_str` to a leaf module. |
| `k()` auto-escaping corrupts non-HTML output (debug, errors) | High | High | Sprint 0: validate which candidates actually benefit from auto-escaping. Only `xmlattr()` wants escaping. Others need a plain `t()` tag or should be skipped. |
| No measurable performance gain | Medium | Low | Sprint 0 baselines + Sprint 4 comparison. Negative result is still valuable — documents when NOT to use t-strings. |
| `k()` call overhead dominates for 1–2 interpolation cases | Certain | Low | Only convert multi-interpolation sites. Single f-strings stay as-is. |
| Python 3.13 fallback breaks | Low | Medium | `tstring.py` already has `try/except ImportError`. Converted code must guard with the same pattern or be 3.14+-only. |

---

## Success Metrics

| Metric | Current | After Sprint 1 | After Sprint 4 |
|--------|---------|----------------|-------------------|
| Internal `k()` usage sites | 0 | 1 (`xmlattr`) | 1–3 depending on findings |
| Manual `html_escape()` calls in converted code | 1 (`xmlattr`) | 0 | 0 |
| Benchmark delta vs baseline (xmlattr) | — | ±15% | Documented |
| Benchmark delta vs baseline (debug) | — | — | Documented (or "skipped — escaping mismatch") |
| "When to use t-strings" doc section | Absent | Absent | Published with data |

---

## Relationship to Existing Work

- **`rfc-tstring-dogfooding.md`** — supersedes — this epic replaces the RFC with a sprint-structured plan grounded in evidence. The RFC's candidate list and benchmark template are incorporated.
- **`rfc-c-escaping-extension.md`** — parallel — if `xmlattr()` conversion shows `k()` escaping as a bottleneck, the C extension RFC becomes higher priority.
- **`rfc-tstring-regex-fsm.md`** — completed — the `r()` tag is already shipped; this epic focuses on the `k()` tag.

---

## Critical Design Decision (Pre-Sprint 1)

**The `k()` tag always HTML-escapes.** This means:

| Candidate | Wants escaping? | Valid for `k()`? |
|-----------|----------------|-----------------|
| `xmlattr()` | Yes — attribute values must be escaped | **Yes** |
| `_filter_debug()` | No — writes to stderr, not HTML | **No** (would corrupt output) |
| `ParseError._format()` | No — error messages are plain text | **No** (would corrupt output) |

**Only 1 of 3 candidates is valid for `k()`.** The other 2 would require a new plain-concatenation tag (e.g., `t_concat()` or `plain()`) that processes t-strings without escaping. This is itself a design decision:

- **Option A**: Only convert `xmlattr()`. Document that `k()` is HTML-specific. 2 candidates produce "negative result" findings.
- **Option B**: Add a `plain()` tag to `tstring.py` that concatenates without escaping. Convert all 3 candidates with the appropriate tag.
- **Option C**: Use raw `Template.strings` + `Template.interpolations` concatenation directly (no tag function needed for non-escaping cases).

**Recommendation**: Option B — add `plain()` tag. It's 10 lines of code, validates t-string infrastructure for non-HTML contexts, and provides users a documented non-escaping alternative.

---

## Changelog

| Date | Change | Reason |
|------|--------|--------|
| 2026-04-12 | Initial draft | Evidence audit revealed escaping mismatch for 2 of 3 candidates |
