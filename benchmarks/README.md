# Kida Benchmarks

Performance comparison between Kida and Jinja2 on **Python 3.14 free-threading**.

> Numbers below are from `test_benchmark_full_comparison.py` (inline templates,
> Python 3.14.2 free-threading, Apple Silicon).
> For file-based template benchmarks, see `test_benchmark_render.py`.

## Quick Results

### Single-Threaded Performance (Inline Templates)

| Template | Kida | Jinja2 | Kida Advantage |
|----------|------|--------|----------------|
| **Minimal** (`{{ name }}`) | 4.53µs | 5.13µs | **1.13x faster** |
| **Small** (loop + filter) | 7.66µs | 10.71µs | **1.40x faster** |
| **Medium** (conditionals + loops) | 9.41µs | 11.82µs | **1.26x faster** |

### Single-Threaded Performance (File-Based Templates)

| Template | Kida | Jinja2 | Kida Advantage |
|----------|------|--------|----------------|
| **Minimal** (`{{ name }}`) | 4.04µs | 5.28µs | **1.31x faster** |
| **Small** (loop + filter) | 6.77µs | 9.78µs | **1.44x faster** |
| **Medium** (~100 vars) | 210.57µs | 363.14µs | **1.72x faster** |
| **Large** (1000 loop items) | 1.59ms | 4.03ms | **2.53x faster** |
| **Complex** (3-level inheritance) | 18.93µs | 29.33µs | **1.55x faster** |

**Takeaway**: Kida is faster across the board. The advantage grows with template size — 2.53x on large templates due to the StringBuilder pattern.

---

### Concurrent Performance (Free-Threading)

Same total work (100 renders of medium template), distributed across workers:

| Workers | Kida | Jinja2 | Kida Advantage |
|---------|------|--------|----------------|
| **1** (baseline) | 1.25ms | 1.48ms | **1.18x faster** |
| **2** | 0.87ms | 0.98ms | **1.12x faster** |
| **4** | 0.90ms | 1.02ms | **1.13x faster** |
| **8** | 1.68ms | 1.62ms | ~same |

**Takeaway**: Kida is faster at all worker counts up to 4. At 8 workers, threading overhead dominates for both engines on this workload size.

> Concurrent benchmarks use `pedantic(rounds=5)` and have higher variance than
> single-threaded benchmarks. Median values are reported above for stability.

---

### Scaling Efficiency

| Engine | 1→2 workers | 1→4 workers | 1→8 workers |
|--------|-------------|-------------|-------------|
| **Kida** | 1.44x speedup | 1.39x speedup | ~0.7x ⚠️ |
| **Jinja2** | 1.51x speedup | 1.45x speedup | ~0.9x ⚠️ |

**Takeaway**: Both engines scale well up to 4 workers. At 8 workers, threading overhead exceeds the parallelism gains for this workload (100 renders of a small inline template). For real-world workloads with heavier templates, scaling continues further.

---

## Why Kida Scales Better

### Kida's Thread-Safe Design

1. **Copy-on-write updates**: Adding filters/tests creates new dicts, no locks
2. **Local render state**: Each `render()` uses only local variables
3. **GIL independence**: Declares `_Py_mod_gil = 0` for free-threading
4. **No shared mutable state**: Templates are immutable after compilation

### Jinja2's Limitations

1. **No GIL independence declaration**: May have internal GIL assumptions
2. **Shared state contention**: Internal caches and state cause contention
3. **Negative scaling**: Actually slows down at high concurrency

---

### Auto-Tuned Workers

Kida includes a worker auto-tuner that selects optimal parallelism:

```python
from kida import get_optimal_workers, should_parallelize, WorkloadType

# Auto-tune based on task count and workload
task_count = 100
if should_parallelize(task_count):
    workers = get_optimal_workers(task_count, workload_type=WorkloadType.RENDER)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(template.render, contexts))
```

---

## Running Benchmarks

```bash
# Full comparison (single + concurrent, inline templates)
pytest benchmarks/test_benchmark_full_comparison.py -v --benchmark-only

# File-based rendering (single-threaded, reported in performance docs)
pytest benchmarks/test_benchmark_render.py -v --benchmark-only

# Streaming: render() vs render_stream(), time-to-first-chunk
pytest benchmarks/test_benchmark_streaming.py -v --benchmark-only

# Kida features: pattern matching, fragment cache cold/hit, bytecode cache
pytest benchmarks/test_benchmark_features.py -v --benchmark-only

# Compile pipeline (lex -> parse -> compile)
pytest benchmarks/test_benchmark_compile_pipeline.py -v --benchmark-only

# Scaling: variables, loops, filters, inheritance, include depth
pytest benchmarks/test_benchmark_scaling.py -v --benchmark-only

# Output-sanity benchmark guards (count/equivalence assertions + timing)
pytest benchmarks/test_benchmark_output_sanity.py -v --benchmark-only

# Stable Kida-only hot-path regression probes
pytest benchmarks/test_benchmark_regression_core.py -v --benchmark-only

# Inherited block hot-path performance
pytest benchmarks/test_benchmark_inherited_blocks.py -v --benchmark-only

# Scaling depth: inheritance, filter chains, add_filter, partial eval, cache contention
pytest benchmarks/test_benchmark_scaling_depth.py -v --benchmark-only

# Cold-start (subprocess, Kida vs Jinja2)
pytest benchmarks/test_benchmark_cold_start.py -v --benchmark-only

# Optional: Mako comparison (requires pip install mako)
pytest benchmarks/test_benchmark_mako.py -v --benchmark-only

# Concurrent comparison only
pytest benchmarks/test_benchmark_concurrent.py -v --benchmark-only

# Lexer performance
pytest benchmarks/test_benchmark_lexer.py -v --benchmark-only

# All benchmarks
pytest benchmarks/ -v --benchmark-only

# Save a baseline for regression detection
./scripts/benchmark_baseline.sh

# Compare against baseline (local)
./scripts/benchmark_compare.sh
```

### Benchmark Suites

The helper scripts split the benchmark garden into three paths:

| Suite | Use | Files |
|-------|-----|-------|
| `core` | CI regression gate and release checks | `test_benchmark_regression_core.py`, `test_benchmark_compile_pipeline.py`, `test_benchmark_output_sanity.py` |
| `product` | Docs/product comparison refreshes | render, full comparison, features, introspection, include depth, inherited blocks, output sanity, regression core |
| `exploratory` | Human profiling sweeps | all `test_benchmark_*.py` modules |

`core` is the default for `benchmark_baseline.sh` and `benchmark_compare.sh`.
Choose another suite with `BENCHMARK_SUITE=product` or `BENCHMARK_SUITE=exploratory`.
Use `BENCHMARK_STORAGE_DIR=/tmp/kida-benchmarks` for smoke runs that should
not touch committed baseline files.

### Benchmark Regression CI

CI runs the `core` benchmark regression check on every PR and push. It compares against a committed baseline and fails if benchmarks exceed the regression threshold.

**Thresholds**: CI uses 20% (shared runners, 4 cores); local uses 15%. Override with `BENCHMARK_REGRESSION_THRESHOLD=25`.

**Comparison stat**: The gate compares `median` by default to reduce shared-runner outlier sensitivity. Override with `BENCHMARK_COMPARE_STAT=mean` when intentionally investigating mean drift.

**Excluded from regression**: each suite carries its own high-variance filter. Include all selected-suite benchmarks with `BENCHMARK_INCLUDE_ALL=1`.

**Initial setup** (required for CI to pass):

1. Run **Benchmark baseline** workflow (Actions → Benchmark baseline → Run workflow)
2. Download the `benchmark-baseline-linux` artifact
3. Extract to `benchmarks/` (creates `Linux-CPython-3.14-64bit/0001_baseline.json`)
4. Commit and push

Without a Linux baseline, benchmark-regression CI fails intentionally.
Add a baseline before merging release-critical performance changes.

**Updating the baseline**: After intentional performance changes, run the Benchmark baseline workflow again, or locally:

```bash
./scripts/benchmark_baseline.sh
# Then commit benchmarks/<platform>/*.json
```

For product comparison numbers, keep CI baselines separate from docs refreshes:

```bash
BENCHMARK_SUITE=product ./scripts/benchmark_baseline.sh product-baseline
```

When a PR updates benchmark baseline JSON files, include a **Baseline Drift Rationale**
section in the PR description with:
- before/after metric deltas
- why drift is expected
- why the new baseline is safe to adopt

### Release Checklist Addendum

Before tagging/publishing a Kida release candidate:

```bash
# In bengal repo, validate downstream sentinels against the candidate
uv run pytest -n 0 -q --tb=short -m performance \
  tests/performance/test_autodoc_render_regression.py \
  tests/performance/test_asset_fallback_cost.py
```

Note: Baselines are machine-specific. CI uses Ubuntu (Linux); local baselines (e.g. Darwin) are for development only.

For the formal Kida vs Jinja2 comparison matrix, see [RESULTS.md](RESULTS.md).

---

## Environment

All benchmarks run on:

```
Python 3.14.2 free-threading build
GIL: DISABLED
Platform: macOS (Apple Silicon)
```

---

## Interpreting Results

### When Kida Wins Big

- **Large templates**: 2.53x faster (file-based benchmark, `test_benchmark_render.py`)
- **Medium templates**: 1.72x faster (file-based, ~100 vars)
- **Small/minimal templates**: 1.3-1.4x faster (lower per-render overhead)
- **Complex inheritance**: 1.55x faster (3-level inheritance chain)
- **Concurrent (2-4 workers)**: Consistent 1.1-1.2x advantage

### When Results Are Similar

- **8+ worker concurrency**: Threading overhead dominates for small workloads
- **I/O-heavy workloads**: Template rendering isn't the bottleneck

### The Real Story

Kida is faster across the board — from minimal templates (1.3x) to large templates (2.53x). The advantage grows with template complexity due to the StringBuilder pattern and AST-native compilation.

| Scenario | Kida Advantage |
|----------|----------------|
| Single-threaded, minimal template | 1.31x (file-based) |
| Single-threaded, medium template | **1.72x** (file-based) |
| Single-threaded, large template | **2.53x** (file-based) |
| 2-4 workers, concurrent renders | 1.12-1.13x |

Choose Kida when you need:
- High-throughput template rendering
- Minimal per-render overhead
- True parallelism on Python 3.14+
