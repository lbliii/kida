# Release Roadmap: Kida 0.10.0

**Status**: Release branch candidate prepared; final local gates passed; publishing not performed
**Created**: 2026-05-30
**Target theme**: Structured diagnostics and release-readiness hardening
**Baseline**: `origin/main` at `66cf8ec` (`[codex] Improve UndefinedError diagnostics for framework views (#132)`)

## Objective

Ship the post-0.9.0 structured diagnostics work as a focused 0.10.0 release,
without mixing in new syntax, new runtime dependencies, new schema versions, or
large-app ergonomics features that still need separate approval.

## Research Basis

- Initial audit found `pyproject.toml` at `0.9.0`; release prep now updates the
  project metadata and lockfile to `0.10.0`.
- Initial local audit before fetching remote state found six post-`v0.9.0`
  diagnostics commits: structured undefined diagnostics, preserved undefined
  attribution, render surface diagnostic parity, a standalone diagnostic HTML
  page, public docs, and the coalescing line-marker contract. Remote `main` now
  carries that work as squash commit `66cf8ec` from PR #132, so the release
  branch is based on current `origin/main` instead of replaying the pre-squash
  local history.
- Focused diagnostics tests pass, and `make lint` / `make ty` are clean on the
  current baseline.
- `CHANGELOG.md` initially had an empty `[Unreleased]` section; release prep now
  includes a dated `0.10.0` changelog entry and published release-page source.

## Steward Signals

### Planning

- Steward: Planning
- Area: Release scope
- Severity: P1
- Invariant: Plans sequence real work and do not smuggle stop-and-ask changes.
- Evidence: The active commits are diagnostics-only; large-app ergonomics is
  still proposed and contains public API/open-question items.
- User Impact: A focused release is reviewable and avoids making unrelated
  promises.
- Required Fix: Treat 0.10.0 as diagnostics hardening; defer new validation
  APIs, schemas, and framework policies.
- Required Proof: Changelog entry, roadmap record, focused tests, lint, and ty.
- Collateral: `CHANGELOG.md`, docs pages touched by diagnostics.
- Confidence: High

### Runtime

- Steward: Runtime
- Area: Exception contracts
- Severity: P1
- Invariant: Public errors preserve template names, source locations, hints, and
  zero-dependency rendering helpers.
- Evidence: `UndefinedError.to_diagnostic()` exposes location, snippets, hints,
  stacks, docs URL, and escaped HTML/Markdown renderers.
- User Impact: Framework debug pages can stop scraping terminal-formatted text.
- Required Fix: Do not export new top-level diagnostic dataclasses in this
  release unless explicitly approved; document the current method-based access.
- Required Proof: `tests/test_diagnostics_contract.py` and public API snapshot.
- Collateral: Error handling and undefined-variable docs.
- Confidence: High

### Template Runtime

- Steward: Template Runtime
- Area: Render-mode diagnostic parity
- Severity: P1
- Invariant: Full render, streaming, imported components, and slot caller bodies
  attribute failures to the template line users can edit.
- Evidence: Existing focused tests cover coalesced output source lines, imported
  slot errors, component stacks, streaming runtime enhancement, HTML pages, and
  Markdown diagnostics.
- User Impact: Users debugging generated code see actionable template source,
  not misleading Python frames.
- Required Fix: Keep diagnostic tests in the release gate; add more render-mode
  parity only if failures appear.
- Required Proof: Focused diagnostics suite and full test/coverage gate.
- Collateral: Troubleshooting docs mention caller-template attribution for slots.
- Confidence: High

### Compiler

- Steward: Compiler
- Area: F-string coalescing source locations
- Severity: P1
- Invariant: Hot-path coalescing must not erase source mapping.
- Evidence: `fix: declare coalescing line marker contract` plus a test asserting
  undefined diagnostics remain on the correct template line with coalescing on.
- User Impact: Optimized templates remain debuggable.
- Required Fix: No further compiler optimization in this release without
  benchmark or explicit no-benchmark rationale.
- Required Proof: Existing coalescing diagnostic test; no benchmark required for
  source-map-only hardening.
- Collateral: Changelog names the source-location fix.
- Confidence: Medium-high

### Static Analysis

- Steward: Static Analysis
- Area: Diagnostic/code contract
- Severity: P2
- Invariant: Codes and machine-readable diagnostics stay documented and
  snapshotable.
- Evidence: `test_every_error_code_is_documented()` covers all `ErrorCode`
  anchors.
- User Impact: CI and agents can link users to stable remediation docs.
- Required Fix: Keep every new code documented before release.
- Required Proof: Diagnostics contract tests.
- Collateral: `site/content/docs/errors.md`.
- Confidence: High

### Docs Site

- Steward: Documentation Site
- Area: Public diagnostic docs
- Severity: P1
- Invariant: Public docs match current API names, tuple shapes, and render
  behavior.
- Evidence: Error-handling docs now describe `to_diagnostic()` and framework
  debug-page usage; a docs typo incorrectly referenced `ErrorCode.K_RUN_001`
  before this roadmap pass.
- User Impact: Framework authors can copy examples without runtime errors.
- Required Fix: Keep docs examples aligned with actual exception attributes.
- Required Proof: Docs source review and docs build when release collateral is
  finalized.
- Collateral: `site/content/docs/usage/error-handling.md`,
  `site/content/docs/troubleshooting/undefined-variable.md`.
- Confidence: High

### Tests

- Steward: Test Corpus
- Area: Release evidence
- Severity: P1
- Invariant: User-facing diagnostics need focused assertions and release gates.
- Evidence: Focused diagnostics suite passes locally.
- User Impact: Regressions in escaping, attribution, or stack context fail before
  release.
- Required Fix: Run full release-relevant gates before tagging.
- Required Proof: `make lint`, `make ty`, diagnostics tests, full test coverage;
  `make verify-stability` for final release candidate.
- Collateral: None beyond test output; no fixtures changed.
- Confidence: High

### Benchmark

- Steward: Benchmark
- Area: Performance evidence
- Severity: P3
- Invariant: Hot-path claims require benchmarks, but source-mapping fixes do not
  need new public performance claims.
- Evidence: The current changes do not advertise speedups.
- User Impact: Avoids noisy benchmark churn for a diagnostics release.
- Required Fix: No benchmark update unless a compiler/render hot-path change is
  added after this plan.
- Required Proof: Explicit no-benchmark rationale in release notes or PR body.
- Collateral: no collateral: no performance claim or baseline change.
- Confidence: Medium

### GitHub Workflow

- Steward: GitHub Workflow
- Area: Release mechanics
- Severity: P2
- Invariant: Release/publish and floating action tag behavior must not change
  casually.
- Evidence: No workflow changes are needed for a diagnostics release.
- User Impact: Existing release automation remains stable.
- Required Fix: Use existing `make verify-stability`, release, and action-tag
  process; do not alter workflows.
- Required Proof: Local gate output and CI on the release PR.
- Collateral: no collateral: workflows unchanged.
- Confidence: High

## Convergence

All consulted stewards converge on a narrow 0.10.0: ship diagnostics hardening,
document it, and verify release gates. No steward requires new syntax, public
configuration, schemas, workflow permissions, or dependencies for this release.

## Minority Reports

- Large-app ergonomics remains important, but it should not be bundled into
  0.10.0 unless a specific approved implementation is already complete and
  covered by docs/tests. It has open questions around API shape and suppression
  policy.
- Benchmark steward does not require a new baseline for current diagnostics work,
  but would object if later 0.10.0 changes alter compiler or render hot paths
  while skipping performance evidence.

## Ranked Backlog

1. Release collateral for diagnostics: update `CHANGELOG.md`, docs examples, and
   this roadmap.
2. Verification: run focused diagnostics tests, `make lint`, `make ty`, full
   test/coverage gate, safety/concurrency tests, docs build, and package smoke
   before tagging.
3. Release notes: maintain `site/content/releases/0.10.0.md` with the final
   release date and user-facing upgrade notes.
4. Optional hardening: add `TemplateRuntimeError.to_diagnostic()` only after a
   public-contract check-in, because it widens the programmatic surface beyond
   the current undefined-error implementation.
5. Post-release: resume `plan/epic-large-app-ergonomics.md` starting with
   route-agnostic context/catalog checks that already have evidence.

## Not Now

- No `TemplateDiagnostic` top-level export without explicit public API approval.
- No new CLI flags or `Environment(...)` knobs.
- No privacy-lint suppression/config surface.
- No public render-packet schema.
- No schema or report-template changes.
- No workflow, publish, or action-tag behavior changes.
- No benchmark baseline churn unless later code changes affect hot paths.

## Parity Matrix

| Contract | API/CLI | Programmatic | Protocol | Schema/Types | Docs | Examples | Tests |
|---|---|---|---|---|---|---|---|
| Undefined diagnostics | no CLI change | `UndefinedError.to_diagnostic()` | none | internal dataclasses only | error handling, troubleshooting | no new example | diagnostics contract |
| Source attribution | no CLI change | exception fields/snippets | none | none | troubleshooting | no new example | coalescing, slots, streaming |
| HTML/Markdown renderers | no CLI change | diagnostic format helpers | none | none | error handling | no new example | escaped output assertions |
| Release process | existing Makefile | none | none | none | changelog/release notes | no new example | lint, ty, tests, verify-stability |

## Execution Record

- 2026-05-30: `uv run pytest tests/test_diagnostics_contract.py` passed.
- 2026-05-30: `make lint` passed.
- 2026-05-30: `make ty` passed.
- 2026-05-30: `uv run pytest tests/test_diagnostics_contract.py tests/test_public_api_snapshot.py` passed.
- 2026-05-30: `make docs` initially built 262 pages with one generated autodoc
  `/llms.txt` health warning. After release-page and metadata updates, `make
  docs` built 270 pages with clean health output.
- 2026-05-30: `make test-cov` passed: 4,279 passed, 5 skipped, 84.14% coverage against the 83% floor.
- 2026-05-30: `make format-check` passed.
- 2026-05-30: `make package-smoke` passed against the prepared `0.10.0` package metadata.
- 2026-05-30: `make test-safety` passed under `PYTHON_GIL=0`: 131 passed.
- 2026-05-30: Version metadata updated to `0.10.0` in `pyproject.toml` and
  `uv.lock`.
- 2026-05-30: `site/content/releases/0.10.0.md` added.
- 2026-05-30: Focused release verification passed against 0.10.0 metadata:
  diagnostics contract, public API snapshot, compiler AST baseline, and async
  streaming exception contract.
- 2026-05-30: Final `make test-cov` passed: 4,279 passed, 5 skipped, 84.13%
  coverage against the 83% floor.
- 2026-05-30: Final `make verify-stability` passed: lint, format-check, ty,
  full coverage, safety, and package smoke all completed successfully against
  the prepared `0.10.0` release candidate.
- 2026-05-30: README and installation docs updated for `0.10.0` upgrade/version
  collateral; `make docs` rebuilt the site successfully with clean health checks.
- 2026-05-30: After fetching, remote `main` was at `66cf8ec` and the local
  pre-squash history diverged. Release prep was replayed onto
  `codex/release-0.10.0` from current `origin/main` to avoid publishing the
  duplicate pre-squash history. Remote tag push, GitHub release, PyPI publish,
  and floating action tag update remain pending.
- 2026-05-30: Origin-main-based focused verification passed:
  `uv run pytest tests/test_diagnostics_contract.py tests/test_public_api_snapshot.py tests/test_kida_async_rendering.py::TestAsyncExceptionPropagation::test_error_in_async_iterable_propagates`
  reported 15 passed.
- 2026-05-30: Origin-main-based docs verification passed: `make docs` found no
  pending site changes and completed with clean health checks.
- 2026-05-30: Origin-main-based final `make verify-stability` passed: lint,
  format-check, ty, full coverage, safety, and package smoke completed
  successfully. Coverage summary: 84.1% against the 83% floor.
