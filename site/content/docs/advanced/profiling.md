---
title: Profiling
description: Opt-in render instrumentation with zero overhead when disabled
draft: false
weight: 60
lang: en
type: doc
tags:
- advanced
- performance
- profiling
keywords:
- profiling
- render accumulator
- instrumentation
- block timings
- macro calls
- filter usage
icon: activity
---

# Profiling

Kida includes compiler-emitted profiling instrumentation that tracks block render times, macro calls, include counts, and filter usage. Profiling is **opt-in** — it has zero overhead when disabled because the accumulator check (`get_accumulator() returns None`) short-circuits immediately.

```python
from kida.render_accumulator import profiled_render
```

## Quick Start

```python
from kida import Environment, FileSystemLoader
from kida.render_accumulator import profiled_render

env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("page.html")

# Normal render — no overhead
html = template.render(page=page, site=site)

# Profiled render — opt-in metrics
with profiled_render() as metrics:
    html = template.render(page=page, site=site)

print(metrics.summary())
```

Output:

```python
{
    "total_ms": 12.5,
    "blocks": {
        "content": {"ms": 8.2, "calls": 1},
        "nav": {"ms": 2.1, "calls": 1},
        "sidebar": {"ms": 1.8, "calls": 1},
    },
    "macros": {"render_card": 15, "format_date": 8},
    "includes": {"partials/sidebar.html": 1},
    "filters": {"escape": 45, "truncate": 12, "date": 8},
}
```

## How It Works

1. `profiled_render()` creates a `RenderAccumulator` and stores it in a `ContextVar`
2. During rendering, compiler-emitted instrumentation checks `get_accumulator()`
3. If an accumulator exists, metrics are recorded; otherwise the check is a no-op
4. After the `with` block exits, the accumulator is removed from the `ContextVar`

Because `ContextVar` provides thread-local isolation, profiling one render call does not affect concurrent renders.

## RenderAccumulator

The accumulator collects four categories of metrics:

### Block Timings

Every block render is timed. If a block renders multiple times (e.g., in a loop), durations are summed and calls counted:

```python
with profiled_render() as metrics:
    html = template.render(**ctx)

for name, timing in metrics.block_timings.items():
    print(f"{name}: {timing.duration_ms:.2f}ms ({timing.call_count} calls)")
```

### Macro Calls

Macro invocations are counted, including cross-template macro imports:

```python
metrics.macro_calls
# {"render_card": 15, "format_date": 8}
```

### Include Counts

Track how many times each template is included:

```python
metrics.include_counts
# {"partials/sidebar.html": 1, "partials/card.html": 15}
```

### Filter Usage

Every filter application is counted:

```python
metrics.filter_calls
# {"escape": 45, "truncate": 12, "upper": 3}
```

## Manual Block Timing

Use `timed_block()` to time custom code sections. It is a no-op when profiling is disabled:

```python
from kida.render_accumulator import timed_block

with timed_block("data_fetch"):
    data = fetch_expensive_data()

with timed_block("render"):
    html = template.render(data=data)
```

## Recording Metrics Manually

The accumulator exposes methods for recording custom metrics:

```python
from kida.render_accumulator import get_accumulator

acc = get_accumulator()
if acc is not None:
    acc.record_block("custom_section", duration_ms=5.2)
    acc.record_macro("my_macro")
    acc.record_include("partials/widget.html")
    acc.record_filter("my_filter")
```

## Integration Patterns

### Finding Slow Blocks

```python
with profiled_render() as metrics:
    html = template.render(**ctx)

# Sort blocks by render time (summary already sorts descending)
summary = metrics.summary()
for name, data in summary["blocks"].items():
    if data["ms"] > 5.0:
        print(f"SLOW: {name} took {data['ms']}ms ({data['calls']} calls)")
```

### Comparing Renders

```python
def benchmark_template(template, contexts, runs=10):
    """Average metrics across multiple renders."""
    totals = []
    for ctx in contexts[:runs]:
        with profiled_render() as metrics:
            template.render(**ctx)
        totals.append(metrics.total_duration_ms)
    avg = sum(totals) / len(totals)
    print(f"Average render: {avg:.2f}ms")
```

### Build System Integration

```python
from kida.render_accumulator import profiled_render

slow_templates = []

for template, context in build_queue:
    with profiled_render() as metrics:
        html = template.render(**context)

    if metrics.total_duration_ms > 50:
        slow_templates.append((template.name, metrics.total_duration_ms))

if slow_templates:
    print("Slow templates:")
    for name, ms in sorted(slow_templates, key=lambda x: x[1], reverse=True):
        print(f"  {name}: {ms:.1f}ms")
```

## API Reference

### Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `profiled_render()` | `() -> Iterator[RenderAccumulator]` | Context manager for profiled rendering |
| `timed_block()` | `(name: str) -> Iterator[None]` | Time a code section (no-op when disabled) |
| `get_accumulator()` | `() -> RenderAccumulator \| None` | Get current accumulator or None |

### RenderAccumulator

| Property / Method | Type | Description |
|-------------------|------|-------------|
| `block_timings` | `dict[str, BlockTiming]` | Block name to timing data |
| `macro_calls` | `dict[str, int]` | Macro name to call count |
| `include_counts` | `dict[str, int]` | Template name to include count |
| `filter_calls` | `dict[str, int]` | Filter name to call count |
| `total_duration_ms` | `float` | Total render duration (property) |
| `record_block()` | `(name, duration_ms) -> None` | Record a block render |
| `record_macro()` | `(name) -> None` | Record a macro invocation |
| `record_include()` | `(template_name) -> None` | Record an include |
| `record_filter()` | `(name) -> None` | Record a filter usage |
| `summary()` | `() -> dict` | Get sorted summary of all metrics |

### BlockTiming

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Block name |
| `duration_ms` | `float` | Total render time in milliseconds |
| `call_count` | `int` | Number of renders |

All classes are importable from `kida.render_accumulator`.

## See Also

- [[docs/about/performance|Performance]] — Benchmark methodology
- [[docs/advanced/analysis|Static Analysis]] — Block-level analysis
- [[docs/advanced/block-caching|Block Caching]] — Cache informed by profiling
