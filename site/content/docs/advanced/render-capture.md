---
title: Render Capture and Manifests
description: Capture rendered block facts for build diffs, search indexes, and freeze-cache analysis
draft: false
weight: 75
lang: en
type: doc
tags:
- advanced
- capture
- manifests
- build tooling
keywords:
- RenderCapture
- RenderManifest
- captured_render
- FreezeCache
- SearchManifestBuilder
icon: database
---

# Render Capture and Manifests

Render capture is Kida's opt-in observability path for build tools. One render
can produce normal HTML while also recording selected block output, semantic
metadata, content hashes, and explicitly selected context values. A build
coordinator can accumulate those facts into a `RenderManifest`, compare two
builds, derive a search manifest, and inspect site-scoped `FreezeCache`
candidates.

This is separate from the `{% cache %}` runtime fragment cache. `Fragment` in
this API means a captured block record; it does not change template rendering.

The complete runnable source is in
[`examples/render_capture_manifest`](https://github.com/lbliii/kida/tree/main/examples/render_capture_manifest).

## Preferred workflow

Compile capture hooks into the environment, create one capture context per
render, and add the completed capture to a caller-owned manifest:

```python
from kida import (
    DictLoader,
    Environment,
    FreezeCache,
    FreezeCacheStats,
    RenderManifest,
    SearchManifestBuilder,
    captured_render,
    get_capture,
)

env = Environment(
    loader=DictLoader(
        {
            "page.html": (
                "{% block content %}<main>{{ doc.body }}</main>{% end %}"
                "{% block nav %}<nav>Docs</nav>{% end %}"
            )
        }
    ),
    enable_capture=True,
)

freeze_cache = FreezeCache()
manifest = RenderManifest(freeze_cache=freeze_cache)
template = env.get_template("page.html")

with captured_render(capture_context=frozenset({"doc"})) as capture:
    assert get_capture() is capture
    html = template.render(doc=doc)

assert get_capture() is None
manifest.add("/guide", capture)

content = capture.blocks["content"]
print(content.html, content.content_hash, content.depends_on)

search_manifest = SearchManifestBuilder().build(manifest)
print(search_manifest["entries"])
```

`enable_capture=True` is a compilation setting. Templates compiled with the
default `False` have no capture hooks, so wrapping their render in
`captured_render()` yields an empty `blocks` mapping. Configure the environment
before loading templates.

The default `preserve_ast=True` lets captured `Fragment` records include block
roles, dependencies, and cache scope from static analysis. With
`preserve_ast=False`, rendered HTML and hashes are still captured, but those
analysis-derived fields fall back to `"unknown"` or an empty dependency set;
`FreezeCache` therefore has no proven site-scoped candidates to record.

## Ownership and lifecycle

The capture context owns one mutable `RenderCapture`:

1. `captured_render()` creates and activates it.
2. `Template.render()` sets `template_name`, snapshots selected context keys,
   and records captured blocks as `Fragment` values.
3. Leaving the context deactivates capture but does not invalidate the returned
   object.
4. The caller adds the completed capture to a `RenderManifest` or inspects it
   directly.

`get_capture()` exists for framework helpers that run inside the active render.
It returns `None` outside a capture context. Application code that already has
the context manager's `capture` value should use that value directly.

`capture_blocks=None` captures all rendered blocks. Pass a `frozenset` to keep
only selected names. Context capture is deliberately stricter:
`capture_context=None` captures no context, and callers opt in to individual
top-level keys. Values are shallow references, not serialized or deep-copied
snapshots, so capture only data the build tool needs and serialize it before the
application mutates it if historical values matter.

## Captured records

`RenderCapture` contains:

| Field | Meaning |
|---|---|
| `template_name` | Resolved template name for the render |
| `blocks` | Block name to `Fragment` |
| `context_keys` | Explicitly selected top-level context values |

Each `Fragment` records `name`, `role`, rendered `html`, a deterministic
`content_hash`, `depends_on`, and inferred `cache_scope`. Use the hash to compare
content; do not treat it as a security or authenticity digest.

## Compare build manifests

`RenderManifest` owns captures from a batch in insertion order. Add each capture
only after its context exits:

```python
old_manifest = RenderManifest()
new_manifest = RenderManifest()

# ...render old and new pages, then call manifest.add(url, capture)...

diff = new_manifest.diff(old_manifest)
```

`diff` is a frozen `ManifestDiff`:

- `added` and `removed` contain URLs;
- `changed[url][block]` is `(old_hash, new_hash)`;
- `unchanged` counts URLs whose captured block hashes agree.

The direction matters: call `new.diff(old)`. `all_fragments()` iterates every
`(url, Fragment)` pair, while `unique_content_hashes()` reveals repeated captured
content that a build tool may be able to deduplicate.

## Optional freeze-cache analysis

Attach a `FreezeCache` when constructing the manifest. `RenderManifest.add()`
then records captured blocks only when analysis classifies them as site-scoped
and they have no context dependencies:

```python
freeze_cache = FreezeCache()
manifest = RenderManifest(freeze_cache=freeze_cache)

# ...capture and add pages...

cached = freeze_cache.get_cached_blocks("page.html")
stats: FreezeCacheStats = freeze_cache.stats
print(cached, stats.blocks_cached, stats.cache_hits)
```

`get_cached_blocks()` returns a new `dict[str, str]` or `None`. It is an
integration output for a build coordinator; obtaining it also updates hit/miss
statistics. A changed hash for a supposedly site-scoped block invalidates that
entry rather than serving stale HTML. The preferred capture workflow does not
change render semantics or promote underscored render plumbing to public API.

`FreezeCacheStats` exposes `cache_hits`, `cache_misses`, `invalidations`, and
`blocks_cached`. Hits count returned blocks, not page requests.

## Optional search manifest

`SearchManifestBuilder` turns a `RenderManifest` into a versioned mapping with
`entries` and optional category/tag facets. Its default field adapter,
`default_field_extractor`, reads the captured `doc` object convention:

```python
from kida import (
    RenderCapture,
    SearchEntry,
    SearchManifestBuilder,
    default_field_extractor,
)


def extract(url: str, capture: RenderCapture) -> SearchEntry:
    entry = default_field_extractor(url, capture)
    entry.setdefault("c", "Documentation")
    return entry


search = SearchManifestBuilder(field_extractor=extract).build(manifest)
```

`SearchEntry` is the typed shape for optional title (`t`), description (`d`),
raw body, category (`c`), tags, and table-of-contents fields. The default
extractor prefers `doc.body` or `doc.content`, so search indexes raw source text
instead of rendered HTML. When an extractor supplies no body, the builder falls
back to captured block HTML whose semantic role has a positive weight.

## Thread and task safety

The active capture is stored in a `ContextVar`. Separate threads and async tasks
therefore get separate active values when each establishes its own
`captured_render()` context, and nested contexts restore the outer capture on
exit.

`RenderCapture`, `RenderManifest`, `FreezeCache`, `FreezeCacheStats`, and
`SearchManifestBuilder.role_weights` are mutable caller-owned objects. They do
not provide internal synchronization. Create one capture per render; let workers
return completed captures; aggregate them into a manifest and cache in one
coordinator, or provide external synchronization. Do not concurrently mutate one
manifest or freeze cache from multiple workers.

## API summary

All names in this workflow are exported from `kida`:

| API | Role |
|---|---|
| `captured_render`, `get_capture` | Activate and inspect render-local capture |
| `RenderCapture`, `Fragment` | Per-render and per-block facts |
| `RenderManifest`, `ManifestDiff` | Batch accumulation and build comparison |
| `FreezeCache`, `FreezeCacheStats` | Site-scoped candidate reuse and statistics |
| `SearchManifestBuilder`, `SearchEntry` | Search-manifest construction and typed entry shape |
| `default_field_extractor` | Default captured-`doc` adapter |

No capture or manifest object is required for ordinary rendering.
