"""Cold-start performance benchmarks.

Measures time from fresh import to first render completion.
Validates the "90%+ cold-start improvement" claim.

Run with: python benchmarks/benchmark_cold_start.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from statistics import mean, median, stdev

ITERATIONS = 10


def measure_cold_start(
    use_bytecode_cache: bool,
    cache_dir: Path | None = None,
) -> float:
    """Measure cold-start time in a fresh Python process (ms)."""
    cache_arg = "None"
    if use_bytecode_cache:
        cache_arg = f"BytecodeCache(Path('{cache_dir}'))"

    script = f'''
import time
from pathlib import Path
from kida import Environment
{"from kida.bytecode_cache import BytecodeCache" if use_bytecode_cache else ""}

_start = time.perf_counter_ns()
env = Environment(bytecode_cache={cache_arg})
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
template.render(title="Test", name="World", items=["a", "b", "c"])
_end = time.perf_counter_ns()

print((_end - _start) / 1_000_000)
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


def summarize(label: str, values: Sequence[float]) -> None:
    print(f"\nSummary: {label}")
    med = median(values)
    avg = mean(values)
    sd = stdev(values) if len(values) > 1 else 0.0
    print(f"  Median: {med:.2f}ms")
    print(f"  Mean:   {avg:.2f}ms")
    print(f"  Stdev:  {sd:.2f}ms")
    print()
    return med


def run_cold_start_suite() -> None:
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
        print(f"  Run {i + 1}: {t:.2f}ms")

    baseline = summarize("baseline", no_cache_times)

    # Scenario 2: Bytecode cache cold (first population)
    print("Scenario 2: Bytecode cache cold (first population)")
    print("-" * 40)
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        cache_cold_times = []
        for i in range(ITERATIONS):
            for f in cache_dir.glob("__kida_*.pyc"):
                f.unlink()
            t = measure_cold_start(use_bytecode_cache=True, cache_dir=cache_dir)
            cache_cold_times.append(t)
            print(f"  Run {i + 1}: {t:.2f}ms")

        cache_cold_median = summarize("cache cold", cache_cold_times)

        print("Scenario 3: Bytecode cache warm (cache hit)")
        print("-" * 40)
        # Pre-populate cache
        measure_cold_start(use_bytecode_cache=True, cache_dir=cache_dir)

        cache_warm_times = []
        for i in range(ITERATIONS):
            t = measure_cold_start(use_bytecode_cache=True, cache_dir=cache_dir)
            cache_warm_times.append(t)
            print(f"  Run {i + 1}: {t:.2f}ms")

        cache_warm_median = summarize("cache warm", cache_warm_times)

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
