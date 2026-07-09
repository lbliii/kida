"""Contract tests for the public render-capture/manifest example."""

from kida import (
    Fragment,
    FreezeCache,
    FreezeCacheStats,
    ManifestDiff,
    RenderCapture,
    RenderManifest,
    SearchEntry,
    SearchManifestBuilder,
    captured_render,
    default_field_extractor,
    get_capture,
)


def test_preferred_workflow_captures_diffs_caches_and_searches(example_app) -> None:
    result = example_app.result

    assert result["captured_urls"] == ["/guide", "/reference"]
    assert result["content_fragment"] == {
        "name": "content",
        "role": "content",
        "depends_on": ["doc.body", "doc.title"],
    }
    assert result["diff"] == {
        "added": ["/reference"],
        "removed": [],
        "changed": ["/guide"],
    }
    assert result["extracted_title"] == "Capture guide"
    assert result["search_entries"] == ["/guide", "/reference"]
    assert result["cached_blocks"] == ["nav"]
    assert result["cache_stats"] == {
        "hits": 1,
        "misses": 0,
        "invalidations": 0,
        "blocks_cached": 1,
    }
    assert "Preferred workflow" in result["rendered_guide"]


def test_every_retained_capture_export_is_directly_callable() -> None:
    fragment = Fragment(
        name="content",
        role="content",
        html="<main>Hello</main>",
        content_hash="abc123",
        depends_on=frozenset(),
        cache_scope="site",
    )
    capture = RenderCapture(
        template_name="page.html",
        blocks={"content": fragment},
        context_keys={},
    )
    stats = FreezeCacheStats()
    freeze = FreezeCache(stats=stats)
    manifest = RenderManifest(freeze_cache=freeze)
    manifest.add("/", capture)

    other = RenderManifest()
    diff = manifest.diff(other)
    explicit_diff = ManifestDiff(added=["/"], removed=[], changed={}, unchanged=0)
    entry = SearchEntry(t="Hello", body="Search body")
    search = SearchManifestBuilder().build(manifest)
    extracted = default_field_extractor("/", capture)

    assert get_capture() is None
    with captured_render() as active:
        assert get_capture() is active
    assert get_capture() is None

    assert isinstance(fragment, Fragment)
    assert isinstance(capture, RenderCapture)
    assert isinstance(stats, FreezeCacheStats)
    assert isinstance(freeze, FreezeCache)
    assert isinstance(manifest, RenderManifest)
    assert isinstance(diff, ManifestDiff)
    assert explicit_diff.added == ["/"]
    assert entry == {"t": "Hello", "body": "Search body"}
    assert isinstance(SearchManifestBuilder(), SearchManifestBuilder)
    assert search["entries"][0]["u"] == "/"
    assert extracted == {}
