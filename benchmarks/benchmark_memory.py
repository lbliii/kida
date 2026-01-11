"""Memory profiling benchmarks using tracemalloc."""

from __future__ import annotations

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
) -> None:
    template = kida_env.get_template("small.html")

    def run() -> int:
        return _peak_bytes(template.render, **small_context)

    peak = benchmark(run)
    assert peak > 0


@pytest.mark.benchmark(group="memory:render")
def test_memory_render_large(
    benchmark: BenchmarkFixture,
    kida_env: Environment,
    large_context: dict[str, object],
) -> None:
    template = kida_env.get_template("large.html")

    def run() -> int:
        return _peak_bytes(template.render, **large_context)

    peak = benchmark(run)
    assert peak > 0


@pytest.mark.benchmark(group="memory:cache")
def test_memory_bytecode_cache(benchmark: BenchmarkFixture, tmp_path: Path) -> None:
    cache_dir = tmp_path / "bytecode-cache"
    cache = BytecodeCache(cache_dir)
    source = "value = 1"

    def populate() -> None:
        from kida.bytecode_cache import hash_source

        code = compile(source, "<string>", "exec")
        cache.set("sample.html", hash_source(source), code)

    benchmark(populate)
    stats = cache.stats()
    assert stats["file_count"] >= 1
