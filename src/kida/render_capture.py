"""Kida RenderCapture — opt-in content capture during template rendering.

This module provides render-time data capture for block content,
context snapshots, and content hashing. Enables search indexing,
block-level caching, and semantic diffing as byproducts of rendering.

Zero overhead when disabled (get_capture() returns None).

RFC: render-capture

Example:
    from kida import Environment, FileSystemLoader
    from kida.render_capture import captured_render

    env = Environment(loader=FileSystemLoader("templates/"), enable_capture=True)
    template = env.get_template("page.html")

    # Normal render (no overhead)
    html = template.render(page=page)

    # Captured render (opt-in)
    with captured_render(
        capture_blocks=frozenset({"content", "sidebar"}),
        capture_context=frozenset({"page"}),
    ) as capture:
        html = template.render(page=page)

    print(capture.template_name)
    # "page.html"
    print(capture.blocks["content"].html)
    # "<article>...</article>"
    print(capture.blocks["content"].content_hash)
    # "a1b2c3d4e5f67890"
    print(capture.context_keys)
    # {"page": <Page object>}

"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from hashlib import sha256
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True, slots=True)
class Fragment:
    """A single block's rendered output with semantic metadata.

    Attributes:
        name: Block name (e.g., "content", "sidebar")
        role: Semantic role from BlockMetadata.inferred_role
            (e.g., "content", "navigation", "unknown")
        html: Raw rendered HTML of this block
        content_hash: SHA256[:16] hex digest of the rendered HTML
        depends_on: Context paths this block reads (from BlockMetadata)
    """

    name: str
    role: str
    html: str
    content_hash: str
    depends_on: frozenset[str]


def _compute_content_hash(html: str) -> str:
    """Compute content hash for a rendered block.

    Uses SHA256 truncated to 16 hex chars, matching the block_hash
    precedent in kida.analysis.analyzer.
    """
    return sha256(html.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class RenderCapture:
    """Collects fragments and context during a single render() call.

    Populated by compiler-injected hooks when an active capture exists.
    Use :func:`captured_render` to create and activate a capture.

    Attributes:
        template_name: Name of the rendered template
        blocks: Block name -> Fragment mapping for captured blocks
        context_keys: Snapshotted context values (top-level keys only)
    """

    template_name: str = ""
    blocks: dict[str, Fragment] = field(default_factory=dict)
    context_keys: dict[str, Any] = field(default_factory=dict)

    # Internal: which blocks/context keys to capture (None = all)
    _capture_blocks: frozenset[str] | None = field(default=None, repr=False)
    _capture_context: frozenset[str] | None = field(default=None, repr=False)

    # Internal: block metadata from template analysis (set by _render_scaffold)
    _block_metadata: dict[str, Any] | None = field(default=None, repr=False)

    def _record(self, name: str, html: str) -> None:
        """Record a block's rendered output.

        Called by compiler-injected hooks at block call sites.
        Skips recording if the block is not in the capture set.
        Pulls role and depends_on from _block_metadata when available.

        Args:
            name: Block name
            html: Rendered HTML output of the block
        """
        if self._capture_blocks is not None and name not in self._capture_blocks:
            return

        role = "unknown"
        depends_on: frozenset[str] = frozenset()
        if self._block_metadata is not None:
            meta = self._block_metadata.get(name)
            if meta is not None:
                role = meta.inferred_role
                depends_on = meta.depends_on

        self.blocks[name] = Fragment(
            name=name,
            role=role,
            html=html,
            content_hash=_compute_content_hash(html),
            depends_on=depends_on,
        )

    def changed_from(self, other: RenderCapture) -> dict[str, tuple[Fragment, Fragment]]:
        """Blocks whose content_hash differs between two captures.

        Returns a dict mapping block name to (old_fragment, new_fragment)
        for blocks present in both captures with different content.

        Args:
            other: The earlier capture to compare against.

        Returns:
            Dict of block name -> (other's fragment, self's fragment) for changed blocks.
        """
        changed: dict[str, tuple[Fragment, Fragment]] = {}
        for name, frag in self.blocks.items():
            other_frag = other.blocks.get(name)
            if other_frag is not None and other_frag.content_hash != frag.content_hash:
                changed[name] = (other_frag, frag)
        return changed


# Module-level ContextVar
_capture: ContextVar[RenderCapture | None] = ContextVar(
    "render_capture",
    default=None,
)


def get_capture() -> RenderCapture | None:
    """Get current capture (None if capture not active).

    Returns:
        Current RenderCapture or None if not in captured render
    """
    return _capture.get()


@contextmanager
def captured_render(
    capture_blocks: frozenset[str] | None = None,
    capture_context: frozenset[str] | None = None,
) -> Iterator[RenderCapture]:
    """Context manager for captured rendering.

    Creates a RenderCapture and makes it available via get_capture()
    for the duration of the with block. Compiler-injected hooks record
    block content and context snapshots into the capture.

    Note:
        Templates must be compiled with ``Environment(enable_capture=True)``
        for capture hooks to be present. Templates compiled with the default
        ``enable_capture=False`` strip all capture AST at compile time
        and will not populate the capture.

    Args:
        capture_blocks: Set of block names to capture. None captures all blocks.
        capture_context: Set of top-level context keys to snapshot.
            None captures no context (explicit opt-in for context).

    Yields:
        RenderCapture that will be populated during render

    Example:
        env = Environment(loader=..., enable_capture=True)
        template = env.get_template("page.html")
        with captured_render(
            capture_blocks=frozenset({"content"}),
            capture_context=frozenset({"doc"}),
        ) as capture:
            html = template.render(doc=doc)
        print(capture.blocks["content"].html)
        print(capture.context_keys["doc"])
    """
    cap = RenderCapture(
        _capture_blocks=capture_blocks,
        _capture_context=capture_context,
    )
    token: Token[RenderCapture | None] = _capture.set(cap)
    try:
        yield cap
    finally:
        _capture.reset(token)
