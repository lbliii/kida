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

This runs lint, format check, `ty`, full pytest with `--cov-fail-under=83`,
focused render/sandbox/concurrency safety tests under `PYTHON_GIL=0`, and a
wheel/sdist build plus clean-venv package smoke test.

`make verify-rc` remains an alias for contributors who already use that name.

The package smoke test verifies:

- import from the installed wheel
- template render
- CLI `check --validate-calls`
- CLI `components --json`
- component metadata
- sandbox denial for blocked reflection attributes

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
