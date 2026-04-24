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
