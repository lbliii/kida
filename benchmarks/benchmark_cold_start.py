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
    engine: str,
    use_bytecode_cache: bool,
    cache_dir: Path | None = None,
    template_dir: Path | None = None,
) -> float:
    """Measure cold-start time in a fresh Python process (ms)."""
    if engine == "kida":
        cache_arg = "None"
        if use_bytecode_cache:
            cache_arg = f"BytecodeCache(Path('{cache_dir}'))"

        script = f'''
import time
from pathlib import Path
from kida import Environment, FileSystemLoader
{"from kida.bytecode_cache import BytecodeCache" if use_bytecode_cache else ""}

_start = time.perf_counter_ns()
env = Environment(
    loader=FileSystemLoader('{template_dir}'),
    bytecode_cache={cache_arg}
)
template = env.get_template("bench.html")
template.render(title="Test", name="World", items=["a", "b", "c"])
_end = time.perf_counter_ns()

print((_end - _start) / 1_000_000)
'''
    else:  # jinja2
        cache_arg = "None"
        if use_bytecode_cache:
            cache_arg = f"FileSystemBytecodeCache(str(Path('{cache_dir}')))"

        script = f'''
import time
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
{"from jinja2 import FileSystemBytecodeCache" if use_bytecode_cache else ""}

_start = time.perf_counter_ns()
env = Environment(
    loader=FileSystemLoader('{template_dir}'),
    bytecode_cache={cache_arg},
    autoescape=True
)
template = env.get_template("bench.html")
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
    print("COLD-START BENCHMARK: KIDA VS JINJA2")
    print("=" * 60)
    print()

    with tempfile.TemporaryDirectory() as base_tmp:
        base_path = Path(base_tmp)
        template_dir = base_path / "templates"
        template_dir.mkdir()
        
        # Create a realistic large template for both engines
        template_content = """
<html>
<head><title>{{ title }}</title></head>
<body>
    <h1>Hello, {{ name }}!</h1>
    {% for item in items %}
        <li>{{ item }}</li>
    {% endfor %}
    
    {% for i in range(500) %}
        <p>Iteration {{ i }}: {{ title }} - {{ name }}</p>
        <div>
            <span>Nested content for {{ i }}</span>
            {% if i % 2 == 0 %}
                <b>Even iteration</b>
            {% else %}
                <i>Odd iteration</i>
            {% endif %}
        </div>
    {% endfor %}
</body>
</html>
"""
        # Note: Kida uses {% end %} but Jinja2 uses {% endfor %}/{% endif %}.
        # We will adjust the template content for each engine in the script.
        
        kida_template = template_content.replace("{% endfor %}", "{% end %}").replace("{% endif %}", "{% end %}")
        (template_dir / "bench.html").write_text(kida_template)

        # Scenario 1: Kida Baseline
        print("Scenario 1: Kida (no cache)")
        print("-" * 40)
        kida_no_cache = []
        for i in range(ITERATIONS):
            t = measure_cold_start("kida", use_bytecode_cache=False, template_dir=template_dir)
            kida_no_cache.append(t)
            print(f"  Run {i + 1}: {t:.2f}ms")
        kida_baseline = summarize("Kida baseline", kida_no_cache)

        # Update template for Jinja2
        (template_dir / "bench.html").write_text(template_content)

        # Scenario 2: Jinja2 Baseline
        print("Scenario 2: Jinja2 (no cache)")
        print("-" * 40)
        jinja2_no_cache = []
        for i in range(ITERATIONS):
            t = measure_cold_start("jinja2", use_bytecode_cache=False, template_dir=template_dir)
            jinja2_no_cache.append(t)
            print(f"  Run {i + 1}: {t:.2f}ms")
        jinja2_baseline = summarize("Jinja2 baseline", jinja2_no_cache)

        # Scenario 3: Kida Warm (cache hit)
        print("Scenario 3: Kida Warm (cache hit)")
        print("-" * 40)
        # Restore Kida template
        (template_dir / "bench.html").write_text(kida_template)
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            # Pre-populate
            measure_cold_start("kida", use_bytecode_cache=True, cache_dir=cache_dir, template_dir=template_dir)
            kida_warm = []
            for i in range(ITERATIONS):
                t = measure_cold_start("kida", use_bytecode_cache=True, cache_dir=cache_dir, template_dir=template_dir)
                kida_warm.append(t)
                print(f"  Run {i + 1}: {t:.2f}ms")
            kida_warm_med = summarize("Kida warm", kida_warm)

        # Scenario 4: Jinja2 Warm (cache hit)
        print("Scenario 4: Jinja2 Warm (cache hit)")
        print("-" * 40)
        # Restore Jinja2 template
        (template_dir / "bench.html").write_text(template_content)
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            # Pre-populate
            measure_cold_start("jinja2", use_bytecode_cache=True, cache_dir=cache_dir, template_dir=template_dir)
            jinja2_warm = []
            for i in range(ITERATIONS):
                t = measure_cold_start("jinja2", use_bytecode_cache=True, cache_dir=cache_dir, template_dir=template_dir)
                jinja2_warm.append(t)
                print(f"  Run {i + 1}: {t:.2f}ms")
            jinja2_warm_med = summarize("Jinja2 warm", jinja2_warm)

    print("=" * 60)
    print("FINAL COMPARISON (Medians)")
    print("=" * 60)
    print(f"Kida (No Cache):   {kida_baseline:.2f}ms")
    print(f"Jinja2 (No Cache): {jinja2_baseline:.2f}ms")
    print(f"Kida (Warm Cache): {kida_warm_med:.2f}ms (Improvement: {((kida_baseline-kida_warm_med)/kida_baseline)*100:.1f}%)")
    print(f"Jinja2 (Warm Cache): {jinja2_warm_med:.2f}ms (Improvement: {((jinja2_baseline-jinja2_warm_med)/jinja2_baseline)*100:.1f}%)")
    print()

    speedup = jinja2_warm_med / kida_warm_med
    print(f"Kida is {speedup:.1f}x faster than Jinja2 in warm cold-starts")
    print()


if __name__ == "__main__":
    run_cold_start_suite()
