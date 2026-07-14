# Cold-Start Phase Contract

Status: active measurement baseline methodology

Tracking: [GitHub issue #247](https://github.com/lbliii/kida/issues/247),
part of [epic #167](https://github.com/lbliii/kida/issues/167)

## Purpose

Cold start is not one number. Kida needs to distinguish interpreter launch,
public imports, environment construction, source compilation, bytecode-cache
loading, and steady-state rendering before changing import boundaries. The
machine-readable runner is
[`benchmarks/benchmark_cold_start_phases.py`](../../benchmarks/benchmark_cold_start_phases.py).

This contract is measurement-only. It sets no regression threshold, changes no
import behavior, and does not update public comparison claims.

## Authoritative capture

Run on Linux CPython 3.14 free-threading with the GIL disabled:

```console
PYTHON_GIL=0 uv run python benchmarks/benchmark_cold_start_phases.py \
  --require-linux-3-14t \
  --warmups 3 \
  --samples 20 \
  --memory-samples 5 \
  --output /tmp/kida-cold-start-linux.json
```

The guard rejects a non-Linux host, a non-CPython interpreter, a Python version
other than 3.14, a non-free-threaded build, or a run with the GIL enabled. Runs
without the guard remain useful for development, but their JSON is marked
`development-only` and `claim_eligible: false`. In particular, local Darwin
measurements are not public competitive evidence.

The output records raw samples plus median, nearest-rank p95, minimum, and
maximum. It also records OS/architecture, Python implementation/build/cache tag,
GIL state, CPU count, Kida version, executable, timestamp, and Git revision.
Keep the raw JSON with the Linux benchmark run or PR evidence; do not copy a
local development number into `RESULTS.md` or the README. Public evidence and
claim publication are separately governed by #199.

## Phase definitions

Each phase after process startup runs in a fresh child interpreter. Imports or
setup excluded by the phase definition happen before its timer.

| Phase | Included in `elapsed_ms` | Excluded |
|---|---|---|
| `process_startup` | Parent-observed wall time for `python -I -S` plus a minimal RSS probe | Kida and site-package import |
| `import_kida` | Clean-process `import kida` | Process startup |
| `import_environment` | Clean-process `from kida import Environment` | Process startup |
| `environment_construction` | `Environment()` | Kida import and process startup |
| `first_source_render` | `Environment.from_string(source)` plus first `render()` | Import and environment construction |
| `first_bytecode_cache_render` | First `get_template()` plus `render()` in a clean process against an untimed prepopulated cache | Import, environment construction, and cache population |
| `warm_render` | Second render of an already compiled in-process template | Import, construction, compile, and first render |

The fixed template renders a heading and a three-item loop. Before any timed
warmup or sample, an untimed preflight proves exact source-render, warm-render,
and bytecode-cache output and confirms that cache population created an artifact.
Every timed rendering worker checks the same exact output again.

## Closure and memory

After each timed phase, the worker records all loaded `kida` module names and
counts unique physical lines in their Python source files. Closure collection
happens after the timer.

Timing samples do not enable `tracemalloc`; enabling it materially distorts
imports and compilation. Separate memory samples record:

- `python_peak_bytes`: peak traced Python allocation during the isolated phase;
- `process_peak_rss_after_bytes`: cumulative process peak RSS at phase end;
- `process_peak_rss_growth_bytes`: growth in the process peak across the phase.

`ru_maxrss` is normalized to bytes (Darwin reports bytes; Linux reports KiB).
Process RSS includes the benchmark worker's standard-library driver. The
tracemalloc figure is the phase-isolated allocation measurement; neither value
should be described as total retained application memory.

## Existing benchmark blind spot

Both `benchmarks/benchmark_cold_start.py` and
`benchmarks/test_benchmark_cold_start.py` import Kida before assigning their
`_start` timer. Their historical “cold-start” values measure environment
construction plus template load/render, not `import kida` plus first render.
They remain useful for their existing Kida/Jinja2 scenario, but they are not the
complete #167 phase contract and must not be used to attribute import cost.

## Interpretation

- Compare phase with phase; do not subtract independently sampled noisy totals
  and call the difference causal.
- Inspect raw samples and environment metadata before accepting a median shift.
- Treat module and LOC closure as diagnostic evidence, not a performance proxy.
- Any lazy-import, AOT, cache, or hot-path change belongs in a later child issue
  with this runner used for before/after evidence.

## Current evidence status

Issue #247's guarded baseline candidate was captured on 2026-07-13. The raw
machine-readable report is
[`2026-07-13-linux-aarch64-linuxkit.json`](../../benchmarks/results/cold-start/2026-07-13-linux-aarch64-linuxkit.json).
It contains all raw samples, exact module lists, memory samples, environment
metadata, and summary statistics; a focused test preserves the committed
artifact's schema, provenance, sanity result, and sample counts.

### Capture provenance

- Kida 0.12.0 at commit
  [`79b5586`](https://github.com/lbliii/kida/commit/79b5586982acdfa8c0d3a8af06a2cc53ac932579).
- CPython 3.14.6 free-threaded aarch64 build with `PYTHON_GIL=0`; the runtime
  reported `gil_enabled: false` and `free_threading_build: true`.
- LinuxKit 6.10.14 in Docker Desktop 28.2.2 on Apple Silicon, with 11 virtual
  CPUs and 18,833,428,480 bytes of VM memory.
- Pinned runner image
  `ghcr.io/astral-sh/uv@sha256:1107ab06cc316f42650d7e77b42f45620ab97e03eabc39fac11b717fe95921ef`.
  The disposable container installed `git` for exact checkout provenance,
  copied the read-only checkout only for package-metadata installation, and
  ran the benchmark against the mounted source tree.
- Three warmups, twenty timing samples, and five separately traced memory
  samples per Kida phase. Process startup has no traced-memory sample by
  design. The untimed output/cache preflight passed before sampling.

The Linux and free-threading guards passed, so the runner correctly labels the
report `baseline-candidate`. Because LinuxKit was virtualized by a Darwin host,
this is an internal phase-contract baseline, not a dedicated benchmark-host or
public competitive result. It does not update `benchmarks/RESULTS.md`, the
README comparison, or any regression threshold. A public claim under #199
still requires a separately governed capture on the documented Linux benchmark
host.

### Summary

| Phase | Median | p95 | Kida modules / source LOC | Median Python peak | Median process peak RSS |
|---|---:|---:|---:|---:|---:|
| Process startup | 6.771 ms | 7.421 ms | 0 / 0 | n/a | 43.99 MiB |
| `import kida` | 51.867 ms | 60.847 ms | 43 / 15,426 | 8.10 MiB | 49.97 MiB |
| `from kida import Environment` | 56.605 ms | 62.134 ms | 43 / 15,426 | 8.10 MiB | 49.97 MiB |
| `Environment()` | 1.045 ms | 2.009 ms | 45 / 16,165 | 238.30 KiB | 49.97 MiB |
| First source compile + render | 65.789 ms | 71.978 ms | 93 / 33,841 | 6.01 MiB | 51.82 MiB |
| First bytecode-cache render | 24.569 ms | 27.508 ms | 53 / 17,263 | 1.84 MiB | 49.97 MiB |
| Warm render | 0.0147 ms | 0.0166 ms | 93 / 33,841 | 2.58 KiB | 49.97 MiB |

These are isolated phase measurements, not an additive end-to-end total. The
module/LOC values describe post-phase closure, while process RSS is cumulative
peak RSS for each fresh worker. The raw report remains authoritative for exact
values and sample-level inspection.
