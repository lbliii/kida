"""Metadata dataclasses for template introspection.

Immutable, frozen dataclasses representing analysis results.
All fields are conservative estimates — may over-approximate but never under.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, final


@final
@dataclass(frozen=True, slots=True)
class BlockMetadata:
    """Metadata about a template block, inferred from static analysis.

    All fields are conservative estimates:
    - `depends_on` may include unused paths (over-approximation)
    - `is_pure` defaults to "unknown" when uncertain
    - `inferred_role` is heuristic, not semantic truth

    Thread-safe: Immutable after creation.

    Attributes:
        name: Block identifier (e.g., "nav", "content", "sidebar")

        emits_html: True if block produces any output.
            Used to detect empty blocks.

        emits_landmarks: HTML5 landmark elements emitted (nav, main, header, etc.).
            Detected from static HTML in Data nodes.

        inferred_role: Heuristic classification based on name and landmarks.
            One of: "navigation", "content", "sidebar", "header", "footer", "unknown"

        depends_on: Context paths this block may access (conservative superset).
            Example: frozenset({"page.title", "site.pages", "config.theme"})

        is_pure: Whether block output is deterministic for same inputs.
            - "pure": Deterministic, safe to cache
            - "impure": Uses random/shuffle/etc, must re-render
            - "unknown": Cannot determine, treat as potentially impure

        cache_scope: Recommended caching granularity.
            - "site": Cache once per site build (no page-specific deps)
            - "page": Cache per page (has page-specific deps)
            - "none": Cannot cache (impure)
            - "unknown": Cannot determine

    Example:
            >>> meta = template.block_metadata()
            >>> nav = meta.get("nav")
            >>> if nav and nav.is_cacheable():
            ...     cached = cache.get_or_render("nav", ...)

    """

    name: str

    # Output characteristics
    emits_html: bool = True
    emits_landmarks: frozenset[str] = frozenset()
    inferred_role: Literal[
        "navigation",
        "content",
        "sidebar",
        "header",
        "footer",
        "unknown",
    ] = "unknown"

    # Input characteristics
    depends_on: frozenset[str] = frozenset()
    is_pure: Literal["pure", "impure", "unknown"] = "unknown"

    # Derived optimization hints
    cache_scope: Literal["none", "page", "site", "unknown"] = "unknown"
    # Deterministic structural hash of this block's AST.
    # Stable across runs for identical template source.
    block_hash: str = ""

    # Region-specific (RFC: kida-regions)
    is_region: bool = False
    region_params: tuple[str, ...] = ()

    def is_cacheable(self) -> bool:
        """Check if this block can be safely cached.

        Returns True if:
        - Block is pure (deterministic)
        - Cache scope is not "none"

        Returns:
            True if block can be cached, False otherwise.
        """
        return self.is_pure == "pure" and self.cache_scope != "none"

    def depends_on_page(self) -> bool:
        """Check if block depends on page-specific context.

        Returns:
            True if any dependency starts with common page prefixes.
        """
        return any(path.startswith("page.") or path == "page" for path in self.depends_on)

    def depends_on_site(self) -> bool:
        """Check if block depends on site-wide context.

        Returns:
            True if any dependency starts with common site prefixes.
        """
        return any(path.startswith("site.") or path == "site" for path in self.depends_on)


@final
@dataclass(frozen=True, slots=True)
class TemplateMetadata:
    """Metadata about a complete template.

    Aggregates block metadata and tracks template-level information
    like inheritance and top-level dependencies.

    Attributes:
        name: Template identifier (e.g., "page.html")

        extends: Parent template name from {% extends %}, or None.
            Example: "base.html"

        blocks: Mapping of block name → BlockMetadata.
            All blocks defined in this template.

        top_level_depends_on: Context paths used outside blocks.
            Captures dependencies from:
            - Code before/after blocks
            - Dynamic extends expressions
            - Template-level set/let statements

    Example:
            >>> meta = template.template_metadata()
            >>> print(f"Extends: {meta.extends}")
            >>> print(f"Blocks: {list(meta.blocks.keys())}")
            >>> print(f"All deps: {meta.all_dependencies()}")

    """

    name: str | None
    extends: str | None
    blocks: dict[str, BlockMetadata]
    top_level_depends_on: frozenset[str] = frozenset()

    def all_dependencies(self) -> frozenset[str]:
        """Return all context paths used anywhere in template.

        Combines top-level dependencies with all block dependencies.

        Returns:
            Frozen set of all context paths.
        """
        deps = set(self.top_level_depends_on)
        for block in self.blocks.values():
            deps |= block.depends_on
        return frozenset(deps)

    def get_block(self, name: str) -> BlockMetadata | None:
        """Get metadata for a specific block.

        Args:
            name: Block name to look up.

        Returns:
            BlockMetadata if found, None otherwise.
        """
        return self.blocks.get(name)

    def cacheable_blocks(self) -> list[BlockMetadata]:
        """Return all blocks that can be safely cached.

        Returns:
            List of BlockMetadata where is_cacheable() is True.
        """
        return [block for block in self.blocks.values() if block.is_cacheable()]

    def site_cacheable_blocks(self) -> list[BlockMetadata]:
        """Return blocks that can be cached site-wide.

        Returns:
            List of BlockMetadata where cache_scope is "site".
        """
        return [block for block in self.blocks.values() if block.cache_scope == "site"]

    def regions(self) -> dict[str, BlockMetadata]:
        """Return only region-typed blocks (RFC: kida-regions)."""
        return {k: v for k, v in self.blocks.items() if v.is_region}


@final
@dataclass(frozen=True, slots=True)
class CallValidation:
    """Result of validating a single call site against a function definition.

    Produced by ``BlockAnalyzer.validate_calls()`` when a ``FuncCall`` targets
    a ``{% def %}`` in the same compilation unit.

    Attributes:
        def_name: Name of the called ``{% def %}``.
        lineno: Source line of the call site.
        col_offset: Source column of the call site.
        unknown_params: Keyword argument names not in the definition's parameters.
        missing_required: Required parameters (no default) not provided by the call.
        duplicate_params: Keyword argument names supplied more than once.

    """

    def_name: str
    lineno: int
    col_offset: int
    unknown_params: tuple[str, ...] = ()
    missing_required: tuple[str, ...] = ()
    duplicate_params: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return True if no issues were found."""
        return not (self.unknown_params or self.missing_required or self.duplicate_params)


@final
@dataclass(frozen=True, slots=True)
class TypeMismatch:
    """Result of a type mismatch at a call site.

    Produced by ``BlockAnalyzer.validate_call_types()`` when a literal
    argument's type doesn't match the ``{% def %}`` parameter's annotation.

    Only literal arguments (strings, ints, floats, bools, None) are checked.
    Variable arguments are skipped since their type can't be known statically.

    Attributes:
        def_name: Name of the called ``{% def %}``.
        param_name: Parameter with the type mismatch.
        expected: Annotation string from the def signature (e.g. ``"int"``).
        actual_type: Python type name of the literal (e.g. ``"str"``).
        actual_value: The literal value that was passed.
        lineno: Source line of the call site.
        col_offset: Source column of the call site.
    """

    def_name: str
    param_name: str
    expected: str
    actual_type: str
    actual_value: str | int | float | bool | None
    lineno: int
    col_offset: int


@final
@dataclass(frozen=True, slots=True)
class DefParamInfo:
    """Metadata about a single parameter in a ``{% def %}`` component.

    Attributes:
        name: Parameter name.
        annotation: Type annotation string from template source (e.g. ``"str"``),
            or None if untyped.
        has_default: True if the parameter has a default value.
        is_required: True if the parameter must be provided by callers.
    """

    name: str
    annotation: str | None = None
    has_default: bool = False
    is_required: bool = True


@final
@dataclass(frozen=True, slots=True)
class DefMetadata:
    """Metadata about a ``{% def %}`` component, inferred from static analysis.

    Parallel to :class:`BlockMetadata` for blocks — makes defs first-class
    citizens in Kida's introspection API.

    Thread-safe: Immutable after creation.

    Attributes:
        name: Def identifier (e.g. ``"card"``, ``"button"``).
        template_name: Template where this def is defined.
        lineno: Source line number of the ``{% def %}`` tag.
        params: Parameter metadata in declaration order.
        slots: Named slots referenced in the def body (excludes ``"default"``).
        has_default_slot: True if the body contains an unnamed ``{% slot %}``.
        depends_on: Context paths the def body may access (conservative superset).

    Example:
            >>> meta = template.def_metadata()
            >>> card = meta.get("card")
            >>> if card:
            ...     print(f"card({', '.join(p.name for p in card.params)})")
            ...     print(f"  slots: {card.slots}")
    """

    name: str
    template_name: str | None = None
    lineno: int = 0
    params: tuple[DefParamInfo, ...] = ()
    slots: tuple[str, ...] = ()
    has_default_slot: bool = False
    depends_on: frozenset[str] = frozenset()


@final
@dataclass(frozen=True, slots=True)
class TemplateStructureManifest:
    """Lightweight template structure for schedulers and dependency planners.

    Attributes:
        name: Template name.
        extends: Parent template name from `{% extends %}`.
        block_names: Ordered block names in this template.
        block_hashes: Deterministic per-block structural hashes.
        dependencies: Top-level + block context dependencies.
    """

    name: str | None
    extends: str | None
    block_names: tuple[str, ...]
    block_hashes: dict[str, str]
    dependencies: frozenset[str]
