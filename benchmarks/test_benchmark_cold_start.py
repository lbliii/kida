"""Cold-start performance benchmarks (pytest wrapper).

Measures time from fresh import to first render completion via subprocess.
Wraps logic from benchmark_cold_start.py for pytest-benchmark integration.

Run with: pytest benchmarks/test_benchmark_cold_start.py --benchmark-only -v

For manual runs with full output: python benchmarks/benchmark_cold_start.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture


def _measure_cold_start(
    engine: str,
    use_bytecode_cache: bool,
    cache_dir: Path,
    template_dir: Path,
) -> float:
    """Measure cold-start time in a fresh Python process (ms)."""
    if engine == "kida":
        cache_arg = "None"
        if use_bytecode_cache:
            cache_arg = f"BytecodeCache(Path('{cache_dir}'))"
        script = f"""
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
"""
    else:  # jinja2
        cache_arg = "None"
        if use_bytecode_cache:
            cache_arg = f"FileSystemBytecodeCache(str(Path('{cache_dir}')))"
        script = f"""
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
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if result.returncode != 0:
        raise RuntimeError(f"Cold-start measurement failed: {result.stderr}")
    return float(result.stdout.strip())


def _setup_bench_template(tmp_path: Path) -> Path:
    """Create bench.html for Kida (uses {% end %})."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    content = """
<html>
<head><title>{{ title }}</title></head>
<body>
    <h1>Hello, {{ name }}!</h1>
    {% for item in items %}
        <li>{{ item }}</li>
    {% end %}
</body>
</html>
"""
    (template_dir / "bench.html").write_text(content)
    return template_dir


def _setup_bench_template_jinja2(tmp_path: Path) -> Path:
    """Create bench.html for Jinja2 (uses {% endfor %})."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    content = """
<html>
<head><title>{{ title }}</title></head>
<body>
    <h1>Hello, {{ name }}!</h1>
    {% for item in items %}
        <li>{{ item }}</li>
    {% endfor %}
</body>
</html>
"""
    (template_dir / "bench.html").write_text(content)
    return template_dir


@pytest.mark.benchmark(group="cold-start:kida")
def test_cold_start_kida_no_cache(
    benchmark: BenchmarkFixture, tmp_path: Path
) -> None:
    """Kida: Cold-start without bytecode cache."""
    template_dir = _setup_bench_template(tmp_path)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    def run():
        return _measure_cold_start(
            "kida", use_bytecode_cache=False, cache_dir=cache_dir, template_dir=template_dir
        )

    result = benchmark(run)
    assert result > 0


@pytest.mark.benchmark(group="cold-start:kida")
def test_cold_start_kida_with_cache(
    benchmark: BenchmarkFixture, tmp_path: Path
) -> None:
    """Kida: Cold-start with bytecode cache (warm cache)."""
    template_dir = _setup_bench_template(tmp_path)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    # Pre-populate cache
    _measure_cold_start(
        "kida", use_bytecode_cache=True, cache_dir=cache_dir, template_dir=template_dir
    )

    def run():
        return _measure_cold_start(
            "kida", use_bytecode_cache=True, cache_dir=cache_dir, template_dir=template_dir
        )

    result = benchmark(run)
    assert result > 0


@pytest.mark.benchmark(group="cold-start:jinja2")
def test_cold_start_jinja2_no_cache(
    benchmark: BenchmarkFixture, tmp_path: Path
) -> None:
    """Jinja2: Cold-start without bytecode cache."""
    template_dir = _setup_bench_template_jinja2(tmp_path)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    def run():
        return _measure_cold_start(
            "jinja2",
            use_bytecode_cache=False,
            cache_dir=cache_dir,
            template_dir=template_dir,
        )

    result = benchmark(run)
    assert result > 0
