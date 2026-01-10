from kida.template import CachedBlocksDict


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
