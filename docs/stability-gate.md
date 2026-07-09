# Kida Stability Gate

Use this checklist when a change touches public contracts, diagnostics,
packaging, render surfaces, sandbox behavior, or free-threading assumptions.
It is a project ritual for keeping Kida boring in production, not a promise
that a major release is imminent.

## Local Stability Gate

Run the full local gate:

```bash
make verify-stability
```

This runs lint, format check, `ty`, full pytest across `tests/` and `examples/`
with `--cov-fail-under=83`, focused render/sandbox/concurrency safety tests
under `PYTHON_GIL=0`, and a wheel/sdist build plus clean-venv package smoke
test.

The 83% value is the active local combined coverage floor with branch
measurement enabled; it is not a claim of 90% branch coverage. The current
measured branch baseline, exact test-node ownership, and unresolved
high-consequence paths are recorded in the versioned
[critical-contract assurance inventory](audit/critical-contract-assurance-v1.md).
Changing the threshold or CI enforcement remains a separate policy decision.

Ruff lint and format checks are repository-wide (`ruff check .` and
`ruff format --check .`) in both Makefile targets and CI. This currently covers
all tracked Python under `src/kida/`, `tests/`, `examples/`, `benchmarks/`, and
`scripts/`. Generated builds, virtual environments, caches, and other
tool-managed directories remain intentionally excluded by Ruff's standard
discovery rules.

The `Type Check (ty)` job in `.github/workflows/tests.yml` is the authoritative
CI type-check lane. It keeps raw `ty` failure output visible and adds the
rendered JUnit report; no separate workflow runs the same check.

`make verify-rc` remains an alias for contributors who already use that name.

The package smoke test verifies:

- import from the installed wheel
- template render
- CLI `check --validate-calls`
- CLI `components --json`
- component metadata
- sandbox denial for blocked reflection attributes

## Scheduled Free-Threading Stress

The required `Thread Safety` CI job runs one deterministic randomized seed on
every pull request. Weekly and manual CI runs expand the same test to 25 seeds.
Each seed assigns ten supported shared-runtime operations to different workers
for 40 barrier-synchronized rounds, covering 400 operations without sleep-based
correctness assertions. The weekly window therefore covers 10,000 operations
across distinct role, key, invalidation, and submission schedules.

Pytest includes the seed in each test ID and the test prints it before execution.
Reproduce a reported seed locally with the GIL disabled:

```bash
PYTHON_GIL=0 KIDA_STRESS_SEED=17 KIDA_STRESS_RUNS=1 \
  uv run pytest tests/test_randomized_thread_stress.py \
  -vv -s --tb=short --timeout=120
```

Increase `KIDA_STRESS_RUNS` to exercise consecutive seeds beginning at
`KIDA_STRESS_SEED`. The accepted weekly window is 25 consecutive seeds; larger
manual windows are allowed up to 100 seeds. A failure is actionable only with
its seed, Python build, GIL status, and failing operation/assertion preserved.

### Periodic debug-runtime protocol

Weekly and manual workflows repeat the same 25-seed window under Python
development mode with allocator debug hooks and `faulthandler`, while retaining
`PYTHON_GIL=0`. The test first asserts that development mode, fault handling,
`PYTHONMALLOC=debug`, and GIL-disabled execution are all active; a misconfigured
lane therefore fails before claiming deeper evidence.

Reproduce the protocol locally:

```bash
PYTHON_GIL=0 PYTHONDEVMODE=1 PYTHONFAULTHANDLER=1 PYTHONMALLOC=debug \
KIDA_REQUIRE_DEBUG_RUNTIME=1 KIDA_STRESS_SEED=0 KIDA_STRESS_RUNS=25 \
  uv run python -X dev -m pytest tests/test_randomized_thread_stress.py \
  -vv -s --tb=short --timeout=120
```

This is a **debug-runtime protocol**, not ThreadSanitizer and not a CPython
`Py_DEBUG` build. It exercises Python's development-mode runtime checks on the
managed free-threaded interpreter without implying native data-race detection.
Adopt a true sanitizer or combined free-threaded debug-build lane only when a
maintained, reproducible runner artifact is available.

## Release Automation Gate

Before running the release target, merge the release-prep PR and work from a
clean checkout whose `HEAD` matches `origin/main`. The release target expects
the version in `pyproject.toml` to match a source page at
`site/content/releases/<version>.md` and creates `v<version>` from the merged
main commit:

```bash
make gh-release
```

The target fails if the worktree is dirty, if `HEAD` differs from `origin/main`,
if the GitHub release already exists, or if an existing remote version tag points
at a different commit. It pushes the version tag, creates the GitHub release from
the curated site release notes, and then moves the floating major action tag
with `make action-tag`.

After `make gh-release`, verify:

- `refs/heads/main`, `refs/tags/v<version>`, and `refs/tags/v<major>` point at
  the same release commit
- the GitHub release body still contains the curated release notes
- the `Upload Python Package` release workflow succeeded
- `https://pypi.org/pypi/kida-templates/<version>/json` returns the released
  wheel and sdist metadata
- the docs release page is reachable under
  `https://lbliii.github.io/kida/releases/<version>/`

The `Release Notes` workflow dogfoods Kida's release-note templates on release
events, but release events do not rewrite the curated GitHub release body or
commit changelog changes. Use its manual `workflow_dispatch` mode when a
maintainer explicitly wants to regenerate release-note/changelog output for a
tag and target branch.

## Benchmark Evidence

Linux 3.14t benchmark baselines are the performance comparison baseline. Darwin
or other local baselines are useful for development, but they must not replace
the committed Linux baseline used by CI.

Refresh the Linux baseline with the existing workflow or on a Linux 3.14t host:

```bash
./scripts/benchmark_baseline.sh baseline
```

Compare a candidate against the committed baseline:

```bash
./scripts/benchmark_compare.sh baseline
```

For stricter stability evidence, run the benchmark families that cover the
main runtime promises:

```bash
uv run pytest \
  benchmarks/test_benchmark_compile_pipeline.py \
  benchmarks/test_benchmark_render.py \
  benchmarks/test_benchmark_streaming.py \
  benchmarks/test_benchmark_inherited_blocks.py \
  benchmarks/test_benchmark_concurrent.py \
  --benchmark-only -v
```

Regression thresholds:

- fail on more than 5% compile/render/stream regression
- fail on more than 10% concurrency regression
- update the Linux baseline only with an explicit baseline drift rationale

Include benchmark evidence in the PR when it matters:

- Linux platform and Python build
- GIL status
- benchmark command
- compare summary
- any baseline updates and why they are safe

## Downstream Pilot Evidence

Changes that add or alter downstream-observable component or runtime contracts
also classify whether they need a change-specific consumer pilot. Follow the
[downstream pilot evidence policy](downstream-pilot-policy.md) for the consumer
matrix, minimum fixture and provenance proof, failure protocol, coordinated
changes, and allowed `No downstream pilot` reasons.

The standing [downstream canaries](audit/downstream-canaries.md) provide broad
regression coverage. A green canary counts as pilot evidence only when its
identified fixture actually exercises the changed contract and the run records
the candidate and consumer provenance. This policy adds no workflow or
required-check gate.
