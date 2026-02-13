# Render Profiling

`profiled_render()` context manager collects block timings, filter usage, macro call counts.

## Run

```bash
cd examples/profiling && python app.py
```

## Test

```bash
pytest examples/profiling/ -v
```

## What It Shows

- `with profiled_render() as metrics:` — opt-in profiling
- Block render times, filter calls, macro counts
- Zero overhead when profiling is not enabled
- `metrics.summary()` for bottleneck identification
