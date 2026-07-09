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

The runner and schema can be developed and smoke-tested on other platforms, but
issue #247 is not fully evidenced until its JSON is captured on the guarded
Linux 3.14t host. This document intentionally contains no local timing values.
