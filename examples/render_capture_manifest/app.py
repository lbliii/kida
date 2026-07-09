"""Render capture and manifest workflow for build and search tooling.

Run:
    python app.py
"""

import json
from dataclasses import dataclass, field
from typing import Any

from kida import (
    DictLoader,
    Environment,
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


@dataclass(frozen=True, slots=True)
class Metadata:
    description: str
    category: str
    tags: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class Doc:
    title: str
    body: str
    metadata: Metadata


TEMPLATE_SOURCE = (
    "{% block content %}<main><h1>{{ doc.title }}</h1>{{ doc.body }}</main>{% end %}"
    "{% block nav %}<nav>Documentation</nav>{% end %}"
)


def capture_page(
    environment: Environment,
    manifest: RenderManifest,
    *,
    url: str,
    doc: Doc,
) -> str:
    """Render one page into its caller-owned manifest."""
    template = environment.get_template("page.html")
    assert get_capture() is None
    with captured_render(capture_context=frozenset({"doc"})) as capture:
        assert get_capture() is capture
        html = template.render(doc=doc)
    assert get_capture() is None
    manifest.add(url, capture)
    return html


def build_demo() -> dict[str, Any]:
    """Run capture, manifest diff, freeze-cache inspection, and search indexing."""
    environment = Environment(
        loader=DictLoader({"page.html": TEMPLATE_SOURCE}),
        enable_capture=True,
    )

    old_manifest = RenderManifest()
    old_doc = Doc(
        title="Capture guide",
        body="Old workflow",
        metadata=Metadata("Capture rendered blocks", "Guides", frozenset({"capture"})),
    )
    capture_page(environment, old_manifest, url="/guide", doc=old_doc)

    freeze_cache = FreezeCache()
    new_manifest = RenderManifest(freeze_cache=freeze_cache)
    new_doc = Doc(
        title="Capture guide",
        body="Preferred workflow",
        metadata=Metadata(
            "Capture rendered blocks",
            "Guides",
            frozenset({"capture", "manifest"}),
        ),
    )
    reference_doc = Doc(
        title="Manifest reference",
        body="Inspect and compare render facts",
        metadata=Metadata("Manifest API", "Reference", frozenset({"manifest"})),
    )
    guide_html = capture_page(environment, new_manifest, url="/guide", doc=new_doc)
    capture_page(environment, new_manifest, url="/reference", doc=reference_doc)

    diff = new_manifest.diff(old_manifest)
    assert isinstance(diff, ManifestDiff)

    _, guide_capture = new_manifest.captures[0]
    assert isinstance(guide_capture, RenderCapture)
    content = guide_capture.blocks["content"]
    assert isinstance(content, Fragment)

    extracted: SearchEntry = default_field_extractor("/guide", guide_capture)
    search = SearchManifestBuilder().build(new_manifest)

    cached_blocks = freeze_cache.get_cached_blocks("page.html")
    stats = freeze_cache.stats
    assert isinstance(stats, FreezeCacheStats)

    return {
        "captured_urls": [url for url, _ in new_manifest.captures],
        "content_fragment": {
            "name": content.name,
            "role": content.role,
            "depends_on": sorted(content.depends_on),
        },
        "diff": {
            "added": diff.added,
            "removed": diff.removed,
            "changed": sorted(diff.changed),
        },
        "extracted_title": extracted["t"],
        "search_entries": [entry["u"] for entry in search["entries"]],
        "cached_blocks": sorted(cached_blocks or {}),
        "cache_stats": {
            "hits": stats.cache_hits,
            "misses": stats.cache_misses,
            "invalidations": stats.invalidations,
            "blocks_cached": stats.blocks_cached,
        },
        "rendered_guide": guide_html,
    }


result = build_demo()


def main() -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
