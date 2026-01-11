# RFC: Benchmarking Strategy

**Status**: Draft  
**Created**: 2026-01-10  
**Updated**: 2026-01-10  
**Author**: Kida Contributors  

---

## Executive Summary

Establish a rigorous benchmarking framework to validate Kida's performance claims and provide actionable metrics for users. Current documentation makes specific performance claims (25-40% faster, 90%+ cold-start improvement, specific timing tables) without supporting benchmarks.

**Key Deliverables:**
- Reproducible Jinja2 comparison benchmarks
- Cold-start measurement suite
- Template complexity scaling tests
- CI-integrated regression detection
- Validated (or corrected) documentation claims

---

## Problem Statement

The deep audit of `performance.md` identified **4 unverified performance claims**:

| Claim | Location | Issue |
|-------|----------|-------|
| Benchmark table (0.3ms, 0.5ms, etc.) | `performance.md:26-30` | No validation exists |
| "25-40% faster" | `performance.md:61`, README | Architecture supports, no benchmark |
| "90%+ cold-start improvement" | `performance.md:119` | Specific metric unvalidated |
| Compile-time optimizations | `performance.md:87-93` | Claims don't match implementation |

**Current state:** Only `benchmarks/benchmark_escape.py` exists (HTML escaping), not template rendering benchmarks.

---

## Goals

1. **Validate or correct** existing performance claims with reproducible data
2. **Establish baseline metrics** for Kida vs Jinja2 across template sizes
3. **Measure cold-start improvement** with bytecode cache enabled/disabled
4. **Create regression detection** to catch performance degradation
5. **Provide user-runnable benchmarks** for their specific workloads

### Non-Goals

- Micro-optimizing for benchmark scores at cost of maintainability
- Comprehensive benchmarks against all template engines (focus: Jinja2 as primary comparison)
- Hardware-specific tuning (provide methodology for users to run their own)

---

## Benchmark Categories

### Category 1: Template Rendering (Kida vs Jinja2)

**Purpose:** Validate "25-40% faster" claim and benchmark table values.

**Test Matrix:**

| Template Type | Variables | Loops | Filters | Inheritance |
|---------------|-----------|-------|---------|-------------|
| Minimal | 1 | 0 | 0 | No |
| Small | 10 | 1 | 2 | No |
| Medium | 100 | 5 | 10 | 1 level |
| Large | 1000 | 20 | 50 | 2 levels |
| Complex | 100 | 10 | 20 | 3 levels + includes |

**Metrics:**
- Mean render time (ms)
- Median render time (ms)
- P95/P99 latency
- Standard deviation
- Throughput (renders/sec)

**Methodology:**
```python
# Warm-up: 100 iterations (discard)
# Measurement: 1000 iterations minimum
# Repetitions: 5 runs, report median of means
# GC: Disabled during measurement window
# CPU: Pin to single core for consistency
```

### Category 2: Cold-Start Performance

**Purpose:** Validate "90%+ cold-start improvement" claim.

**Test Scenarios:**

| Scenario | Description | Expected Metric |
|----------|-------------|-----------------|
| No cache | Fresh Environment, no bytecode cache | Baseline |
| Bytecode cache miss | First load with cache enabled | ~Baseline |
| Bytecode cache hit | Subsequent load from cache | Target: 90%+ improvement |
| Template cache hit | In-memory cache hit | ~0ms overhead |

**Methodology:**
```python
# Measure time from Environment() to first render completion
# Include: Lexing, parsing, compilation, execution
# Exclude: Import time (measured separately)

import subprocess
import time

def measure_cold_start(cache_enabled: bool) -> float:
    """Spawn fresh Python process to measure true cold-start."""
    script = f'''
import time
start = time.perf_counter()
from kida import Environment
env = Environment(bytecode_cache={cache_enabled})
template = env.from_string("Hello, {{{{ name }}}}!")
result = template.render(name="World")
end = time.perf_counter()
print(end - start)
'''
    result = subprocess.run(["python", "-c", script], capture_output=True, text=True)
    return float(result.stdout.strip())
```

### Category 3: Scaling Characteristics

**Purpose:** Understand performance at scale and identify bottlenecks.

**Tests:**
1. **Variable count scaling**: 10 → 100 → 1000 → 10000 variables
2. **Loop iteration scaling**: 10 → 100 → 1000 → 10000 items
3. **Filter chain depth**: 1 → 5 → 10 → 20 filters
4. **Template inheritance depth**: 1 → 3 → 5 → 10 levels
5. **Include count**: 1 → 10 → 50 → 100 includes

**Expected Characteristics:**
- O(n) for variable count (StringBuilder)
- O(n) for loop iterations
- O(k) for filter chains (k = filter count)
- O(d) for inheritance (d = depth)

### Category 4: Memory Usage

**Purpose:** Understand memory footprint for capacity planning.

**Metrics:**
- Template object size (bytes)
- Peak memory during render
- Cache memory overhead (per template)
- Bytecode cache disk usage

### Category 5: Concurrency / Free-Threading

**Purpose:** Validate thread-safety claims and measure concurrent performance.

**Tests:**
1. **Single-threaded baseline**: 1 thread, N renders
2. **Multi-threaded scaling**: 2, 4, 8, 16 threads
3. **Contention under load**: Concurrent compilation + rendering
4. **GIL-free performance** (Python 3.14t): Measure actual parallelism

---

## Benchmark Implementation

### File Structure

```
benchmarks/
├── __init__.py
├── conftest.py              # Shared fixtures, pytest-benchmark config
├── benchmark_escape.py      # Existing: HTML escaping (keep)
├── benchmark_render.py      # NEW: Template rendering vs Jinja2
├── benchmark_cold_start.py  # NEW: Cold-start measurements
├── benchmark_scaling.py     # NEW: Scaling characteristics
├── benchmark_memory.py      # NEW: Memory profiling
├── benchmark_threading.py   # NEW: Concurrency tests
├── templates/               # Test templates
│   ├── minimal.html
│   ├── small.html
│   ├── medium.html
│   ├── large.html
│   ├── complex/
│   │   ├── base.html
│   │   ├── layout.html
│   │   └── page.html
│   └── jinja2/             # Equivalent Jinja2 templates
│       └── ...
├── fixtures/
│   ├── context_small.py    # 10 variables
│   ├── context_medium.py   # 100 variables
│   └── context_large.py    # 1000 variables
└── README.md               # How to run, interpret results
```

### Core Benchmark: Render Comparison

```python
# benchmarks/benchmark_render.py
"""Template rendering benchmarks: Kida vs Jinja2.

Run with: pytest benchmarks/benchmark_render.py --benchmark-only
Compare: pytest benchmarks/benchmark_render.py --benchmark-compare
"""

from __future__ import annotations

import pytest
from jinja2 import Environment as Jinja2Environment
from kida import Environment as KidaEnvironment

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def kida_env() -> KidaEnvironment:
    return KidaEnvironment()

@pytest.fixture
def jinja2_env() -> Jinja2Environment:
    return Jinja2Environment()

@pytest.fixture
def small_context() -> dict:
    """10 variables for small template tests."""
    return {
        "title": "Hello World",
        "name": "Alice",
        "count": 42,
        "items": ["a", "b", "c", "d", "e"],
        "active": True,
        "price": 19.99,
        "tags": ["python", "template"],
        "metadata": {"author": "test", "version": "1.0"},
        "description": "A short description of the page content.",
        "footer": "© 2026 Example Corp",
    }

@pytest.fixture
def medium_context() -> dict:
    """100 variables for medium template tests."""
    ctx = {f"var_{i}": f"value_{i}" for i in range(90)}
    ctx["items"] = [{"id": i, "name": f"Item {i}", "price": i * 1.5} for i in range(100)]
    ctx["categories"] = [f"Category {i}" for i in range(10)]
    return ctx

@pytest.fixture
def large_context() -> dict:
    """1000 variables for large template tests."""
    ctx = {f"var_{i}": f"value_{i}" for i in range(900)}
    ctx["items"] = [{"id": i, "name": f"Item {i}", "data": {"x": i, "y": i*2}} for i in range(1000)]
    ctx["sections"] = [{"title": f"Section {i}", "content": "x" * 100} for i in range(100)]
    return ctx

# =============================================================================
# Small Template (10 vars)
# =============================================================================

SMALL_TEMPLATE_KIDA = """
<html>
<head><title>{{ title }}</title></head>
<body>
    <h1>Hello, {{ name }}!</h1>
    <p>Count: {{ count }}</p>
    <ul>
    {% for item in items %}
        <li>{{ item }}</li>
    {% end %}
    </ul>
    {% if active %}
        <p>Status: Active</p>
    {% end %}
    <footer>{{ footer }}</footer>
</body>
</html>
"""

SMALL_TEMPLATE_JINJA2 = """
<html>
<head><title>{{ title }}</title></head>
<body>
    <h1>Hello, {{ name }}!</h1>
    <p>Count: {{ count }}</p>
    <ul>
    {% for item in items %}
        <li>{{ item }}</li>
    {% endfor %}
    </ul>
    {% if active %}
        <p>Status: Active</p>
    {% endif %}
    <footer>{{ footer }}</footer>
</body>
</html>
"""

def test_render_small_kida(benchmark, kida_env, small_context):
    """Kida: Small template (10 vars)."""
    template = kida_env.from_string(SMALL_TEMPLATE_KIDA)
    benchmark(template.render, **small_context)

def test_render_small_jinja2(benchmark, jinja2_env, small_context):
    """Jinja2: Small template (10 vars)."""
    template = jinja2_env.from_string(SMALL_TEMPLATE_JINJA2)
    benchmark(template.render, **small_context)

# =============================================================================
# Medium Template (100 vars)
# =============================================================================

MEDIUM_TEMPLATE_KIDA = """
<html>
<head><title>Product Catalog</title></head>
<body>
    <nav>
    {% for cat in categories %}
        <a href="#{{ cat | lower | replace(" ", "-") }}">{{ cat }}</a>
    {% end %}
    </nav>

    <main>
    {% for item in items %}
        <article id="item-{{ item.id }}">
            <h2>{{ item.name | escape }}</h2>
            <p class="price">${{ item.price | round(2) }}</p>
        </article>
    {% end %}
    </main>

    <aside>
    {% for i in range(10) %}
        <div>{{ var_{i} }}</div>
    {% end %}
    </aside>
</body>
</html>
"""

MEDIUM_TEMPLATE_JINJA2 = """
<html>
<head><title>Product Catalog</title></head>
<body>
    <nav>
    {% for cat in categories %}
        <a href="#{{ cat | lower | replace(" ", "-") }}">{{ cat }}</a>
    {% endfor %}
    </nav>

    <main>
    {% for item in items %}
        <article id="item-{{ item.id }}">
            <h2>{{ item.name | escape }}</h2>
            <p class="price">${{ item.price | round(2) }}</p>
        </article>
    {% endfor %}
    </main>

    <aside>
    {% for i in range(10) %}
        <div>{{ var_{i} }}</div>
    {% endfor %}
    </aside>
</body>
</html>
"""

def test_render_medium_kida(benchmark, kida_env, medium_context):
    """Kida: Medium template (100 vars, 100 loop items)."""
    # Note: Dynamic variable access needs adjustment for actual test
    template = kida_env.from_string(MEDIUM_TEMPLATE_KIDA.replace("var_{i}", "var_0"))
    benchmark(template.render, **medium_context)

def test_render_medium_jinja2(benchmark, jinja2_env, medium_context):
    """Jinja2: Medium template (100 vars, 100 loop items)."""
    template = jinja2_env.from_string(MEDIUM_TEMPLATE_JINJA2.replace("var_{i}", "var_0"))
    benchmark(template.render, **medium_context)

# =============================================================================
# Large Template (1000 vars)
# =============================================================================

def test_render_large_kida(benchmark, kida_env, large_context):
    """Kida: Large template (1000 loop items)."""
    template = kida_env.from_string("""
{% for item in items %}
<div id="{{ item.id }}">{{ item.name }} - {{ item.data.x }}/{{ item.data.y }}</div>
{% end %}
""")
    benchmark(template.render, **large_context)

def test_render_large_jinja2(benchmark, jinja2_env, large_context):
    """Jinja2: Large template (1000 loop items)."""
    template = jinja2_env.from_string("""
{% for item in items %}
<div id="{{ item.id }}">{{ item.name }} - {{ item.data.x }}/{{ item.data.y }}</div>
{% endfor %}
""")
    benchmark(template.render, **large_context)

# =============================================================================
# Compilation Benchmarks
# =============================================================================

def test_compile_small_kida(benchmark, kida_env):
    """Kida: Compile small template."""
    benchmark(kida_env.from_string, SMALL_TEMPLATE_KIDA)

def test_compile_small_jinja2(benchmark, jinja2_env):
    """Jinja2: Compile small template."""
    benchmark(jinja2_env.from_string, SMALL_TEMPLATE_JINJA2)
```

### Cold-Start Benchmark

```python
# benchmarks/benchmark_cold_start.py
"""Cold-start performance benchmarks.

Measures time from fresh import to first render completion.
Validates the "90%+ cold-start improvement" claim.

Run with: python benchmarks/benchmark_cold_start.py
"""

from __future__ import annotations

import gc
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from statistics import mean, median, stdev

ITERATIONS = 10  # Number of cold-start measurements


def measure_cold_start(
    use_bytecode_cache: bool,
    cache_dir: Path | None = None,
    pre_warm: bool = False,
) -> float:
    """Measure cold-start time in a fresh Python process.

    Args:
        use_bytecode_cache: Enable bytecode caching
        cache_dir: Directory for bytecode cache (None = temp)
        pre_warm: If True, assumes cache is already populated

    Returns:
        Time in milliseconds from import to render completion
    """
    cache_arg = "None" if not use_bytecode_cache else f"BytecodeCache(Path('{cache_dir}'))"

    script = f'''
import time
_start = time.perf_counter_ns()

from pathlib import Path
from kida import Environment
{"from kida.bytecode_cache import BytecodeCache" if use_bytecode_cache else ""}

env = Environment(
    bytecode_cache={cache_arg},
)

# Simulate realistic template
template = env.from_string("""
<html>
<head><title>{{{{ title }}}}</title></head>
<body>
    <h1>Hello, {{{{ name }}}}!</h1>
    {{% for item in items %}}
        <li>{{{{ item }}}}</li>
    {{% end %}}
</body>
</html>
""")

result = template.render(title="Test", name="World", items=["a", "b", "c"])
_end = time.perf_counter_ns()

print((_end - _start) / 1_000_000)  # Convert to ms
'''

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )

    if result.returncode != 0:
        raise RuntimeError(f"Cold-start measurement failed: {result.stderr}")

    return float(result.stdout.strip())


def run_cold_start_suite():
    """Run complete cold-start benchmark suite."""
    print("=" * 60)
    print("KIDA COLD-START BENCHMARK")
    print("=" * 60)
    print()

    # Scenario 1: No bytecode cache (baseline)
    print("Scenario 1: No bytecode cache (baseline)")
    print("-" * 40)
    no_cache_times = []
    for i in range(ITERATIONS):
        t = measure_cold_start(use_bytecode_cache=False)
        no_cache_times.append(t)
        print(f"  Run {i+1}: {t:.2f}ms")

    baseline = median(no_cache_times)
    print(f"\n  Median: {baseline:.2f}ms")
    print(f"  Mean:   {mean(no_cache_times):.2f}ms")
    print(f"  Stdev:  {stdev(no_cache_times):.2f}ms")
    print()

    # Scenario 2: Bytecode cache (cold - first population)
    print("Scenario 2: Bytecode cache cold (first population)")
    print("-" * 40)
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        cache_cold_times = []
        for i in range(ITERATIONS):
            # Clear cache between runs
            for f in cache_dir.glob("__kida_*.pyc"):
                f.unlink()
            t = measure_cold_start(use_bytecode_cache=True, cache_dir=cache_dir)
            cache_cold_times.append(t)
            print(f"  Run {i+1}: {t:.2f}ms")

        cache_cold_median = median(cache_cold_times)
        print(f"\n  Median: {cache_cold_median:.2f}ms")
        print(f"  Mean:   {mean(cache_cold_times):.2f}ms")
        print()

        # Scenario 3: Bytecode cache (warm - cache hit)
        print("Scenario 3: Bytecode cache warm (cache hit)")
        print("-" * 40)
        # Pre-populate cache
        measure_cold_start(use_bytecode_cache=True, cache_dir=cache_dir)

        cache_warm_times = []
        for i in range(ITERATIONS):
            t = measure_cold_start(use_bytecode_cache=True, cache_dir=cache_dir, pre_warm=True)
            cache_warm_times.append(t)
            print(f"  Run {i+1}: {t:.2f}ms")

        cache_warm_median = median(cache_warm_times)
        print(f"\n  Median: {cache_warm_median:.2f}ms")
        print(f"  Mean:   {mean(cache_warm_times):.2f}ms")

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Baseline (no cache):     {baseline:.2f}ms")
    print(f"Cache cold (first load): {cache_cold_median:.2f}ms")
    print(f"Cache warm (cache hit):  {cache_warm_median:.2f}ms")
    print()

    if baseline > 0:
        cold_improvement = ((baseline - cache_cold_median) / baseline) * 100
        warm_improvement = ((baseline - cache_warm_median) / baseline) * 100
        print(f"Cold cache improvement:  {cold_improvement:+.1f}%")
        print(f"Warm cache improvement:  {warm_improvement:+.1f}%")
        print()

        if warm_improvement >= 90:
            print("✅ VALIDATED: 90%+ cold-start improvement claim")
        elif warm_improvement >= 80:
            print("⚠️  CLOSE: ~80% improvement (update docs to reflect)")
        else:
            print(f"❌ NOT VALIDATED: Only {warm_improvement:.1f}% improvement")


if __name__ == "__main__":
    run_cold_start_suite()
```

---

## Execution Plan

### Phase 1: Infrastructure (1 day)

- [ ] Add `jinja2` to dev dependencies in `pyproject.toml`
- [ ] Add `pytest-benchmark` to dev dependencies
- [ ] Create `benchmarks/conftest.py` with shared fixtures
- [ ] Create `benchmarks/README.md` with usage instructions
- [ ] Set up benchmark result storage (`.benchmarks/` in gitignore)

### Phase 2: Core Benchmarks (2-3 days)

- [ ] Implement `benchmark_render.py` (Kida vs Jinja2 comparison)
- [ ] Implement `benchmark_cold_start.py` (bytecode cache validation)
- [ ] Create template fixtures for small/medium/large/complex scenarios
- [ ] Run initial benchmarks, document baseline results

### Phase 3: Extended Benchmarks (2 days)

- [ ] Implement `benchmark_scaling.py` (variable/loop/filter scaling)
- [ ] Implement `benchmark_memory.py` (memory profiling)
- [ ] Implement `benchmark_threading.py` (concurrency tests)

### Phase 4: Documentation Updates (1 day)

- [ ] Update `performance.md` with validated numbers
- [ ] Update README performance claims
- [ ] Update `architecture.md` if compile-time optimization claims need correction
- [ ] Add "How to benchmark" section to docs

### Phase 5: CI Integration (1 day)

- [ ] Add benchmark job to GitHub Actions (non-blocking)
- [ ] Configure benchmark comparison for PRs
- [ ] Set up performance regression alerts (>10% slowdown)

---

## Success Criteria

### Quantitative

| Metric | Target | Validation Method |
|--------|--------|-------------------|
| Benchmark table accuracy | Within ±20% of documented values | `benchmark_render.py` |
| "25-40% faster" claim | Confirmed or corrected | Kida vs Jinja2 median |
| "90%+ cold-start" claim | Confirmed or corrected | `benchmark_cold_start.py` |
| Benchmark reproducibility | <5% variance between runs | Multiple iterations |

### Qualitative

- [ ] All performance claims in docs are backed by runnable benchmarks
- [ ] Users can run benchmarks on their own hardware
- [ ] CI catches performance regressions before merge
- [ ] Methodology documented for transparency

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Benchmarks don't validate claims | High | Correct documentation, don't inflate |
| Hardware variance affects results | Medium | Document methodology, report percentiles |
| Jinja2 updates change comparison | Low | Pin Jinja2 version in benchmark deps |
| Benchmark overhead | Low | Keep benchmark suite fast (<5 min total) |

---

## Open Questions

1. **Which Jinja2 version to compare against?** Recommend latest stable (3.1.x).
2. **Include other engines?** (Mako, Django Templates) — Defer to future RFC.
3. **Memory benchmark methodology?** `tracemalloc` vs `memory_profiler`?
4. **Publish benchmark results?** Consider automated reporting to docs site.

---

## Appendix: Expected Corrections

Based on audit findings, these documentation updates are likely needed:

### `performance.md` Lines 87-93

```diff
### Compile-Time Optimization

- AST manipulation enables optimizations before code generation:
- - Constant folding
- - Dead code elimination
- - Static expression evaluation
+ The AST-based architecture enables structured manipulation and future
+ optimization passes. Currently, Kida relies on Python's built-in peephole
+ optimizer for constant folding. Dead code elimination is planned for a
+ future release.
```

### Benchmark Table

Current (unvalidated):
| Template Size | Kida | Jinja2 | Speedup |
|---------------|------|--------|---------|
| Small (10 vars) | 0.3ms | 0.5ms | 1.6x |

Expected format after validation:
| Template Size | Kida | Jinja2 | Speedup | Notes |
|---------------|------|--------|---------|-------|
| Small (10 vars) | X.Xms | X.Xms | X.Xx | Measured on [hardware spec] |

*Results may vary. Run `pytest benchmarks/ --benchmark-only` for your hardware.*

---

## References

- [pytest-benchmark documentation](https://pytest-benchmark.readthedocs.io/)
- [Python Performance Tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips)
- [Jinja2 Performance](https://jinja.palletsprojects.com/en/3.1.x/faq/#performance)
- Related RFC: `rfc-test-coverage-hardening.md`
