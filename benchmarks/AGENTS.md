<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: benchmarks

Represent honest evidence for compiler, renderer, escaping, streaming, caching, and free-threaded scaling claims.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Cold-start and benchmark runners preserve preflight, provenance, timing/memory separation, and output schema before timing claims. | P1 | machine-backed | `uv run pytest tests/test_cold_start_phase_benchmark.py -q` (`benchmark-sanity`) |
| Published performance claims name platform, Python build, GIL status, command, and Linux baseline provenance. | P1 | manual | benchmarks/RESULTS.md · `## Environment` |

## Guardrails

- Output-sanity precedes timing and thresholds name variance rationale.
- Linux 3.14t committed baselines are authoritative; Darwin runs are development evidence only.

## Edges

- measures → **compiler** (compile and render hot paths)
- gated-by → **github** (Linux comparison workflow)

## Owns

- **code:** `benchmarks/`, `scripts/benchmark_compare.sh`, `scripts/benchmark_baseline.sh`
- **tests:** `tests/test_cold_start_phase_benchmark.py`
- **docs:** `benchmarks/RESULTS.md`, `docs/stability-gate.md`

## Do Not

- Replace Linux baselines with local Darwin results.
- Benchmark unequal output or unexplained changed workloads.
