# Kida vs Jinja2 Comparison Matrix

Formal comparison matrix for the Kida Maturity Epic. Results are populated by running
the benchmark suite. See [README.md](README.md) for full analysis and interpretation.

## How to Populate

```bash
# Run all comparison benchmarks
pytest benchmarks/test_benchmark_full_comparison.py benchmarks/test_benchmark_streaming.py \
  benchmarks/test_benchmark_cold_start.py benchmarks/test_benchmark_scaling.py \
  benchmarks/test_benchmark_scaling_depth.py --benchmark-only -v

# Or run individually and record median (µs) from output
```

## Comparison Matrix

| Scenario                      | Kida (µs) | Jinja2 (µs) | Notes                    |
| ----------------------------- | --------- | ----------- | ------------------------ |
| Cold compile (no cache)       | —         | —           | `test_benchmark_cold_start` |
| Warm render (cached template) | ~8–18     | ~12–27      | `test_benchmark_full_comparison` minimal/small/medium |
| Streaming render              | —         | —           | `test_benchmark_streaming` |
| 50-filter chain render        | ~10       | —           | `test_benchmark_scaling_depth` filters[50] |
| 10-level inheritance render   | ~35       | —           | `test_benchmark_scaling_depth` inheritance[10] |
| 8-thread concurrent render    | ~1.76ms   | ~1.97ms     | `test_benchmark_full_comparison` 8-workers |

## Benchmark Sources

| Scenario              | Benchmark File                         | Group / Param          |
| --------------------- | -------------------------------------- | ---------------------- |
| Cold compile          | `test_benchmark_cold_start.py`         | cold-start            |
| Single-threaded       | `test_benchmark_full_comparison.py`    | 1-single:minimal/small/medium |
| Concurrent            | `test_benchmark_full_comparison.py`    | 2-concurrent:8-workers |
| Streaming             | `test_benchmark_streaming.py`         | streaming              |
| Filter chain          | `test_benchmark_scaling_depth.py`      | scaling-depth:filters  |
| Inheritance depth     | `test_benchmark_scaling_depth.py`      | scaling-depth:inheritance |

## Environment

Results depend on:

- Python version (3.14+ free-threading recommended)
- GIL status (disabled for concurrent benchmarks)
- Platform (Apple Silicon, x86_64, etc.)

Record environment when capturing results:

```
Python 3.14.2 free-threading
GIL: DISABLED
Platform: macOS (Apple Silicon)
```
