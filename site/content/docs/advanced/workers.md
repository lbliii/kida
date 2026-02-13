---
title: Worker Auto-Tuning
description: Workload-aware parallelization for free-threaded Python
draft: false
weight: 40
lang: en
type: doc
tags:
- advanced
- performance
- threading
keywords:
- workers
- parallelization
- thread pool
- auto-tuning
- free-threading
- scheduling
icon: cpu
---

# Worker Auto-Tuning

Kida provides a workload-aware worker pool toolkit for framework authors who need to parallelize template rendering. It is calibrated for free-threaded Python (3.14t) where CPU-bound rendering achieves true parallelism.

```python
from kida.utils.workers import get_optimal_workers, should_parallelize
```

## Quick Start

```python
from concurrent.futures import ThreadPoolExecutor
from kida.utils.workers import get_optimal_workers, should_parallelize

contexts = [{"name": f"User {i}"} for i in range(100)]

if should_parallelize(len(contexts)):
    workers = get_optimal_workers(len(contexts))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(template.render, contexts))
else:
    results = [template.render(**ctx) for ctx in contexts]
```

## Core Functions

> **Import:** Use `from kida.utils.workers import ...` or `from kida import get_optimal_workers, should_parallelize, ...`

### should_parallelize

Determine if parallelization is worthwhile. Thread pool overhead (~1-2ms per task) only pays off above a threshold.

```python
from kida.utils.workers import should_parallelize

should_parallelize(5)    # False — below threshold
should_parallelize(100)  # True — above threshold

# With work size estimate (bytes of template output)
should_parallelize(100, total_work_estimate=500)  # False — too small
```

### get_optimal_workers

Calculate the optimal worker count based on workload type, environment, CPU cores, and free-threading status.

```python
from kida.utils.workers import get_optimal_workers, WorkloadType

# Template rendering (default)
get_optimal_workers(100)  # 4 (local, free-threading)

# Template compilation
get_optimal_workers(100, workload_type=WorkloadType.COMPILE)  # 2

# Override auto-tuning
get_optimal_workers(100, config_override=16)  # 16

# Weight heavy templates higher
get_optimal_workers(50, task_weight=2.0)  # Adjusts for heavy work
```

## Workload Types

| Type | Use Case | Parallelism |
|------|----------|-------------|
| `WorkloadType.RENDER` | Template rendering (CPU-bound) | High — benefits from free-threading |
| `WorkloadType.COMPILE` | Template compilation (CPU-bound) | Moderate — shared cache limits scaling |
| `WorkloadType.IO_BOUND` | File loading, network | High — threads wait on I/O |

## Environment Detection

The toolkit auto-detects the execution environment to tune worker counts:

| Environment | Detection | Worker Strategy |
|-------------|-----------|-----------------|
| **CI** | `CI`, `GITHUB_ACTIONS`, etc. | Conservative (2 workers max) |
| **Local** | Default | Moderate (up to 4 workers) |
| **Production** | `KIDA_ENV=production` | Aggressive (up to 8 workers) |

Override detection with the `KIDA_ENV` environment variable:

```bash
export KIDA_ENV=production  # or "ci" or "local"
```

## Free-Threading Detection

The toolkit detects whether the GIL is disabled and scales worker counts accordingly:

```python
from kida.utils.workers import is_free_threading_enabled

if is_free_threading_enabled():
    print("GIL disabled — true parallelism available")
```

On free-threaded Python, render workloads get a 1.5x multiplier on the CPU-based worker count.

## Template Scheduling

For optimal throughput, schedule heavy templates first to avoid the "straggler effect" where one slow render delays overall completion.

### estimate_template_weight

Estimate relative complexity of a template:

```python
from kida.utils.workers import estimate_template_weight

weight = estimate_template_weight(template)
# 1.0 = average, >1 = heavy, <1 = light (capped at 5.0)
```

Weight factors:
- **Source size**: +0.5 per 5KB above 5KB threshold
- **Block count**: +0.1 per block above 3
- **Macro count**: +0.2 per macro
- **Inheritance**: +0.5 if extends another template
- **Includes**: +0.15 per include statement

### order_by_complexity

Sort templates for optimal parallel execution:

```python
from kida.utils.workers import order_by_complexity

# Heavy templates first (default — best for parallel execution)
ordered = order_by_complexity(templates)

# Light templates first (useful for testing)
ordered = order_by_complexity(templates, descending=False)
```

## Workload Profiles

Inspect the tuning parameters for any workload/environment combination:

```python
from kida.utils.workers import get_profile, WorkloadType

profile = get_profile(WorkloadType.RENDER)
print(profile.parallel_threshold)        # 10
print(profile.max_workers)               # 4
print(profile.free_threading_multiplier) # 1.5
```

### WorkloadProfile Fields

| Field | Type | Description |
|-------|------|-------------|
| `parallel_threshold` | `int` | Minimum tasks before parallelizing |
| `min_workers` | `int` | Floor for worker count |
| `max_workers` | `int` | Ceiling for worker count |
| `cpu_fraction` | `float` | Fraction of cores to use (0.0-1.0) |
| `free_threading_multiplier` | `float` | Extra scaling when GIL is disabled |

## Complete Example

```python
from concurrent.futures import ThreadPoolExecutor
from kida import Environment, FileSystemLoader
from kida.utils.workers import (
    get_optimal_workers,
    order_by_complexity,
    should_parallelize,
    WorkloadType,
)

env = Environment(loader=FileSystemLoader("templates/"))

# Load and schedule templates
templates = [env.get_template(name) for name in env.loader.list_templates()]
ordered = order_by_complexity(templates)

# Build render tasks
tasks = [(tmpl, {"page": page}) for tmpl, page in zip(ordered, pages, strict=True)]

if should_parallelize(len(tasks)):
    workers = get_optimal_workers(
        len(tasks),
        workload_type=WorkloadType.RENDER,
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda t: t[0].render(**t[1]), tasks))
else:
    results = [tmpl.render(**ctx) for tmpl, ctx in tasks]
```

## See Also

- [[docs/about/thread-safety|Thread Safety]] — Free-threading design
- [[docs/about/performance|Performance]] — Concurrent benchmark results
- [[docs/advanced/analysis|Static Analysis]] — Template complexity analysis
