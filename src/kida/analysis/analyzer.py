"""Block analyzer - unified entry point for template analysis.

Combines dependency analysis, purity checking, landmark detection,
and role classification into a unified analysis pass.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from kida.analysis.cache import infer_cache_scope
from kida.analysis.config import DEFAULT_CONFIG, AnalysisConfig
from kida.analysis.dependencies import DependencyWalker
from kida.analysis.landmarks import LandmarkDetector
from kida.analysis.metadata import BlockMetadata, CallValidation, TemplateMetadata
from kida.analysis.purity import PurityAnalyzer
from kida.analysis.roles import classify_role
from kida.nodes import (
    Block,
    CallBlock,
    Const,
    Data,
    Def,
    Extends,
    FuncCall,
    Name,
    Node,
    Output,
    Template,
)

logger = logging.getLogger(__name__)


class BlockAnalyzer:
    """Analyze template blocks and extract metadata.

    Combines dependency analysis, purity checking, landmark detection,
    and role classification into a unified analysis pass.

    Thread-safe: Stateless analyzers, creates new result objects.

    Example:
            >>> analyzer = BlockAnalyzer()
            >>> meta = analyzer.analyze(template_ast)
            >>> print(meta.blocks["nav"].cache_scope)
            'site'

    Configuration:
            >>> from kida.analysis import AnalysisConfig
            >>> config = AnalysisConfig(
            ...     page_prefixes=frozenset({"post.", "item."}),
            ...     site_prefixes=frozenset({"global.", "settings."}),
            ... )
            >>> analyzer = BlockAnalyzer(config=config)

    """

    def __init__(
        self,
        config: AnalysisConfig | None = None,
        template_resolver: Callable[[str], Any] | None = None,
    ) -> None:
        """Initialize analyzer with optional configuration.

        Args:
            config: Analysis configuration. Uses DEFAULT_CONFIG if not provided.
            template_resolver: Optional callback(name: str) -> Template | None
                to resolve included templates for purity analysis. If None,
                includes return "unknown" purity.
        """
        self._config = config or DEFAULT_CONFIG
        self._dep_walker = DependencyWalker()
        self._purity_analyzer = PurityAnalyzer(
            extra_pure_functions=self._config.extra_pure_functions,
            extra_impure_filters=self._config.extra_impure_filters,
            template_resolver=template_resolver,
        )
        self._landmark_detector = LandmarkDetector()

    def analyze(self, ast: Template) -> TemplateMetadata:
        """Analyze a template AST and return metadata.

        Args:
            ast: Parsed template AST (nodes.Template)

        Returns:
            TemplateMetadata with block information
        """
        blocks: dict[str, BlockMetadata] = {}

        # Collect blocks from AST
        block_nodes = self._collect_blocks(ast)

        for block_node in block_nodes:
            block_meta = self._analyze_block(block_node)
            blocks[block_meta.name] = block_meta

        # Analyze top-level dependencies (outside blocks)
        top_level_deps = self._analyze_top_level(ast, set(blocks.keys()))

        # Extract extends info
        # Extends can be on the Template node directly, or in the body
        extends: str | None = None
        if ast.extends:
            extends_expr = ast.extends.template
            if isinstance(extends_expr, Const) and isinstance(extends_expr.value, str):
                extends = extends_expr.value
        else:
            # Check body for Extends node (parser puts it there)
            for node in ast.body:
                if isinstance(node, Extends):
                    extends_expr = node.template
                    if isinstance(extends_expr, Const) and isinstance(extends_expr.value, str):
                        extends = extends_expr.value
                    break

        return TemplateMetadata(
            name=None,  # Set by caller
            extends=extends,
            blocks=blocks,
            top_level_depends_on=top_level_deps,
        )

    def _analyze_block(self, block_node: Block) -> BlockMetadata:
        """Analyze a single block node."""
        # Dependency analysis
        depends_on = self._dep_walker.analyze(block_node)

        # Purity analysis
        is_pure = self._purity_analyzer.analyze(block_node)

        # Landmark detection
        landmarks = self._landmark_detector.detect(block_node)

        # Role classification
        inferred_role = classify_role(block_node.name, landmarks)

        # Cache scope inference
        cache_scope = infer_cache_scope(depends_on, is_pure, self._config)

        # Check if block emits any HTML
        emits_html = self._check_emits_html(block_node)

        return BlockMetadata(
            name=block_node.name,
            emits_html=emits_html,
            emits_landmarks=landmarks,
            inferred_role=inferred_role,
            depends_on=depends_on,
            is_pure=is_pure,
            cache_scope=cache_scope,
            block_hash=_compute_block_hash(block_node),
        )

    def _collect_blocks(self, ast: Template) -> list[Block]:
        """Recursively collect all Block nodes from AST."""
        blocks: list[Block] = []
        self._collect_blocks_recursive(ast.body, blocks)
        return blocks

    def _collect_blocks_recursive(
        self, nodes: Sequence[Node], blocks: list[Block]
    ) -> None:
        """Recursively find Block nodes."""
        for node in nodes:
            if isinstance(node, Block):
                blocks.append(node)

            # Recurse into containers
            for attr in ("body", "else_", "empty"):
                children = getattr(node, attr, None)
                if children:
                    self._collect_blocks_recursive(children, blocks)

            # Handle elif
            elif_ = getattr(node, "elif_", None)
            if elif_:
                for _test, body in elif_:
                    self._collect_blocks_recursive(body, blocks)

            # Handle match cases
            cases = getattr(node, "cases", None)
            if cases:
                for _pattern, _guard, body in cases:
                    self._collect_blocks_recursive(body, blocks)

    def _analyze_top_level(
        self,
        ast: Template,
        block_names: set[str],
    ) -> frozenset[str]:
        """Analyze dependencies in top-level code outside blocks.

        This captures dependencies from:
        - Code before/after blocks
        - Extends expression (e.g., dynamic parent template)
        - Context type declarations

        Does NOT include dependencies from inside blocks (those are
        tracked per-block).
        """
        deps: set[str] = set()

        # Analyze extends expression
        if ast.extends:
            extends_deps = self._dep_walker.analyze(ast.extends)
            deps.update(extends_deps)

        # Walk top-level nodes, excluding block bodies
        self._analyze_top_level_nodes(ast.body, block_names, deps)

        return frozenset(deps)

    def _analyze_top_level_nodes(
        self,
        nodes: Sequence[Node],
        block_names: set[str],
        deps: set[str],
    ) -> None:
        """Walk nodes, collecting dependencies but skipping block bodies."""
        for node in nodes:
            node_type = type(node).__name__

            if node_type == "Block":
                # Skip block body - it's analyzed separately
                continue

            if node_type in (
                "Output",
                "If",
                "For",
                "AsyncFor",
                "Set",
                "Let",
                "With",
                "WithConditional",
                "Include",
                "Import",
                "FromImport",
                "Cache",
                "Match",
            ):
                # These nodes may have dependencies
                node_deps = self._dep_walker.analyze(node)
                deps.update(node_deps)

            elif node_type == "Data":
                # Static content has no dependencies
                continue

            elif node_type in ("Def", "Macro"):
                # Function definitions - analyze body for lexical scope access
                node_deps = self._dep_walker.analyze(node)
                deps.update(node_deps)

            else:
                # Unknown node type - try to analyze it
                try:
                    node_deps = self._dep_walker.analyze(node)
                    deps.update(node_deps)
                except (AttributeError, TypeError) as e:
                    # Expected for some node types that don't support dependency analysis
                    logger.debug(f"Skipping node analysis: {type(node).__name__}: {e}")
                except Exception as e:
                    # Unexpected - log for debugging but don't fail
                    logger.warning(
                        f"Unexpected error analyzing {type(node).__name__}: {e}",
                        exc_info=False,  # Don't include full traceback for warnings
                    )

    def _check_emits_html(self, node: Node) -> bool:
        """Check if a node produces any output."""
        if isinstance(node, Data) and node.value.strip():
            return True
        if isinstance(node, Output):
            return True

        for attr in ("body", "else_", "empty"):
            if hasattr(node, attr):
                children = getattr(node, attr)
                if children:
                    for child in children:
                        if hasattr(child, "lineno") and self._check_emits_html(child):
                            return True

        # Handle elif
        elif_ = getattr(node, "elif_", None)
        if elif_:
            for _test, body in elif_:
                for child in body:
                    if hasattr(child, "lineno") and self._check_emits_html(child):
                        return True

        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Call-site validation
    # ─────────────────────────────────────────────────────────────────────────

    def validate_calls(self, ast: Template) -> list[CallValidation]:
        """Validate call sites against {% def %} signatures.

        Walks the AST to collect all ``{% def %}`` signatures, then checks
        every ``FuncCall`` and ``{% call %}`` site that references a known
        definition. Reports unknown parameters, missing required parameters,
        and duplicate keyword arguments.

        Only validates calls within the same compilation unit. Cross-template
        calls (via ``{% from ... import %}``) are not checked.

        When a ``{% def %}`` declares ``*args`` or ``**kwargs``, validation
        is relaxed accordingly (extra positional/keyword args are allowed).

        Args:
            ast: Parsed template AST.

        Returns:
            List of ``CallValidation`` results — one per problematic call site.
            An empty list means all call sites are valid.
        """
        # 1. Collect all {% def %} signatures
        signatures: dict[str, _DefSignature] = {}
        self._collect_defs(ast.body, signatures)

        # 2. Walk AST for FuncCall nodes and validate
        issues: list[CallValidation] = []
        self._validate_call_nodes(ast.body, signatures, issues)

        return issues

    def _collect_defs(
        self,
        nodes: Sequence[Node],
        signatures: dict[str, _DefSignature],
    ) -> None:
        """Recursively collect {% def %} signatures from the AST."""
        for node in nodes:
            if isinstance(node, Def):
                sig = _DefSignature.from_def(node)
                signatures[node.name] = sig
                # Also recurse into def body (nested defs)
                self._collect_defs(node.body, signatures)
                continue

            # Recurse into containers
            for attr in ("body", "else_", "empty"):
                children = getattr(node, attr, None)
                if children and isinstance(children, (list, tuple)):
                    self._collect_defs(children, signatures)

            # Handle elif
            elif_ = getattr(node, "elif_", None)
            if elif_:
                for _test, body in elif_:
                    self._collect_defs(body, signatures)

            # Handle match cases
            cases = getattr(node, "cases", None)
            if cases:
                for _pattern, _guard, body in cases:
                    self._collect_defs(body, signatures)

    def _validate_call_nodes(
        self,
        nodes: Sequence[Node],
        signatures: dict[str, _DefSignature],
        issues: list[CallValidation],
    ) -> None:
        """Recursively walk nodes and validate FuncCall sites."""
        for node in nodes:
            # Check CallBlock: {% call func(...) %}
            if isinstance(node, CallBlock):
                self._check_func_call(node.call, signatures, issues)
                self._validate_call_nodes(node.body, signatures, issues)
                continue

            # Check Output expressions ({{ func(...) }})
            if isinstance(node, Output):
                self._check_func_call(node.expr, signatures, issues)
                continue

            # Check {% def %} body
            if isinstance(node, Def):
                self._validate_call_nodes(node.body, signatures, issues)
                continue

            # Check expression nodes that may contain FuncCall
            expr = getattr(node, "value", None)
            if expr and hasattr(expr, "lineno"):
                self._check_func_call(expr, signatures, issues)

            # Recurse into containers
            for attr in ("body", "else_", "empty"):
                children = getattr(node, attr, None)
                if children and isinstance(children, (list, tuple)):
                    self._validate_call_nodes(children, signatures, issues)

            elif_ = getattr(node, "elif_", None)
            if elif_:
                for _test, body in elif_:
                    self._validate_call_nodes(body, signatures, issues)

            cases = getattr(node, "cases", None)
            if cases:
                for _pattern, _guard, body in cases:
                    self._validate_call_nodes(body, signatures, issues)

    def _check_func_call(
        self,
        expr: Node,
        signatures: dict[str, _DefSignature],
        issues: list[CallValidation],
    ) -> None:
        """Check a single expression for FuncCall nodes targeting known defs."""
        if not isinstance(expr, FuncCall):
            return

        # Only validate calls to names (not attribute calls like obj.method())
        if not isinstance(expr.func, Name):
            return

        func_name = expr.func.name
        sig = signatures.get(func_name)
        if sig is None:
            return  # Not a known {% def %} — skip

        # Validate keyword arguments
        call_kwargs = list(expr.kwargs.keys())

        # Check for duplicate keyword args
        seen: set[str] = set()
        duplicates: list[str] = []
        for kw in call_kwargs:
            if kw in seen:
                duplicates.append(kw)
            seen.add(kw)

        # Check for unknown parameter names
        unknown: list[str] = (
            [kw for kw in call_kwargs if kw not in sig.param_names]
            if not sig.has_kwarg
            else []
        )

        # Check for missing required parameters
        # Required = params without defaults that aren't supplied
        # Positional args fill params left-to-right
        n_positional = len(expr.args)
        missing: list[str] = []

        if not sig.has_vararg:
            for i, param_name in enumerate(sig.required_params):
                if i < n_positional:
                    continue  # Filled by positional arg
                if param_name not in seen:
                    missing.append(param_name)

        if unknown or missing or duplicates:
            issues.append(CallValidation(
                def_name=func_name,
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                unknown_params=tuple(unknown),
                missing_required=tuple(missing),
                duplicate_params=tuple(duplicates),
            ))


@dataclass(frozen=True, slots=True)
class _DefSignature:
    """Internal: extracted signature of a {% def %} for call validation."""

    param_names: frozenset[str]
    required_params: tuple[str, ...]
    has_vararg: bool
    has_kwarg: bool

    @staticmethod
    def from_def(node: Def) -> _DefSignature:
        """Build signature from a Def AST node."""
        all_names = [p.name for p in node.params]
        # Required params: those without defaults (counted from the end)
        n_defaults = len(node.defaults)
        n_total = len(all_names)
        required = all_names[: n_total - n_defaults] if n_defaults < n_total else []

        return _DefSignature(
            param_names=frozenset(all_names),
            required_params=tuple(required),
            has_vararg=node.vararg is not None,
            has_kwarg=node.kwarg is not None,
        )


def _compute_block_hash(block_node: Block) -> str:
    """Compute deterministic structural hash for a block AST."""
    parts: list[str] = []

    def visit(node: Node) -> None:
        parts.append(type(node).__name__)

        for attr in ("name", "value", "data"):
            raw_value = getattr(node, attr, None)
            if raw_value is not None:
                parts.append(repr(raw_value))

        for attr in ("body", "else_", "empty"):
            children = getattr(node, attr, None)
            if children:
                for child in children:
                    if isinstance(child, Node):
                        visit(child)

        elif_ = getattr(node, "elif_", None)
        if elif_:
            for _test, body in elif_:
                for child in body:
                    if isinstance(child, Node):
                        visit(child)

        cases = getattr(node, "cases", None)
        if cases:
            for _pattern, _guard, body in cases:
                for child in body:
                    if isinstance(child, Node):
                        visit(child)

    visit(block_node)
    payload = "|".join(parts)
    return sha256(payload.encode("utf-8")).hexdigest()[:16]
