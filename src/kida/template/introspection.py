"""Template introspection mixin (RFC: kida-template-introspection).

Adds static analysis and metadata methods to the Template class
via mixin inheritance.

"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import ast

    from kida.analysis import TemplateMetadata
    from kida.environment import Environment


class TemplateIntrospectionMixin:
    """Mixin adding static analysis and introspection to Template.

    Requires the host class to define the following slots:
        _optimized_ast: ast.Module | None
        _metadata_cache: TemplateMetadata | None
        _name: str | None
        _env_ref: weakref.ref[Environment]

    """

    if TYPE_CHECKING:
        _optimized_ast: ast.Module | None
        _metadata_cache: TemplateMetadata | None
        _name: str | None
        _env_ref: weakref.ref[Environment]

    def block_metadata(self) -> dict[str, Any]:
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

    def _analyze(self) -> None:
        """Perform static analysis and cache results."""
        # Avoid circular import at module level
        from kida.analysis import BlockAnalyzer, TemplateMetadata
        from kida.template.core import Template

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
            from kida.environment.exceptions import (
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
            except (TemplateNotFoundError, TemplateSyntaxError, RuntimeError):
                return None

        analyzer = BlockAnalyzer(template_resolver=resolve_template)
        result = analyzer.analyze(self._optimized_ast)

        # Set template name from self
        self._metadata_cache = TemplateMetadata(
            name=self._name,
            extends=result.extends,
            blocks=result.blocks,
            top_level_depends_on=result.top_level_depends_on,
        )

        # Store in environment's shared cache for reuse by other templates
        if (
            env_for_cache is not None
            and hasattr(env_for_cache, "_analysis_cache")
            and self._name is not None
        ):
            env_for_cache._analysis_cache[self._name] = self._metadata_cache
