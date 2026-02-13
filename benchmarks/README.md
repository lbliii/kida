# Kida Benchmarks

Performance comparison between Kida and Jinja2 on **Python 3.14 free-threading**.

> Numbers below are from `test_benchmark_full_comparison.py` (inline templates,
> Python 3.14.2 free-threading, Apple Silicon).
> For file-based template benchmarks, see `test_benchmark_render.py`.

## Quick Results

### Single-Threaded Performance

| Template | Kida | Jinja2 | Kida Advantage |
|----------|------|--------|----------------|
| **Minimal** (`{{ name }}`) | 8.25µs | 11.97µs | **1.45x faster** |
| **Small** (loop + filter) | 17.03µs | 27.69µs | **1.63x faster** |
| **Medium** (conditionals + loops) | 17.90µs | 19.04µs | 1.06x faster |

**Takeaway**: Kida has significantly lower per-render overhead, most visible on small templates.

---

### Concurrent Performance (Free-Threading)

Same total work (100 renders of medium template), distributed across workers:

| Workers | Kida | Jinja2 | Kida Advantage |
|---------|------|--------|----------------|
| **1** (baseline) | 1.80ms | 1.80ms | ~same |
| **2** | 1.12ms | 1.15ms | ~same |
| **4** | 1.62ms | 1.90ms | **1.17x faster** |
| **8** | 1.76ms | 1.97ms | **1.12x faster** |

**Takeaway**: Kida's advantage **grows with concurrency**. Jinja2 degrades at higher worker counts.

> Concurrent benchmarks use `pedantic(rounds=5)` and have higher variance than
> single-threaded benchmarks. The consistent signal is that Kida maintains
> performance under concurrency while Jinja2 tends to degrade.

---

### Scaling Efficiency

| Engine | 1→2 workers | 1→4 workers | 1→8 workers |
|--------|-------------|-------------|-------------|
| **Kida** | 1.61x speedup | 1.11x speedup | 1.02x speedup |
| **Jinja2** | 1.57x speedup | 0.95x speedup ⚠️ | 0.91x speedup ⚠️ |

**Takeaway**: Jinja2 shows **negative scaling** at 4+ workers (slower than baseline). Kida maintains gains.

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

# Compile pipeline (lex → parse → compile)
pytest benchmarks/test_benchmark_compile_pipeline.py -v --benchmark-only

# Scaling: variables, loops, filters, inheritance, include depth
pytest benchmarks/test_benchmark_scaling.py -v --benchmark-only

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

# Compare against baseline
./scripts/benchmark_compare.sh
```

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

- **Minimal/small templates**: Lower runtime overhead dominates (1.5-1.6x)
- **Large templates**: 2.14x faster (file-based benchmark, `test_benchmark_render.py`)
- **High concurrency**: Thread-safe design enables true parallelism
- **Many small renders**: Per-render overhead matters

### When Results Are Similar

- **Medium templates**: HTML escaping overhead dominates — Jinja2's C extension (`markupsafe`) vs Kida's pure-Python escape is a factor
- **Single-threaded**: GIL isn't a bottleneck
- **I/O-heavy workloads**: Template rendering isn't the bottleneck

### The Real Story

**Single-threaded benchmarks undersell Kida**. The true advantage emerges under concurrent workloads — exactly where modern Python (free-threading) is headed. Kida also wins large template rendering (2.14x faster) due to the StringBuilder pattern.

| Scenario | Kida Advantage |
|----------|----------------|
| Single-threaded, minimal template | 1.56x (file-based) |
| Single-threaded, large template | **2.14x** (file-based) |
| 8 workers, concurrent renders | 1.12x |

Choose Kida when you need:
- High-concurrency template rendering
- Minimal per-render overhead
- True parallelism on Python 3.14+
