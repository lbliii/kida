## Baseline Drift Rationale

**Before (main):** No baseline files existed. Benchmarks ran but had no regression gate.

**After (this PR):** Establishes `benchmarks/Linux-CPython-3.14-64bit/0001_baseline.json` and `benchmarks/Darwin-CPython-3.14-64bit/0001_baseline.json` from CI/local runs.

**Why drift is expected:** This is initial baseline establishment, not a regression. The 0.2.5 release adds the PyPI publish workflow with a regression gate; these baselines are the first snapshot against which future changes will be compared.

**Why safe to adopt:** Baseline capture is from the current benchmark suite (render, features, include depth, inheritance, introspection, output sanity). No performance regressions; this PR sets the reference point for subsequent releases.
