"""Concurrency tests for BytecodeCache.

Verifies thread safety under concurrent get/set operations.
"""

from __future__ import annotations

import threading
from pathlib import Path
from types import CodeType

from kida.bytecode_cache import BytecodeCache, hash_source


def _make_code(name: str) -> CodeType:
    """Create a minimal code object for caching."""
    return compile(f"# {name}\nx = 1", "<test>", "exec")


class TestBytecodeCacheConcurrency:
    """BytecodeCache under concurrent get/set."""

    def test_concurrent_get_set_different_keys(self, tmp_path: Path) -> None:
        """16 threads get/set with different keys; no corruption."""
        cache = BytecodeCache(tmp_path)
        results: list[str | None] = []
        results_lock = threading.Lock()

        def worker(i: int) -> None:
            name = f"t{i}.html"
            source = f"{{{{ x{i} }}}}"
            h = hash_source(source)
            code = _make_code(name)
            cache.set(name, h, code)
            loaded = cache.get(name, h)
            with results_lock:
                results.append("ok" if loaded is not None else None)

        threads = [threading.Thread(target=lambda j=i: worker(j)) for i in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == "ok" for r in results)
        assert len(results) == 16

    def test_concurrent_get_set_same_key(self, tmp_path: Path) -> None:
        """Multiple threads set same key; get returns valid code."""
        cache = BytecodeCache(tmp_path)
        name = "shared.html"
        source = "{{ x }}"
        h = hash_source(source)
        code = _make_code(name)

        def writer() -> None:
            cache.set(name, h, code)

        def reader() -> str | None:
            loaded = cache.get(name, h)
            return "ok" if loaded is not None else None

        # First populate
        cache.set(name, h, code)

        results: list[str | None] = []
        results_lock = threading.Lock()

        def reader_task() -> None:
            r = reader()
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=reader_task) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == "ok" for r in results)

    def test_concurrent_mixed_get_set(self, tmp_path: Path) -> None:
        """Writers and readers interleaved; no corruption."""
        cache = BytecodeCache(tmp_path)
        errors: list[BaseException] = []
        errors_lock = threading.Lock()

        def writer(i: int) -> None:
            try:
                name = f"w{i}.html"
                h = hash_source(f"source{i}")
                cache.set(name, h, _make_code(name))
            except BaseException as e:
                with errors_lock:
                    errors.append(e)

        def reader(i: int) -> None:
            try:
                name = f"w{i}.html"
                h = hash_source(f"source{i}")
                _ = cache.get(name, h)
            except BaseException as e:
                with errors_lock:
                    errors.append(e)

        # Pre-populate
        for i in range(20):
            cache.set(f"w{i}.html", hash_source(f"source{i}"), _make_code(f"w{i}"))

        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=lambda j=i: writer(j)))
            threads.append(threading.Thread(target=lambda j=i: reader(j)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Unexpected errors: {errors}"
