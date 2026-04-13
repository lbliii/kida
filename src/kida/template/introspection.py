"""Template introspection mixin (RFC: kida-template-introspection).

Adds static analysis and metadata methods to the Template class
via mixin inheritance.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import weakref

    from kida.analysis import BlockMetadata, DefMetadata, TemplateMetadata
    from kida.environment import Environment
    from kida.nodes import Template as TemplateNode
    from kida.template.core import Template


class TemplateIntrospectionMixin:
    """Mixin adding static analysis and introspection to Template.

    Requires the host class to define the following slots:
        _optimized_ast: TemplateNode | None
        _metadata_cache: TemplateMetadata | None
        _def_metadata_cache: dict[str, DefMetadata] | None
        _name: str | None
        _env_ref: weakref.ref[Environment]

    """

    if TYPE_CHECKING:
        _optimized_ast: TemplateNode | None
        _metadata_cache: TemplateMetadata | None
        _def_metadata_cache: dict[str, DefMetadata] | None
        _name: str | None
        _env_ref: weakref.ref[Environment]

    def block_metadata(self) -> dict[str, BlockMetadata]:
        """Get metadata about template blocks.

        Returns a mapping of block name -> BlockMetadata with:
        - depends_on: Context paths the block may access
        - is_pure: Whether output is deterministic
        - cache_scope: Recommended caching granularity
        - inferred_role: Heuristic classification

        Results are cached after first call.

        Returns empty dict if:
        - AST was not preserved (preserve_ast=False)
        - Template was loaded from bytecode cache without source

        Example:
            >>> meta = template.block_metadata()
            >>> nav = meta.get("nav")
            >>> if nav and nav.cache_scope == "site":
            ...     html = cache.get_or_render("nav", ...)

        Note:
            This is best-effort static analysis. Dependency sets
            are conservative (may over-approximate). Treat as hints.
        """
        if self._optimized_ast is None:
            return {}

        if self._metadata_cache is None:
            self._analyze()

        return self._metadata_cache.blocks if self._metadata_cache else {}

    def def_metadata(self) -> dict[str, DefMetadata]:
        """Get metadata about ``{% def %}`` components in this template.

        Returns a mapping of def name → DefMetadata with:
        - params: Parameter names, annotations, and defaults
        - slots: Named slots used in the def body
        - has_default_slot: Whether an unnamed ``{% slot %}`` exists
        - depends_on: Context paths the def body may access

        Results are cached after first call.

        Returns empty dict if AST was not preserved (preserve_ast=False).

        Example:
            >>> meta = template.def_metadata()
            >>> card = meta.get("card")
            >>> if card:
            ...     sig = ", ".join(p.name for p in card.params)
            ...     print(f"def card({sig})")
            ...     print(f"  slots: {card.slots}")
        """
        if self._optimized_ast is None:
            return {}

        if self._def_metadata_cache is None:
            self._analyze_defs()

        return self._def_metadata_cache or {}

    def list_defs(self) -> list[str]:
        """List all ``{% def %}`` names defined in this template.

        Returns:
            List of def names defined in this template.

        Example:
            >>> template.list_defs()
            ['card', 'button', 'badge']
        """
        return list(self.def_metadata().keys())

    def template_metadata(self) -> TemplateMetadata | None:
        """Get full template metadata including inheritance info.

        Returns TemplateMetadata with:
        - name: Template identifier
        - extends: Parent template name (if any)
        - blocks: Mapping of block name -> BlockMetadata
        - top_level_depends_on: Context paths used outside blocks

        Returns None if AST was not preserved (preserve_ast=False or
        loaded from bytecode cache without source).

        Example:
            >>> meta = template.template_metadata()
            >>> if meta:
            ...     print(f"Extends: {meta.extends}")
            ...     print(f"All deps: {meta.all_dependencies()}")
        """
        if self._optimized_ast is None:
            return None

        if self._metadata_cache is None:
            self._analyze()

        return self._metadata_cache

    def depends_on(self) -> frozenset[str]:
        """Get all context paths this template may access.

        Convenience method combining all block dependencies and
        top-level dependencies.

        Returns empty frozenset if AST was not preserved.

        Example:
            >>> deps = template.depends_on()
            >>> print(f"Template requires: {deps}")
            Template requires: frozenset({'page.title', 'site.pages'})
        """
        meta = self.template_metadata()
        if meta is None:
            return frozenset()
        result: frozenset[str] = meta.all_dependencies()
        return result

    def dependencies(self) -> dict[str, list[str]]:
        """Get template dependency graph: extends, includes, embeds, imports.

        Returns a dict with keys "extends", "includes", "embeds", "imports",
        each mapping to a list of template names (string literals only).
        Dynamic template names (e.g. {{ var }}) are not included.

        Returns empty dict if AST was not preserved.

        Example:
            >>> deps = template.dependencies()
            >>> deps["extends"]
            ['base.html']
            >>> deps["includes"]
            ['nav.html', 'footer.html']
        """
        if self._optimized_ast is None:
            return {}

        from kida.nodes import Const, Embed, Extends, FromImport, Import, Include

        def _str_from_expr(expr: Any) -> str | None:
            if isinstance(expr, Const) and isinstance(expr.value, str):
                return expr.value
            return None

        def _walk(node: Any, out: dict[str, list[str]]) -> None:
            if isinstance(node, Extends):
                name = _str_from_expr(node.template)
                if name:
                    out.setdefault("extends", []).append(name)
            elif isinstance(node, Include):
                name = _str_from_expr(node.template)
                if name:
                    out.setdefault("includes", []).append(name)
            elif isinstance(node, Embed):
                name = _str_from_expr(node.template)
                if name:
                    out.setdefault("embeds", []).append(name)
                for block in getattr(node, "blocks", {}).values():
                    _walk(block, out)
            elif isinstance(node, (FromImport, Import)):
                name = _str_from_expr(node.template)
                if name:
                    out.setdefault("imports", []).append(name)

            for child in getattr(node, "body", []) or []:
                _walk(child, out)
            if hasattr(node, "extends") and node.extends is not None:
                _walk(node.extends, out)

        result: dict[str, list[str]] = {}
        _walk(self._optimized_ast, result)
        return result

    def required_context(self) -> frozenset[str]:
        """Get the set of context variable names this template requires.

        Returns top-level variable names (without dotted paths) that the
        template depends on. This is useful for checking whether a context
        dictionary provides all required variables before rendering.

        Returns empty frozenset if AST was not preserved.

        Example:
            >>> template.required_context()
            frozenset({'page', 'site', 'config'})
        """
        paths = self.depends_on()
        return frozenset(path.split(".")[0] for path in paths)

    def is_cacheable(self, block_name: str | None = None) -> bool:
        """Check if a block (or the whole template) can be safely cached.

        Args:
            block_name: Specific block to check. If None, returns True only
                if *all* blocks are cacheable.

        Returns:
            True if the target is pure and has a cacheable scope.

        Example:
            >>> template.is_cacheable("nav")
            True
            >>> template.is_cacheable()  # all blocks
            False
        """
        meta = self.template_metadata()
        if meta is None:
            return False

        if block_name is not None:
            block = meta.get_block(block_name)
            return block.is_cacheable() if block else False

        # All blocks must be cacheable
        if not meta.blocks:
            return False
        return all(block.is_cacheable() for block in meta.blocks.values())

    def validate_context(self, context: dict[str, Any]) -> list[str]:
        """Check a context dict for missing variables the template requires.

        Compares provided context keys against the template's dependency
        analysis to identify variables that the template references but
        are not present in the context. This catches missing variables
        *before* rendering, avoiding runtime UndefinedError.

        Note: This checks top-level variable names only. A template
        that accesses ``page.title`` requires ``page`` to be in context,
        but does not verify that ``page`` has a ``title`` attribute.

        Args:
            context: The context dictionary that would be passed to render().

        Returns:
            List of missing top-level variable names, sorted alphabetically.
            Empty list if all required variables are present or if AST
            was not preserved (no analysis available).

        Example:
            >>> tmpl = env.from_string("{{ title }} by {{ author.name }}")
            >>> tmpl.validate_context({"title": "Hello"})
            ['author']
            >>> tmpl.validate_context({"title": "Hello", "author": obj})
            []
        """
        required = self.required_context()
        if not required:
            return []

        # Merge with environment globals (they're always available)
        available = set(context.keys())
        env = self._env_ref()
        if env is not None:
            available |= env.globals.keys()

        missing = required - available
        return sorted(missing)

    def _analyze(self) -> None:
        """Perform static analysis and cache results."""
        # Avoid circular import at module level
        from kida.analysis import BlockAnalyzer, TemplateMetadata

        # Check environment's shared analysis cache first (for included templates)
        env_for_cache = self._env_ref()
        if (
            env_for_cache is not None
            and hasattr(env_for_cache, "_analysis_cache")
            and self._name is not None
        ):
            cached = env_for_cache._analysis_cache.get(self._name)
            if cached is not None:
                self._metadata_cache = cached
                return

        # Create template resolver for included template analysis
        def resolve_template(name: str) -> Template | None:
            """Resolve and analyze included templates."""
            from kida.exceptions import (
                TemplateNotFoundError,
                TemplateSyntaxError,
            )

            if env_for_cache is None:
                return None
            try:
                included = env_for_cache.get_template(name)
                # Trigger analysis of included template (will cache it)
                if (
                    hasattr(included, "_optimized_ast")
                    and included._optimized_ast is not None
                    and included._metadata_cache is None
                ):
                    included._analyze()
                return included
            except TemplateNotFoundError, TemplateSyntaxError, RuntimeError:
                return None

        analyzer = BlockAnalyzer(template_resolver=resolve_template)
        if self._optimized_ast is None:
            return
        result = analyzer.analyze(self._optimized_ast)

        # Merge inherited blocks from parent when template extends another
        blocks = dict(result.blocks)
        if result.extends and env_for_cache is not None:
            parent = resolve_template(result.extends)
            if parent is not None:
                parent_meta = parent.template_metadata()
                if parent_meta is not None and parent_meta.blocks:
                    # Parent blocks first, child overlay (child overrides parent)
                    blocks = {**parent_meta.blocks, **blocks}

        # Set template name from self
        self._metadata_cache = TemplateMetadata(
            name=self._name,
            extends=result.extends,
            blocks=blocks,
            top_level_depends_on=result.top_level_depends_on,
        )

        # Store in environment's shared cache for reuse by other templates
        if (
            env_for_cache is not None
            and hasattr(env_for_cache, "_analysis_cache")
            and self._name is not None
        ):
            env_for_cache._analysis_cache[self._name] = self._metadata_cache

    def _analyze_defs(self) -> None:
        """Walk the AST to extract DefMetadata for all {% def %} nodes."""
        from kida.analysis.metadata import DefMetadata, DefParamInfo
        from kida.nodes.functions import Def, Slot

        if self._optimized_ast is None:
            return

        def _collect_slots(body: object) -> tuple[list[str], bool]:
            """Recursively find Slot nodes in a def body.

            Returns (named_slots, has_default_slot).
            """
            named: list[str] = []
            has_default = False
            if isinstance(body, (list, tuple)):
                nodes_to_visit = list(body)
            else:
                nodes_to_visit = list(getattr(body, "body", [body]))
            while nodes_to_visit:
                node = nodes_to_visit.pop()
                if isinstance(node, Slot):
                    if node.name == "default":
                        has_default = True
                    else:
                        named.append(node.name)
                # Recurse into child bodies (but not into nested defs)
                if not isinstance(node, Def):
                    for attr in ("body", "orelse", "finalbody"):
                        children = getattr(node, attr, None)
                        if isinstance(children, (list, tuple)):
                            nodes_to_visit.extend(children)
            return named, has_default

        def _walk_for_defs(nodes: object) -> dict[str, DefMetadata]:
            """Walk AST collecting top-level Def nodes."""
            result: dict[str, DefMetadata] = {}
            to_visit = list(getattr(nodes, "body", []) if not isinstance(nodes, list) else nodes)
            while to_visit:
                node = to_visit.pop()
                if isinstance(node, Def):
                    # Build param info
                    n_defaults = len(node.defaults)
                    n_params = len(node.params)
                    params: list[DefParamInfo] = []
                    for i, p in enumerate(node.params):
                        has_default = i >= (n_params - n_defaults)
                        params.append(
                            DefParamInfo(
                                name=p.name,
                                annotation=p.annotation,
                                has_default=has_default,
                                is_required=not has_default,
                            )
                        )

                    # Collect slots from body
                    named_slots, has_default_slot = _collect_slots(node.body)

                    result[node.name] = DefMetadata(
                        name=node.name,
                        template_name=self._name,
                        lineno=getattr(node, "lineno", 0),
                        params=tuple(params),
                        slots=tuple(dict.fromkeys(named_slots)),  # deduplicate, preserve order
                        has_default_slot=has_default_slot,
                    )
                    # Don't recurse into def bodies for nested defs
                    continue
                # Recurse into non-def children
                for attr in ("body", "orelse"):
                    children = getattr(node, attr, None)
                    if isinstance(children, (list, tuple)):
                        to_visit.extend(children)
            return result

        self._def_metadata_cache = _walk_for_defs(self._optimized_ast)
