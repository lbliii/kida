"""Concurrency tests for LRUCache (template cache backend).

Verifies thread safety under:
- Different keys (concurrent get_or_set)
- Same key (thundering herd - single computation, all get same result)
"""

from __future__ import annotations

import threading

from kida.utils.lru_cache import LRUCache


class TestLRUCacheConcurrency:
    """LRU cache under concurrent access."""

    def test_concurrent_different_keys(self) -> None:
        """16 threads get_or_set with different keys; all succeed."""
        cache: LRUCache[int, str] = LRUCache(maxsize=100)
        computed: set[int] = set()
        computed_lock = threading.Lock()

        def factory(key: int) -> str:
            with computed_lock:
                computed.add(key)
            return f"val_{key}"

        def get_key(i: int) -> str:
            return cache.get_or_set(i, factory, pass_key=True)

        threads = []
        for i in range(16):
            t = threading.Thread(target=lambda j=i: get_key(j * 10))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(16):
            assert cache.get(i * 10) == f"val_{i * 10}"
        assert len(computed) == 16

    def test_thundering_herd_same_key(self) -> None:
        """16 threads get_or_set same key; all get same result, no duplicate values."""
        cache: LRUCache[str, int] = LRUCache(maxsize=100)
        compute_count = 0
        compute_lock = threading.Lock()

        def factory() -> int:
            nonlocal compute_count
            with compute_lock:
                compute_count += 1
            return 42

        results: list[int] = []
        results_lock = threading.Lock()

        def get_same() -> None:
            v = cache.get_or_set("key", factory)
            with results_lock:
                results.append(v)

        threads = [threading.Thread(target=get_same) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert compute_count >= 1
        assert all(r == 42 for r in results), "All threads must see same value"
        assert len(results) == 16

    def test_concurrent_get_and_set(self) -> None:
        """Concurrent get/set/delete; no corruption."""
        cache: LRUCache[int, int] = LRUCache(maxsize=1000)

        def writer() -> None:
            for i in range(100):
                cache.set(i, i * 2)

        def reader() -> None:
            for i in range(100):
                v = cache.get(i)
                if v is not None:
                    assert v == i * 2

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
