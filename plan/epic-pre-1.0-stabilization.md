# Kida Pre-1.0 Stabilization Rituals

Kida is moving from pre-1.0 feature turbulence to a framework-author-ready
surface. This is not a plan to cut a major release candidate; it is a plan to
turn the behaviors framework authors already depend on into visible, repeatable
project rituals. The stabilization posture is deliberately conservative: no new
runtime dependencies, public APIs, template tags, or config knobs unless they
are required to close a bug that blocks real users.

Current baseline after the `0.8.0` work on `main`:

- Pure Python remains the default contract; runtime dependencies stay empty.
- `make lint`, `make ty`, and the full test suite are the required local gates.
- Coverage currently targets the project floor in `pyproject.toml`; the
  stability gate should enforce the current 83% floor.
- Existing strict xfails should stay at zero for stabilization work.

## Phase 1: Stability Inventory and API Snapshot

Freeze the public framework-author surface before changing behavior.

- Add a public API snapshot test for:
  - `kida.__all__`
  - `ErrorCode` names and values
  - `Environment.__init__`
  - public `Template` render and metadata methods
  - metadata dataclass fields
  - CLI subcommands and flags
- Update API and CLI docs to name stable surfaces and separate them from
  internal or still-provisional surfaces.
- Treat snapshot changes as deliberate API changes that require changelog and
  docs updates in the same PR.

Acceptance:

- `make lint`, `make ty`, and focused tests pass.
- Snapshot tests fail when public contracts drift.

## Phase 2: Component and Metadata Contract Tests

Harden component validation and metadata for framework integration.

- Extend imported def validation tests for aliases, missing required props,
  unknown props, literal type mismatches, missing imported templates, and
  dynamic import skip behavior.
- Stabilize metadata across `list_defs()`, `def_metadata()`,
  `block_metadata()`, `template_metadata()`, inheritance, regions, slots, and
  CLI JSON output.
- Ensure `K-CMP-001` and `K-CMP-002` have docs entries with fix guidance.

Acceptance:

- Imported literal component validation is covered end to end.
- Dynamic imports are explicitly documented as skipped.

## Phase 3: Render, Sandbox, and Free-Threading Gates

Convert safety invariants into local verification gates.

- Add render-surface coverage meta-tests for every current render surface.
- Assert there are no active strict xfails.
- Add a fragment-render scaffold guard so block/fragment render methods use the
  shared scaffold path.
- Promote sandbox fuzz, bytecode-cache concurrency, LRU concurrency, and render
  stress tests into stability verification.

Acceptance:

- `PYTHON_GIL=0 make verify-stability` passes locally on 3.14t.
- Free-threaded shared state has an audit note for intentional sharing,
  locking, and copy-on-write behavior.

## Phase 4: Diagnostics and Docs Truth Audit

Make docs match actual behavior.

- Add an ErrorCode docs coverage test for every public `ErrorCode`, including
  `K-CMP-*`.
- Snapshot representative `kida check --validate-calls`,
  `kida components --json`, and error/warning formatting.
- Reconcile API, CLI, components, type-checking, sandbox, thread-safety, and
  Jinja2 migration docs with current behavior.

Acceptance:

- Every public diagnostic has docs, fix guidance, and stable formatting.

## Phase 5: Benchmark Baseline and Packaging Smoke

Collect performance evidence and package smoke tests.

- Refresh Linux 3.14t benchmark baselines using existing benchmark scripts for
  render, compile pipeline, streaming, inherited blocks, and concurrency.
- Add benchmark comparison instructions to release docs.
- Build wheel/sdist, install from the wheel in a clean temporary environment,
  and smoke-test import, render, CLI check, component metadata, and sandbox
  denial.
- Fail the stability gate on more than 5% compile/render/stream regression or more than 10%
  concurrency regression versus the committed Linux 3.14t baseline unless the
  PR updates the baseline with justification.

Acceptance:

- Any user-facing behavior change has docs or changelog coverage.
- The repo has enough evidence to make a release decision later without
  reconstructing what was tested.

## Stability Gate Target

`make verify-stability` should become the single local stabilization gate and
run:

- `ruff check`
- `ruff format --check`
- `ty`
- full pytest
- coverage with `--cov-fail-under=83`
- sandbox fuzz and thread-safety tests
- `PYTHON_GIL=0` free-threading pass where supported
- wheel build/install smoke test

`make verify-rc` may remain as an alias, but the ritual is about stability
evidence rather than committing the project to a specific version tag.
