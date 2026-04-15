"""Tests for kida.render_manifest — batch accumulation, search, and diffing."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from kida import DictLoader, Environment, captured_render
from kida.render_capture import Fragment, RenderCapture
from kida.render_manifest import (
    FreezeCache,
    ManifestDiff,
    RenderManifest,
    SearchManifestBuilder,
    default_field_extractor,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def capture_env():
    return Environment(
        loader=DictLoader(
            {
                "doc.html": (
                    "{% block content %}<main>{{ title }}: {{ body }}</main>{% end %}"
                    "{% block nav %}<nav>Nav</nav>{% end %}"
                ),
                "blog.html": "{% block content %}<article>{{ post }}</article>{% end %}",
            }
        ),
        enable_capture=True,
    )


def _render_page(env, template_name, url, ctx, manifest):
    """Helper: render a page and add to manifest."""
    t = env.get_template(template_name)
    with captured_render(capture_context=frozenset(ctx.keys())) as cap:
        t.render(**ctx)
    manifest.add(url, cap)
    return cap


# ---------------------------------------------------------------------------
# RenderManifest tests
# ---------------------------------------------------------------------------


class TestRenderManifest:
    def test_add_and_iterate(self, capture_env):
        manifest = RenderManifest()
        _render_page(capture_env, "doc.html", "/page1", {"title": "A", "body": "b"}, manifest)
        _render_page(capture_env, "doc.html", "/page2", {"title": "B", "body": "c"}, manifest)

        assert len(manifest.captures) == 2
        urls = [url for url, _ in manifest.captures]
        assert urls == ["/page1", "/page2"]

    def test_all_fragments(self, capture_env):
        manifest = RenderManifest()
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, manifest)

        frags = list(manifest.all_fragments())
        assert len(frags) == 2  # content + nav
        urls = {url for url, _ in frags}
        assert urls == {"/p1"}
        names = {f.name for _, f in frags}
        assert "content" in names
        assert "nav" in names

    def test_unique_content_hashes_dedup(self, capture_env):
        manifest = RenderManifest()
        # Same nav block rendered twice → same content_hash
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, manifest)
        _render_page(capture_env, "doc.html", "/p2", {"title": "B", "body": "c"}, manifest)

        hashes = manifest.unique_content_hashes()
        # Nav block is static → both pages produce same hash
        nav_hashes = [cap.blocks["nav"].content_hash for _, cap in manifest.captures]
        assert nav_hashes[0] == nav_hashes[1]
        assert hashes[nav_hashes[0]] == 2  # deduplicated


class TestManifestDiff:
    def test_no_changes(self, capture_env):
        m1 = RenderManifest()
        m2 = RenderManifest()
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, m1)
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, m2)

        diff = m2.diff(m1)
        assert diff.added == []
        assert diff.removed == []
        assert diff.changed == {}
        assert diff.unchanged == 1

    def test_added_page(self, capture_env):
        m1 = RenderManifest()
        m2 = RenderManifest()
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, m1)
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, m2)
        _render_page(capture_env, "doc.html", "/p2", {"title": "B", "body": "c"}, m2)

        diff = m2.diff(m1)
        assert diff.added == ["/p2"]
        assert diff.removed == []

    def test_removed_page(self, capture_env):
        m1 = RenderManifest()
        m2 = RenderManifest()
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, m1)
        _render_page(capture_env, "doc.html", "/p2", {"title": "B", "body": "c"}, m1)
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, m2)

        diff = m2.diff(m1)
        assert diff.removed == ["/p2"]
        assert diff.added == []

    def test_changed_block(self, capture_env):
        m1 = RenderManifest()
        m2 = RenderManifest()
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "old"}, m1)
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "new"}, m2)

        diff = m2.diff(m1)
        assert "/p1" in diff.changed
        assert "content" in diff.changed["/p1"]
        assert "nav" not in diff.changed["/p1"]  # nav didn't change

    def test_manifest_diff_frozen(self):
        diff = ManifestDiff(added=[], removed=[], changed={}, unchanged=0)
        with pytest.raises(AttributeError):
            diff.added = ["x"]


# ---------------------------------------------------------------------------
# SearchManifestBuilder tests
# ---------------------------------------------------------------------------


class TestSearchManifestBuilder:
    def test_basic_search_manifest(self, capture_env):
        manifest = RenderManifest()
        _render_page(capture_env, "doc.html", "/p1", {"title": "Hello", "body": "World"}, manifest)

        search = SearchManifestBuilder().build(manifest)
        assert search["version"] == 1
        assert len(search["entries"]) == 1
        entry = search["entries"][0]
        assert entry["u"] == "/p1"
        assert "body" in entry  # content block should be included
        assert entry["template"] == "doc.html"

    def test_navigation_excluded(self, capture_env):
        """Blocks with role='navigation' and weight=0 should not appear in body."""
        manifest = RenderManifest()
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, manifest)

        builder = SearchManifestBuilder()
        search = builder.build(manifest)
        entry = search["entries"][0]
        # Body should contain content block but NOT nav block
        assert "<main>" in entry["body"]
        assert "<nav>" not in entry["body"]

    def test_custom_role_weights(self, capture_env):
        """Custom weights can exclude or include different roles."""
        manifest = RenderManifest()
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, manifest)

        builder = SearchManifestBuilder(role_weights={"content": 0.0, "navigation": 1.0})
        search = builder.build(manifest)
        entry = search["entries"][0]
        # With inverted weights: nav included, content excluded
        assert "<nav>" in entry["body"]
        assert "<main>" not in entry["body"]

    def test_doc_context_extraction(self):
        """When context has a 'doc' object with metadata, it extracts facets."""

        @dataclass
        class Metadata:
            description: str = ""
            category: str = ""
            tags: frozenset[str] = frozenset()

        @dataclass
        class Doc:
            title: str = ""
            metadata: Metadata = None
            toc: list = None

        env = Environment(
            loader=DictLoader({"p.html": "{% block content %}{{ doc.title }}{% end %}"}),
            enable_capture=True,
        )
        doc = Doc(
            title="Test Page",
            metadata=Metadata(
                description="A test", category="Guides", tags=frozenset({"python", "kida"})
            ),
        )

        manifest = RenderManifest()
        t = env.get_template("p.html")
        with captured_render(capture_context=frozenset({"doc"})) as cap:
            t.render(doc=doc)
        manifest.add("/test", cap)

        search = SearchManifestBuilder().build(manifest)
        entry = search["entries"][0]
        assert entry["t"] == "Test Page"
        assert entry["d"] == "A test"
        assert entry["c"] == "Guides"
        assert sorted(entry["tags"]) == ["kida", "python"]
        assert search["facets"]["category"] == ["Guides"]
        assert search["facets"]["tags"] == ["kida", "python"]

    def test_multiple_pages(self, capture_env):
        manifest = RenderManifest()
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, manifest)
        _render_page(capture_env, "doc.html", "/p2", {"title": "B", "body": "c"}, manifest)
        _render_page(capture_env, "blog.html", "/blog/1", {"post": "Hello"}, manifest)

        search = SearchManifestBuilder().build(manifest)
        assert len(search["entries"]) == 3
        urls = [e["u"] for e in search["entries"]]
        assert "/p1" in urls
        assert "/p2" in urls
        assert "/blog/1" in urls

    def test_empty_manifest(self):
        search = SearchManifestBuilder().build(RenderManifest())
        assert search == {"version": 1, "facets": {}, "entries": []}

    def test_raw_body_from_doc_context(self):
        """When doc has .body, search entry uses raw text instead of rendered HTML."""

        @dataclass
        class Doc:
            title: str = ""
            body: str = ""

        env = Environment(
            loader=DictLoader(
                {"p.html": "{% block content %}<article>{{ doc.body }}</article>{% end %}"}
            ),
            enable_capture=True,
        )
        doc = Doc(title="Raw Test", body="This is **raw** markdown text")

        manifest = RenderManifest()
        t = env.get_template("p.html")
        with captured_render(capture_context=frozenset({"doc"})) as cap:
            t.render(doc=doc)
        manifest.add("/raw", cap)

        search = SearchManifestBuilder().build(manifest)
        entry = search["entries"][0]
        # Body should be raw text from doc.body, NOT the rendered HTML
        assert entry["body"] == "This is **raw** markdown text"
        assert "<article>" not in entry["body"]
        assert entry["t"] == "Raw Test"

    def test_html_fallback_when_no_doc_body(self, capture_env):
        """Without doc.body in context, falls back to HTML blocks."""
        manifest = RenderManifest()
        # _render_page captures {"title": ..., "body": ...} as flat strings,
        # not a structured doc object — no .body attribute on string
        _render_page(capture_env, "doc.html", "/p1", {"title": "A", "body": "b"}, manifest)

        search = SearchManifestBuilder().build(manifest)
        entry = search["entries"][0]
        # Should fall back to HTML since there's no doc.body
        assert "<main>" in entry["body"]

    def test_custom_field_extractor(self):
        """Custom extractor overrides all field extraction."""

        def my_extractor(url, capture):
            return {"t": f"Custom: {url}", "body": "custom body", "c": "MyCategory"}

        env = Environment(
            loader=DictLoader({"p.html": "{% block content %}hello{% end %}"}),
            enable_capture=True,
        )

        manifest = RenderManifest()
        t = env.get_template("p.html")
        with captured_render() as cap:
            t.render()
        manifest.add("/custom", cap)

        search = SearchManifestBuilder(field_extractor=my_extractor).build(manifest)
        entry = search["entries"][0]
        assert entry["t"] == "Custom: /custom"
        assert entry["body"] == "custom body"
        assert entry["c"] == "MyCategory"
        assert search["facets"]["category"] == ["MyCategory"]

    def test_extractor_without_body_triggers_html_fallback(self):
        """If extractor returns no body, HTML blocks are used as fallback."""

        def partial_extractor(url, capture):
            return {"t": "Title Only"}

        env = Environment(
            loader=DictLoader({"p.html": "{% block content %}<p>Hello</p>{% end %}"}),
            enable_capture=True,
        )

        manifest = RenderManifest()
        t = env.get_template("p.html")
        with captured_render() as cap:
            t.render()
        manifest.add("/partial", cap)

        search = SearchManifestBuilder(field_extractor=partial_extractor).build(manifest)
        entry = search["entries"][0]
        assert entry["t"] == "Title Only"
        # body falls back to HTML since extractor didn't provide it
        assert "<p>Hello</p>" in entry["body"]

    def test_default_field_extractor_with_content_attr(self):
        """default_field_extractor falls back to doc.content when doc.body missing."""

        @dataclass
        class Doc:
            title: str = ""
            content: str = ""

        env = Environment(
            loader=DictLoader({"p.html": "{% block content %}{{ doc.content }}{% end %}"}),
            enable_capture=True,
        )
        doc = Doc(title="Content Test", content="raw content here")

        manifest = RenderManifest()
        t = env.get_template("p.html")
        with captured_render(capture_context=frozenset({"doc"})) as cap:
            t.render(doc=doc)
        manifest.add("/content", cap)

        search = SearchManifestBuilder().build(manifest)
        entry = search["entries"][0]
        assert entry["body"] == "raw content here"

    def test_default_field_extractor_no_doc(self):
        """default_field_extractor returns empty dict when no doc in context."""
        cap = RenderCapture(context_keys={"title": "Hello"})
        result = default_field_extractor("/test", cap)
        assert result == {}


# ---------------------------------------------------------------------------
# FreezeCache tests
# ---------------------------------------------------------------------------


def _make_fragment(
    name: str,
    html: str,
    *,
    cache_scope: str = "site",
    depends_on: frozenset[str] = frozenset(),
    role: str = "unknown",
) -> Fragment:
    """Helper: create a Fragment with given properties."""
    from hashlib import sha256

    content_hash = sha256(html.encode("utf-8")).hexdigest()[:16]
    return Fragment(
        name=name,
        role=role,
        html=html,
        content_hash=content_hash,
        depends_on=depends_on,
        cache_scope=cache_scope,
    )


def _make_capture(template_name: str, fragments: list[Fragment]) -> RenderCapture:
    """Helper: create a RenderCapture with given fragments."""
    return RenderCapture(
        template_name=template_name,
        blocks={f.name: f for f in fragments},
    )


class TestFreezeCache:
    def test_records_site_scoped_blocks(self):
        """Site-scoped blocks with no deps are cached after record()."""
        cache = FreezeCache()
        cap = _make_capture(
            "base.html",
            [
                _make_fragment("nav", "<nav>Main</nav>", cache_scope="site"),
            ],
        )
        cache.record("base.html", cap)

        cached = cache.get_cached_blocks("base.html")
        assert cached is not None
        assert cached["nav"] == "<nav>Main</nav>"
        assert cache.stats.blocks_cached == 1

    def test_ignores_page_scoped_blocks(self):
        """Page-scoped blocks are NOT cached."""
        cache = FreezeCache()
        cap = _make_capture(
            "page.html",
            [
                _make_fragment("content", "<main>Hello</main>", cache_scope="page"),
            ],
        )
        cache.record("page.html", cap)

        assert cache.get_cached_blocks("page.html") is None

    def test_ignores_blocks_with_dependencies(self):
        """Even site-scoped blocks with depends_on are NOT cached."""
        cache = FreezeCache()
        cap = _make_capture(
            "page.html",
            [
                _make_fragment(
                    "content",
                    "<main>Hello</main>",
                    cache_scope="site",
                    depends_on=frozenset({"title"}),
                ),
            ],
        )
        cache.record("page.html", cap)

        assert cache.get_cached_blocks("page.html") is None

    def test_ignores_unknown_scope(self):
        """Unknown cache_scope blocks are not cached."""
        cache = FreezeCache()
        cap = _make_capture(
            "page.html",
            [
                _make_fragment("sidebar", "<aside>X</aside>", cache_scope="unknown"),
            ],
        )
        cache.record("page.html", cap)

        assert cache.get_cached_blocks("page.html") is None

    def test_ignores_none_scope(self):
        """Impure blocks (cache_scope='none') are never cached."""
        cache = FreezeCache()
        cap = _make_capture(
            "page.html",
            [
                _make_fragment("timestamp", "<time>now</time>", cache_scope="none"),
            ],
        )
        cache.record("page.html", cap)

        assert cache.get_cached_blocks("page.html") is None

    def test_content_hash_invalidation(self):
        """If a site-scoped block changes content, it gets invalidated."""
        cache = FreezeCache()

        cap1 = _make_capture(
            "base.html",
            [
                _make_fragment("nav", "<nav>V1</nav>", cache_scope="site"),
            ],
        )
        cache.record("base.html", cap1)
        assert cache.get_cached_blocks("base.html") is not None

        # Same block, different content — invalidate
        cap2 = _make_capture(
            "base.html",
            [
                _make_fragment("nav", "<nav>V2</nav>", cache_scope="site"),
            ],
        )
        cache.record("base.html", cap2)

        assert cache.get_cached_blocks("base.html") is None
        assert cache.stats.invalidations == 1

    def test_invalidated_block_stays_invalidated(self):
        """Once invalidated, a block cannot be re-cached."""
        cache = FreezeCache()

        cap1 = _make_capture(
            "base.html",
            [
                _make_fragment("nav", "<nav>V1</nav>", cache_scope="site"),
            ],
        )
        cache.record("base.html", cap1)

        # Invalidate
        cap2 = _make_capture(
            "base.html",
            [
                _make_fragment("nav", "<nav>V2</nav>", cache_scope="site"),
            ],
        )
        cache.record("base.html", cap2)

        # Try to re-cache original
        cache.record("base.html", cap1)
        assert cache.get_cached_blocks("base.html") is None

    def test_different_templates_isolated(self):
        """Blocks from different templates are cached independently."""
        cache = FreezeCache()

        cap1 = _make_capture(
            "a.html",
            [
                _make_fragment("nav", "<nav>A</nav>", cache_scope="site"),
            ],
        )
        cap2 = _make_capture(
            "b.html",
            [
                _make_fragment("nav", "<nav>B</nav>", cache_scope="site"),
            ],
        )
        cache.record("a.html", cap1)
        cache.record("b.html", cap2)

        assert cache.get_cached_blocks("a.html") == {"nav": "<nav>A</nav>"}
        assert cache.get_cached_blocks("b.html") == {"nav": "<nav>B</nav>"}

    def test_get_cached_blocks_returns_none_for_unknown_template(self):
        cache = FreezeCache()
        assert cache.get_cached_blocks("unknown.html") is None

    def test_stats_tracking(self):
        cache = FreezeCache()

        cap = _make_capture(
            "base.html",
            [
                _make_fragment("nav", "<nav>X</nav>", cache_scope="site"),
                _make_fragment("footer", "<footer>Y</footer>", cache_scope="site"),
                _make_fragment("content", "<main>Z</main>", cache_scope="page"),
            ],
        )
        cache.record("base.html", cap)

        assert cache.stats.blocks_cached == 2  # nav + footer
        cache.get_cached_blocks("base.html")  # hit
        assert cache.stats.cache_hits == 2  # 2 blocks returned
        cache.get_cached_blocks("other.html")  # miss
        assert cache.stats.cache_misses == 1

    def test_manifest_integration_auto_records(self):
        """RenderManifest with freeze_cache auto-records on add()."""
        freeze = FreezeCache()
        manifest = RenderManifest(freeze_cache=freeze)

        cap = _make_capture(
            "base.html",
            [
                _make_fragment("nav", "<nav>Nav</nav>", cache_scope="site"),
            ],
        )
        manifest.add("/page1", cap)

        cached = freeze.get_cached_blocks("base.html")
        assert cached is not None
        assert cached["nav"] == "<nav>Nav</nav>"

    def test_manifest_without_freeze_cache(self):
        """RenderManifest without freeze_cache works normally."""
        manifest = RenderManifest()
        cap = _make_capture(
            "base.html",
            [
                _make_fragment("nav", "<nav>Nav</nav>", cache_scope="site"),
            ],
        )
        manifest.add("/page1", cap)
        assert len(manifest.captures) == 1
        assert manifest.freeze_cache is None


class TestFreezeCacheIntegration:
    """End-to-end tests using real template compilation and rendering."""

    def test_freeze_loop_caches_static_blocks(self):
        """Full freeze loop: nav block cached after first render, reused."""
        env = Environment(
            loader=DictLoader(
                {
                    "page.html": (
                        "{% block content %}<main>{{ title }}</main>{% end %}"
                        "{% block nav %}<nav>Static Nav</nav>{% end %}"
                    ),
                }
            ),
            enable_capture=True,
            preserve_ast=True,
        )

        manifest = RenderManifest(freeze_cache=FreezeCache())

        # First render — populates cache
        t = env.get_template("page.html")
        with captured_render(capture_context=frozenset({"title"})) as cap1:
            t.render(title="Page 1")
        manifest.add("/page1", cap1)

        # Check that nav is cached (static, no deps, site-scoped)
        cached = manifest.freeze_cache.get_cached_blocks("page.html")
        assert cached is not None
        assert "nav" in cached
        # content should NOT be cached (has depends_on={"title"})
        assert "content" not in cached

    def test_freeze_loop_with_cached_blocks_injection(self):
        """Cached blocks injected via _cached_blocks produce same output."""
        env = Environment(
            loader=DictLoader(
                {
                    "page.html": (
                        "{% block content %}<main>{{ title }}</main>{% end %}"
                        "{% block nav %}<nav>Static</nav>{% end %}"
                    ),
                }
            ),
            enable_capture=True,
            preserve_ast=True,
        )

        manifest = RenderManifest(freeze_cache=FreezeCache())

        # First render — seeds cache
        t = env.get_template("page.html")
        with captured_render(capture_context=frozenset({"title"})) as cap1:
            html1 = t.render(title="Page 1")
        manifest.add("/page1", cap1)

        # Second render — inject cached blocks
        cached = manifest.freeze_cache.get_cached_blocks("page.html")
        with captured_render(capture_context=frozenset({"title"})) as cap2:
            html2 = t.render(title="Page 2", _cached_blocks=cached)
        manifest.add("/page2", cap2)

        # Both should produce valid HTML
        assert "<main>Page 1</main>" in html1
        assert "<main>Page 2</main>" in html2
        # Nav should be the same static content
        assert "<nav>Static</nav>" in html1
        assert "<nav>Static</nav>" in html2

    def test_capture_records_cached_blocks(self):
        """Capture hook fires for blocks served from CachedBlocksDict."""
        env = Environment(
            loader=DictLoader(
                {
                    "page.html": (
                        "{% block content %}<main>{{ title }}</main>{% end %}"
                        "{% block nav %}<nav>Static</nav>{% end %}"
                    ),
                }
            ),
            enable_capture=True,
            preserve_ast=True,
        )

        manifest = RenderManifest(freeze_cache=FreezeCache())

        # First render — seeds cache
        t = env.get_template("page.html")
        with captured_render(capture_context=frozenset({"title"})) as cap1:
            t.render(title="Page 1")
        manifest.add("/page1", cap1)

        # Second render — inject cached nav block
        cached = manifest.freeze_cache.get_cached_blocks("page.html")
        assert cached is not None
        with captured_render(capture_context=frozenset({"title"})) as cap2:
            t.render(title="Page 2", _cached_blocks=cached)
        manifest.add("/page2", cap2)

        # Capture should have recorded the nav block even though it was served
        # from CachedBlocksDict (the capture hook fires on the return value)
        assert "nav" in cap2.blocks
        assert cap2.blocks["nav"].html == "<nav>Static</nav>"
        # Content should also be captured with new value
        assert "content" in cap2.blocks
        assert "<main>Page 2</main>" in cap2.blocks["content"].html
