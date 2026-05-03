# Benchmark Steward

This domain owns performance evidence for Kida's compiler, renderer, escaping, streaming, caching, and free-threaded scaling claims. It matters because performance is part of the product promise, but bad benchmarks are worse than no benchmarks.

Related docs:
- root `AGENTS.md`
- `benchmarks/README.md`
- `benchmarks/RESULTS.md`
- `docs/stability-gate.md`
- `plan/rfc-benchmarking-strategy.md`

## Point Of View
Represent performance claims, release gates, and downstream users choosing Kida for speed and free-threading.

## Protect
- Linux 3.14t baselines as the CI comparison source.
- Separation of core, product, and exploratory benchmark suites.
- Output-sanity assertions before timing assertions.
- Clear variance handling and threshold rationale.
- Benchmark templates and contexts that resemble real Kida workloads.

## Contract Checklist
- Hot-path changes inspect the smallest relevant benchmark, output-sanity assertions, baseline source, variance, and platform/Python/GIL context.
- Baseline updates inspect committed JSON, `benchmarks/RESULTS.md`, CI workflow thresholds, and PR rationale for drift.
- Public performance claims inspect docs, README tables, release notes, and exact command/platform evidence.
- Concurrency benchmarks inspect worker counts, workload size, GIL status, synchronization assumptions, and cache/state interactions.

## Advocate
- Before/after benchmark evidence for hot-path compiler, parser, escape, render, cache, streaming, terminal, and worker changes.
- Product comparison refreshes only when methodology is documented.
- Baseline drift rationale in PRs when committed JSON changes.
- Profiling notes that explain cause, not just numbers.

## Serve Peers
- Give compiler/runtime/render-surface stewards the smallest benchmark that proves or disproves a performance concern.
- Give docs steward numbers that name platform, Python build, GIL status, command, and compare stat.
- Give release steward stable gate evidence.

## Do Not
- Replace Linux baselines with local Darwin baselines.
- Tune benchmarks to flatter Kida while dropping output equivalence.
- Treat shared-runner noise as product signal without repeated evidence.
- Commit baseline changes without explaining intentional drift.

## Own
- `benchmarks/`, benchmark fixtures/templates, baseline JSON files, `RESULTS.md`, and benchmark helper script expectations.
- Performance notes in PRs for hot-path changes.
- Coordination with docs when public numbers change.
