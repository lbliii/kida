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

| Scenario                      | Kida        | Jinja2      | Notes                    |
| ----------------------------- | ----------- | ----------- | ------------------------ |
| Cold start (no cache)         | ~135ms      | ~66ms       | `test_benchmark_cold_start` — Jinja2 faster (C extensions) |
| Cold start (bytecode cache)   | ~125ms      | —           | `test_benchmark_cold_start` |
| Warm render: minimal          | 4.53µs      | 5.13µs      | `test_benchmark_full_comparison` inline |
| Warm render: small            | 7.66µs      | 10.71µs     | `test_benchmark_full_comparison` inline |
| Warm render: medium           | 9.41µs      | 11.82µs     | `test_benchmark_full_comparison` inline |
| File render: minimal          | 4.04µs      | 5.28µs      | `test_benchmark_render` |
| File render: medium           | 210.57µs    | 363.14µs    | `test_benchmark_render` |
| File render: large            | 1.59ms      | 4.03ms      | `test_benchmark_render` — **2.53x faster** |
| File render: complex          | 18.93µs     | 29.33µs     | `test_benchmark_render` — 3-level inheritance |
| Streaming render: medium      | 10.61µs     | 12.39µs     | `test_benchmark_streaming` |
| Time to first chunk: medium   | 5.15µs      | —           | `test_benchmark_streaming` |
| 50-filter chain render        | ~8.6µs      | —           | `test_benchmark_scaling_depth` filters[50] |
| 10-level inheritance render   | ~38µs       | —           | `test_benchmark_scaling_depth` inheritance[10] |
| 2-thread concurrent render    | 0.87ms      | 0.98ms      | `test_benchmark_full_comparison` 2-workers |
| 4-thread concurrent render    | 0.90ms      | 1.02ms      | `test_benchmark_full_comparison` 4-workers |
| 8-thread concurrent render    | ~1.68ms     | ~1.62ms     | `test_benchmark_full_comparison` 8-workers — ~same |

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
