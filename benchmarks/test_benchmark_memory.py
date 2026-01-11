"""Memory profiling benchmarks using tracemalloc."""

from __future__ import annotations

import sys
import tracemalloc
from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from kida import Environment
from kida.bytecode_cache import BytecodeCache


def _peak_bytes(func, *args, **kwargs) -> int:
    tracemalloc.start()
    func(*args, **kwargs)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


@pytest.mark.benchmark(group="memory:render")
def test_memory_render_small(
    benchmark: BenchmarkFixture,
    kida_env: Environment,
    small_context: dict[str, object],
    gc_disabled,
) -> None:
    template = kida_env.get_template("small.html")

    def run() -> dict[str, int]:
        peak = _peak_bytes(template.render, **small_context)
        return {"peak_bytes": peak, "template_obj_size": sys.getsizeof(template)}

    result = benchmark(run)
    assert result["peak_bytes"] > 0


@pytest.mark.benchmark(group="memory:render")
def test_memory_render_large(
    benchmark: BenchmarkFixture,
    kida_env: Environment,
    large_context: dict[str, object],
    gc_disabled,
) -> None:
    template = kida_env.get_template("large.html")

    def run() -> dict[str, int]:
        peak = _peak_bytes(template.render, **large_context)
        return {"peak_bytes": peak, "template_obj_size": sys.getsizeof(template)}

    result = benchmark(run)
    assert result["peak_bytes"] > 0


@pytest.mark.benchmark(group="memory:cache")
def test_memory_bytecode_cache(benchmark: BenchmarkFixture, tmp_path: Path) -> None:
    cache_dir = tmp_path / "bytecode-cache"
    cache = BytecodeCache(cache_dir)
    source = "value = 1"

    def populate() -> dict[str, int]:
        from kida.bytecode_cache import hash_source

        code = compile(source, "<string>", "exec")
        cache.set("sample.html", hash_source(source), code)

        # Measure disk usage of the cached file
        cache_file = next(cache_dir.glob("__kida_*.pyc"))
        return {"disk_bytes": cache_file.stat().st_size}

    result = benchmark(populate)
    stats = cache.stats()
    assert stats["file_count"] >= 1
    assert result["disk_bytes"] > 0
