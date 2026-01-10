# RFC: Test Coverage Hardening

**Status**: Draft  
**Created**: 2026-01-09  
**Updated**: 2026-01-09  
**Author**: Bengal Contributors  

---

## Executive Summary

Raise Kida's automated test coverage from 78% to ≥90% with targeted additions that prioritize correctness-sensitive modules (analysis, parser, template, environment filters/tests, `tstring`). This RFC inventories current gaps from the latest coverage run and defines a phased plan to close them without refactoring runtime code.

**Key Metrics (current → target):**
- **Overall coverage**: 78% → ≥90%  
- **High-risk modules**: `analysis.dependencies` 46%, `analysis.purity` 51%, `environment.filters` 58%, `parser.statements` 68%, `template` 69%, `tstring` 13%, `environment.tests` 51%

---

## Current State (2026-01-09)

Command used:
```bash
PYTHONPATH=src pytest --cov=kida --cov-report=term-missing
```

Findings:
- Suite: 1441 tests (1420 passed, 17 skipped, 3 xfailed, 1 xpassed)
- Warnings: `PytestUnraisableExceptionWarning` with `KeyError: '__import__'` in async filter/global tests (`tests/test_kida_async_features.py`)
- Coverage hotspots (missed lines are concentrated in these modules):
  - `src/kida/analysis/dependencies.py` — 46% (e.g., 121-225, 320-340, 398-413, 546-552, 706-744)
  - `src/kida/analysis/purity.py` — 51% (e.g., 242-270, 416-435, 488-553, 590-651)
  - `src/kida/environment/filters.py` — 58% (e.g., 316-354, 493-539, 761-810, 994-1071)
  - `src/kida/parser/statements.py` — 68% (e.g., 280-371, 425-460, 496)
  - `src/kida/template.py` — 69% (e.g., 191-287, 654-664, 841-886, 967-978)
  - `src/kida/environment/tests.py` — 51% (e.g., 79-104, 168-183, 219-223)
  - `src/kida/tstring.py` — 13% (11-39)
  - Protocol stubs: `compiler/_protocols.py`, `parser/_protocols.py` at 0% (interfaces only)

---

## Goals

1. Increase overall coverage to ≥90% without reducing test reliability (no mass fixture skipping).
2. Cover high-risk control-flow branches in analyzer/purity, parser statement handling, template error paths, and environment filters/tests.
3. Add focused unit tests for `tstring` utilities and remaining small modules.
4. Stabilize async tests by eliminating `KeyError: '__import__'` unraisable warnings.
5. Ensure local/CI runs set `PYTHONPATH=src` (or editable install) so coverage is consistent.

### Non-Goals
- Refactoring production code solely for coverage.
- Broadly mocking internals in a way that hides regressions.

---

## Plan

### Phase 1 — Coverage Quick Wins (1-2 days)
- Add unit tests for `tstring` (constructors, formatting, error handling) to lift from 13% → ≥80%.
- Add narrow tests for `environment/tests.py` built-ins (is_defined, truthiness, comparisons) covering lines 79-183, 219-223.
- Add regression tests for `template.py` simple render/error branches (191-287, 654-664) using minimal templates.
- Fix async warning source in `tests/test_kida_async_features.py` by asserting/guarding `__import__` access; add a regression test to prevent recurrence.

### Phase 2 — Parser & Environment Branches (2-3 days)
- Extend parser statement tests to cover branches in `parser/statements.py` (280-371, 425-460, 496) including edge cases for `match`, `with`, and pipeline syntax.
- Add filter registry and loader edge-case tests for `environment/filters.py` (316-354, 493-539, 761-810, 994-1071) and `environment/tests.py` (remaining gaps).
- Add template error-path tests for late-bound variables, undefined filters, and pipeline failures (`template.py` ranges 841-886, 967-978).

### Phase 3 — Analysis Depth (3-5 days)
- Add scenario-based tests for `analysis/dependencies.py` covering include/extend chains, macro imports, and cycle detection (ranges 121-225, 320-340, 398-413, 546-552, 706-744).
- Add purity classification tests for side-effect detection and whitelists (`analysis/purity.py` ranges 242-270, 416-435, 488-553, 590-651).
- Add bytecode cache edge tests if needed to mop up remaining misses (low count).

### Phase 4 — Hardening & CI (1 day)
- Add a coverage threshold job (e.g., `pytest --cov=kida --cov-fail-under=90` with `PYTHONPATH=src`).
- Track module-level coverage deltas in CI output (term-missing).
- Document local run command in `README.md` for contributors.

---

## Acceptance Criteria

- Overall coverage ≥90% on CI using `pytest --cov=kida --cov-fail-under=90`.
- No `PytestUnraisableExceptionWarning` for async tests.
- High-risk modules improved:
  - `analysis.dependencies` ≥80%
  - `analysis.purity` ≥80%
  - `environment.filters` ≥80%
  - `parser.statements` ≥85%
  - `template` ≥85%
  - `tstring` ≥80%
- New tests are deterministic (no flakiness under `pytest -n auto --dist worksteal`).

---

## Risks & Mitigations

- **Flaky async tests**: Use explicit cleanup and key guards around globals to avoid unraisable exceptions.
- **Overfitting tests**: Prefer behavior-driven scenarios (rendering/parsing) over internal mocks.
- **Performance**: Large suites may lengthen CI; mitigate via `pytest -n auto` and focused parametrization.

---

## Tracking

- Owner: QA + Core Maintainers  
- Progress metric: Coverage % per module (reported from `--cov-report=term-missing` in CI)  
- Checkpoints: After each phase, re-run coverage and update this RFC status to reflect achieved targets.
