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
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from kida.render_capture import Fragment, RenderCapture


class SearchEntry(TypedDict, total=False):
    """Fields extractable from a RenderCapture for search indexing.

    All fields are optional — extractors return only what's available.
    """

    t: str  # title
    d: str  # description
    body: str  # searchable text (raw, not HTML)
    c: str  # category
    tags: list[str]  # tags
    toc: list[dict[str, Any]]  # table of contents


class FieldExtractor(Protocol):
    """Protocol for extracting search fields from a capture.

    Frameworks implement this to map their data models to search entries.
    The default extractor reads from the ``doc`` context key convention.
    """

    def __call__(self, url: str, capture: RenderCapture) -> SearchEntry: ...


def default_field_extractor(url: str, capture: RenderCapture) -> SearchEntry:
    """Extract search fields from capture context using the ``doc`` convention.

    Reads ``capture.context_keys["doc"]`` for structured fields:
    - ``doc.title`` → title
    - ``doc.body`` or ``doc.content`` → body (raw text, not HTML)
    - ``doc.metadata.description`` → description
    - ``doc.metadata.category`` → category
    - ``doc.metadata.tags`` → tags
    - ``doc.toc`` → table of contents

    Returns only fields that are present on the doc object.
    """
    entry: SearchEntry = {}
    ctx = capture.context_keys
    doc = ctx.get("doc")
    if doc is None:
        return entry

    if hasattr(doc, "title"):
        entry["t"] = doc.title

    # Raw body text — the core insight: use source, not rendered HTML
    if hasattr(doc, "body"):
        entry["body"] = doc.body
    elif hasattr(doc, "content"):
        entry["body"] = doc.content

    if hasattr(doc, "metadata"):
        meta = doc.metadata
        if hasattr(meta, "description"):
            entry["d"] = meta.description
        if hasattr(meta, "category") and meta.category:
            entry["c"] = meta.category
        if hasattr(meta, "tags") and meta.tags:
            entry["tags"] = sorted(meta.tags)

    if hasattr(doc, "toc") and doc.toc:
        entry["toc"] = [
            {"level": e.level, "id": e.id, "text": e.text}
            for e in doc.toc
            if hasattr(e, "level") and hasattr(e, "id") and hasattr(e, "text")
        ]

    return entry


@dataclass(slots=True)
class FreezeCacheStats:
    """Statistics for freeze cache performance during a batch render."""

    cache_hits: int = 0
    cache_misses: int = 0
    invalidations: int = 0
    blocks_cached: int = 0


# Cache scopes that are eligible for freeze caching
_CACHEABLE_SCOPES: frozenset[str] = frozenset({"site"})


@dataclass(slots=True)
class FreezeCache:
    """Accumulates site-scoped block cache during a freeze (batch render).

    Tracks block HTML by ``(template_name, block_name)`` key. When a block
    with ``cache_scope="site"`` is captured, its HTML is stored. On subsequent
    renders of the same template, the cached HTML can be injected via
    ``_cached_blocks`` to skip redundant block execution.

    A ``content_hash`` guard detects when a "site"-scoped block unexpectedly
    produces different output — indicating the ``cache_scope`` classification
    was wrong — and skips caching that block rather than serving stale content.

    Example:
        manifest = RenderManifest(freeze_cache=FreezeCache())

        for url, template_name, ctx in pages:
            template = env.get_template(template_name)
            cached = manifest.freeze_cache.get_cached_blocks(template_name)
            with captured_render(capture_context=frozenset(ctx.keys())) as cap:
                html = template.render(_cached_blocks=cached, **ctx)
            manifest.add(url, cap)  # auto-records to freeze_cache

        print(manifest.freeze_cache.stats)
    """

    _cache: dict[tuple[str, str], str] = field(default_factory=dict)
    _hashes: dict[tuple[str, str], str] = field(default_factory=dict)
    _invalidated: set[tuple[str, str]] = field(default_factory=set)
    stats: FreezeCacheStats = field(default_factory=FreezeCacheStats)

    def record(self, template_name: str, capture: RenderCapture) -> None:
        """Record site-scoped blocks from a completed render.

        Only caches blocks with ``cache_scope="site"``. If a previously cached
        block produces a different ``content_hash``, the entry is invalidated
        (removed from cache) to prevent serving stale content.

        Args:
            template_name: Name of the template that was rendered
            capture: The RenderCapture from the completed render
        """
        for name, frag in capture.blocks.items():
            if not self._is_cacheable(frag):
                continue

            key = (template_name, name)

            # Already invalidated — don't re-cache
            if key in self._invalidated:
                continue

            existing_hash = self._hashes.get(key)
            if existing_hash is not None and existing_hash != frag.content_hash:
                # Site-scoped block changed — cache_scope was wrong
                self._invalidated.add(key)
                self._cache.pop(key, None)
                self._hashes.pop(key, None)
                self.stats.invalidations += 1
                continue

            if key not in self._cache:
                self.stats.blocks_cached += 1
            self._cache[key] = frag.html
            self._hashes[key] = frag.content_hash

    def get_cached_blocks(self, template_name: str) -> dict[str, str] | None:
        """Get cached block HTML for a template.

        Returns a dict suitable for passing as ``_cached_blocks`` to
        ``template.render()``, or ``None`` if no blocks are cached.

        Args:
            template_name: Name of the template to look up

        Returns:
            Dict of block_name -> cached HTML, or None if nothing cached
        """
        blocks: dict[str, str] = {}
        for (tpl, block_name), html in self._cache.items():
            if tpl == template_name:
                blocks[block_name] = html
        if blocks:
            self.stats.cache_hits += len(blocks)
            return blocks
        self.stats.cache_misses += 1
        return None

    @staticmethod
    def _is_cacheable(frag: Fragment) -> bool:
        """Check if a fragment is eligible for freeze caching.

        Requires both ``cache_scope="site"`` AND empty ``depends_on``.
        A block that reads context variables (even if classified as site-scoped
        by static analysis) might produce different output per page.
        """
        return frag.cache_scope in _CACHEABLE_SCOPES and len(frag.depends_on) == 0


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
    freeze_cache: FreezeCache | None = field(default=None, repr=False)

    def add(self, url: str, capture: RenderCapture) -> None:
        """Add a rendered page's capture to the manifest.

        If a :class:`FreezeCache` is attached, automatically records
        site-scoped blocks for cache reuse on subsequent renders.

        Args:
            url: The URL or path of the rendered page
            capture: The RenderCapture from rendering this page
        """
        self.captures.append((url, capture))
        if self.freeze_cache is not None:
            self.freeze_cache.record(capture.template_name, capture)

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
    """Builds a search manifest from a RenderManifest.

    Uses a :class:`FieldExtractor` to pull structured fields (title, body,
    tags, etc.) from captured context. The default extractor reads from the
    ``doc`` context key convention, returning **raw text** — not rendered HTML.

    When the extractor does not provide a ``body`` field, falls back to
    assembling body text from rendered block HTML weighted by role.

    Attributes:
        role_weights: Mapping of role -> weight (0.0 = excluded from search).
            Used only for the HTML fallback path.
        field_extractor: Callable that extracts search fields from a capture.
            Defaults to :func:`default_field_extractor`.
    """

    role_weights: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_ROLE_WEIGHTS))
    field_extractor: Callable[[str, RenderCapture], SearchEntry] | None = field(
        default=None, repr=False
    )

    def build(self, manifest: RenderManifest) -> dict[str, Any]:
        """Build a search manifest from captured renders.

        Args:
            manifest: RenderManifest containing captured page data

        Returns:
            Search manifest dict with version, facets, and entries.
            Compatible with Chirp's search manifest format.
        """
        extractor = self.field_extractor or default_field_extractor
        entries: list[dict[str, Any]] = []
        all_tags: set[str] = set()
        all_categories: set[str] = set()

        for url, cap in manifest.captures:
            entry: dict[str, Any] = {"u": url}

            # Use extractor for structured fields from raw context
            extracted = extractor(url, cap)
            entry.update(dict(extracted))

            # Fallback: if extractor didn't provide body, use HTML blocks
            if "body" not in entry:
                body_parts: list[str] = []
                for frag in cap.blocks.values():
                    weight = self.role_weights.get(frag.role, 0.5)
                    if weight > 0:
                        body_parts.append(frag.html)
                if body_parts:
                    entry["body"] = "\n".join(body_parts)

            # Collect facets
            if "c" in entry:
                all_categories.add(entry["c"])
            if "tags" in entry:
                all_tags.update(entry["tags"])

            # Template name metadata
            if cap.template_name:
                entry.setdefault("template", cap.template_name)

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
