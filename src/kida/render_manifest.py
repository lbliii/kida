"""Kida RenderManifest — batch capture accumulation, search indexing, and diffing.

Accumulates RenderCapture objects across multiple renders (e.g., during a
static site freeze) and provides search manifest generation and semantic
diffing between deploy snapshots.

RFC: render-capture

Example:
    from kida import Environment, FileSystemLoader, captured_render
    from kida.render_manifest import RenderManifest, SearchManifestBuilder

    env = Environment(loader=FileSystemLoader("templates/"), enable_capture=True)
    manifest = RenderManifest()

    for url, template_name, ctx in pages:
        template = env.get_template(template_name)
        with captured_render(capture_context=frozenset(ctx.keys())) as cap:
            html = template.render(**ctx)
        manifest.add(url, cap)

    # Auto-derive search index from block roles
    search = SearchManifestBuilder().build(manifest)
    print(search)

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from kida.render_capture import Fragment, RenderCapture


@dataclass(frozen=True, slots=True)
class ManifestDiff:
    """Result of comparing two RenderManifests.

    Attributes:
        added: URLs present in new manifest but not old
        removed: URLs present in old manifest but not new
        changed: URL -> {block_name -> (old_hash, new_hash)} for changed blocks
        unchanged: Count of URLs with identical content
    """

    added: list[str]
    removed: list[str]
    changed: dict[str, dict[str, tuple[str, str]]]
    unchanged: int


@dataclass(slots=True)
class RenderManifest:
    """Accumulates captures across a batch of renders.

    Each entry is a (url, RenderCapture) pair representing one rendered page.
    Provides search index generation, semantic diffing, and cache analysis.

    Attributes:
        version: Manifest format version
        captures: List of (url, capture) pairs in insertion order
    """

    version: int = 1
    captures: list[tuple[str, RenderCapture]] = field(default_factory=list)

    def add(self, url: str, capture: RenderCapture) -> None:
        """Add a rendered page's capture to the manifest.

        Args:
            url: The URL or path of the rendered page
            capture: The RenderCapture from rendering this page
        """
        self.captures.append((url, capture))

    def all_fragments(self) -> Iterator[tuple[str, Fragment]]:
        """Iterate over all (url, fragment) pairs across all captures.

        Yields:
            (url, fragment) tuples for every block in every captured page
        """
        for url, cap in self.captures:
            for frag in cap.blocks.values():
                yield url, frag

    def unique_content_hashes(self) -> dict[str, int]:
        """Count unique content hashes across all fragments.

        Returns:
            Dict mapping content_hash -> number of occurrences.
            Hashes with count > 1 represent deduplatable content.
        """
        counts: dict[str, int] = {}
        for _, frag in self.all_fragments():
            counts[frag.content_hash] = counts.get(frag.content_hash, 0) + 1
        return counts

    def diff(self, other: RenderManifest) -> ManifestDiff:
        """Compute semantic diff between this manifest and another.

        Compares by URL, then by block content_hash within each URL.

        Args:
            other: The older manifest to compare against.

        Returns:
            ManifestDiff with added, removed, changed URLs and block-level changes.
        """
        self_urls = dict(self.captures)
        other_urls = dict(other.captures)

        added = [url for url in self_urls if url not in other_urls]
        removed = [url for url in other_urls if url not in self_urls]

        changed: dict[str, dict[str, tuple[str, str]]] = {}
        unchanged = 0

        for url in self_urls:
            if url not in other_urls:
                continue
            self_cap = self_urls[url]
            other_cap = other_urls[url]

            block_changes: dict[str, tuple[str, str]] = {}
            all_block_names = set(self_cap.blocks.keys()) | set(other_cap.blocks.keys())
            for block_name in all_block_names:
                self_frag = self_cap.blocks.get(block_name)
                other_frag = other_cap.blocks.get(block_name)
                if self_frag is None or other_frag is None:
                    # Block added or removed — report as change
                    self_hash = self_frag.content_hash if self_frag else ""
                    other_hash = other_frag.content_hash if other_frag else ""
                    block_changes[block_name] = (other_hash, self_hash)
                elif self_frag.content_hash != other_frag.content_hash:
                    block_changes[block_name] = (other_frag.content_hash, self_frag.content_hash)

            if block_changes:
                changed[url] = block_changes
            else:
                unchanged += 1

        return ManifestDiff(
            added=added,
            removed=removed,
            changed=changed,
            unchanged=unchanged,
        )


# Default role weights for search relevance
_DEFAULT_ROLE_WEIGHTS: dict[str, float] = {
    "content": 1.0,
    "sidebar": 0.3,
    "header": 0.2,
    "footer": 0.0,
    "navigation": 0.0,
    "unknown": 0.5,
}


@dataclass(slots=True)
class SearchManifestBuilder:
    """Builds a search manifest from a RenderManifest using block roles.

    Uses BlockMetadata.inferred_role to automatically classify blocks:
    - "content" blocks provide searchable text
    - "navigation" and "footer" blocks are excluded
    - Context keys provide facets when available

    Attributes:
        role_weights: Mapping of role -> weight (0.0 = excluded from search)
    """

    role_weights: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_ROLE_WEIGHTS))

    def build(self, manifest: RenderManifest) -> dict[str, Any]:
        """Build a search manifest from captured renders.

        Args:
            manifest: RenderManifest containing captured page data

        Returns:
            Search manifest dict with version, facets, and entries.
            Compatible with Chirp's search manifest format.
        """
        entries: list[dict[str, Any]] = []
        all_tags: set[str] = set()
        all_categories: set[str] = set()

        for url, cap in manifest.captures:
            entry: dict[str, Any] = {"u": url}

            # Extract title from context if available
            ctx = cap.context_keys
            if "doc" in ctx:
                doc = ctx["doc"]
                if hasattr(doc, "title"):
                    entry["t"] = doc.title
                if hasattr(doc, "metadata"):
                    meta = doc.metadata
                    if hasattr(meta, "description"):
                        entry["d"] = meta.description
                    if hasattr(meta, "category") and meta.category:
                        entry["c"] = meta.category
                        all_categories.add(meta.category)
                    if hasattr(meta, "tags") and meta.tags:
                        entry["tags"] = sorted(meta.tags)
                        all_tags.update(meta.tags)
                if hasattr(doc, "toc") and doc.toc:
                    entry["toc"] = [
                        {"level": e.level, "id": e.id, "text": e.text}
                        for e in doc.toc
                        if hasattr(e, "level") and hasattr(e, "id") and hasattr(e, "text")
                    ]

            # Extract body text from content-role blocks
            body_parts: list[str] = []
            for frag in cap.blocks.values():
                weight = self.role_weights.get(frag.role, 0.5)
                if weight > 0:
                    body_parts.append(frag.html)

            if body_parts:
                entry["body"] = "\n".join(body_parts)

            # Use template name and capture info for metadata
            if cap.template_name:
                entry["template"] = cap.template_name

            entries.append(entry)

        facets: dict[str, list[str]] = {}
        if all_categories:
            facets["category"] = sorted(all_categories)
        if all_tags:
            facets["tags"] = sorted(all_tags)

        return {
            "version": manifest.version,
            "facets": facets,
            "entries": entries,
        }
