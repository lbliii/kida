"""Tests for kida.render_manifest — batch accumulation, search, and diffing."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from kida import DictLoader, Environment, captured_render
from kida.render_manifest import ManifestDiff, RenderManifest, SearchManifestBuilder

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
