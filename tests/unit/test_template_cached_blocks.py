"""Unit tests for CachedBlocksDict."""

from __future__ import annotations

import threading

import pytest

from kida.template import CachedBlocksDict

# ---------------------------------------------------------------------------
# Basic hit/miss tracking
# ---------------------------------------------------------------------------


def test_cached_blocks_dict_hits_and_misses() -> None:
    stats: dict[str, int] = {}
    cached = {"nav": "<nav>hi</nav>"}
    original = {"other": lambda *_: "orig"}
    proxy = CachedBlocksDict(original, cached, set(cached), stats=stats)

    # Cache hit returns wrapper and increments stats
    wrapper = proxy.get("nav")
    assert callable(wrapper)
    assert wrapper({}, {}) == "<nav>hi</nav>"
    assert stats["hits"] == 1

    # Miss falls back to original and records miss
    assert proxy.get("other")("ctx", {}) == "orig"
    assert stats["misses"] == 1

    # setdefault honors cache priority
    wrapper2 = proxy.setdefault("nav")
    assert callable(wrapper2)
    assert wrapper2({}, {}) == "<nav>hi</nav>"
    assert stats["hits"] == 2

    # __contains__ sees both original and cached keys
    assert "nav" in proxy and "other" in proxy


def test_cached_blocks_dict_copy_includes_wrappers() -> None:
    stats: dict[str, int] = {}
    cached = {"footer": "<footer>cached</footer>"}
    proxy = CachedBlocksDict({}, cached, set(cached), stats=stats)

    copied = proxy.copy()
    assert "footer" in copied
    # Wrapped copy increments hits when invoked
    assert copied["footer"]({}, {}) == "<footer>cached</footer>"
    assert stats["hits"] == 1


# ---------------------------------------------------------------------------
# __getitem__ / __setitem__
# ---------------------------------------------------------------------------


def test_getitem_cached_hit() -> None:
    stats: dict[str, int] = {}
    cached = {"header": "<header>H</header>"}
    proxy = CachedBlocksDict({}, cached, set(cached), stats=stats)

    wrapper = proxy["header"]
    assert wrapper({}, {}) == "<header>H</header>"
    assert stats["hits"] == 1


def test_getitem_miss_falls_to_original() -> None:
    stats: dict[str, int] = {}
    original = {"body": lambda *_: "body_content"}
    proxy = CachedBlocksDict(original, {}, set(), stats=stats)

    result = proxy["body"]
    assert result("ctx", {}) == "body_content"
    assert stats["misses"] == 1


def test_getitem_missing_key_raises() -> None:
    proxy = CachedBlocksDict({}, {}, set())
    with pytest.raises(KeyError):
        proxy["nonexistent"]


def test_setitem_stores_in_original() -> None:
    original: dict = {}
    proxy = CachedBlocksDict(original, {}, set())
    proxy["new_block"] = lambda *_: "new"
    assert "new_block" in original
    assert original["new_block"]("ctx", {}) == "new"


# ---------------------------------------------------------------------------
# setdefault miss tracking
# ---------------------------------------------------------------------------


def _stub(*_: object) -> str:
    return "default"


def test_setdefault_miss_records_stat() -> None:
    stats: dict[str, int] = {}
    original: dict = {}
    proxy = CachedBlocksDict(original, {}, set(), stats=stats)

    result = proxy.setdefault("missing", _stub)
    assert result is _stub
    assert stats["misses"] == 1


def test_setdefault_existing_original() -> None:
    def existing_fn(*_: object) -> str:
        return "existing"

    original = {"block": existing_fn}
    stats: dict[str, int] = {}
    proxy = CachedBlocksDict(original, {}, set(), stats=stats)

    result = proxy.setdefault("block", _stub)
    assert result is existing_fn
    assert stats["misses"] == 1


# ---------------------------------------------------------------------------
# keys()
# ---------------------------------------------------------------------------


def test_keys_union() -> None:
    original = {"a": lambda *_: "a", "b": lambda *_: "b"}
    cached = {"c": "<c/>"}
    proxy = CachedBlocksDict(original, cached, set(cached))

    keys = proxy.keys()
    assert keys == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# __contains__
# ---------------------------------------------------------------------------


def test_contains_cached_only() -> None:
    proxy = CachedBlocksDict({}, {"x": "val"}, {"x"})
    assert "x" in proxy
    assert "y" not in proxy


def test_contains_original_only() -> None:
    proxy = CachedBlocksDict({"x": lambda *_: ""}, {}, set())
    assert "x" in proxy


# ---------------------------------------------------------------------------
# None original
# ---------------------------------------------------------------------------


def test_none_original_handled() -> None:
    proxy = CachedBlocksDict(None, {"nav": "<nav/>"}, {"nav"})
    assert proxy.get("nav")({}, {}) == "<nav/>"
    assert proxy.get("missing") is None


# ---------------------------------------------------------------------------
# copy() without stats
# ---------------------------------------------------------------------------


def test_copy_without_stats_reuses_wrappers() -> None:
    cached = {"nav": "<nav/>"}
    proxy = CachedBlocksDict({"body": lambda *_: "B"}, cached, set(cached), stats=None)

    copied = proxy.copy()
    assert "nav" in copied
    assert "body" in copied
    assert copied["nav"]({}, {}) == "<nav/>"


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_concurrent_access() -> None:
    """Verify thread-safe stats recording under contention."""
    stats: dict[str, int] = {}
    cached = {"nav": "<nav/>"}
    original = {"body": lambda *_: "body"}
    proxy = CachedBlocksDict(original, cached, set(cached), stats=stats)

    errors: list[Exception] = []
    iterations = 500

    def hammer_hits() -> None:
        try:
            for _ in range(iterations):
                proxy.get("nav")
        except Exception as e:
            errors.append(e)

    def hammer_misses() -> None:
        try:
            for _ in range(iterations):
                proxy.get("body")
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=hammer_hits),
        threading.Thread(target=hammer_hits),
        threading.Thread(target=hammer_misses),
        threading.Thread(target=hammer_misses),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert stats["hits"] == iterations * 2
    assert stats["misses"] == iterations * 2
