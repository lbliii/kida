"""Purity analysis for template introspection.

Determines if expressions and blocks are pure (deterministic).
Pure blocks produce the same output for the same inputs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal, cast

from kida.environment.exceptions import TemplateNotFoundError, TemplateSyntaxError

if TYPE_CHECKING:
    from kida.nodes import Node

# Purity lattice: pure < unknown < impure
# When combining, take the most conservative (worst case)

PurityLevel = Literal["pure", "unknown", "impure"]


def _combine_purity(a: PurityLevel, b: PurityLevel) -> PurityLevel:
    """Combine two purity levels (take worst case)."""
    if a == "impure" or b == "impure":
        return "impure"
    if a == "unknown" or b == "unknown":
        return "unknown"
    return "pure"


# Filters known to be pure (deterministic, no side effects)
_KNOWN_PURE_FILTERS = frozenset(
    {
        # String manipulation
        "upper",
        "lower",
        "title",
        "capitalize",
        "swapcase",
        "strip",
        "lstrip",
        "rstrip",
        "trim",
        "replace",
        "truncate",
        "wordwrap",
        "center",
        "indent",
        "striptags",
        "urlize",
        "wordcount",
        # Collections
        "first",
        "last",
        "length",
        "count",
        "sort",
        "reverse",
        "unique",
        "batch",
        "slice",
        "list",
        "map",
        "select",
        "reject",
        "selectattr",
        "rejectattr",
        "groupby",
        "join",
        "pprint",
        # Type conversion
        "string",
        "int",
        "float",
        "bool",
        "tojson",
        "safe",
        "escape",
        "e",
        # Defaults
        "default",
        "d",
        # Math
        "abs",
        "round",
        "sum",
        "min",
        "max",
        # Format
        "filesizeformat",
        "format",
        # Path/URL
        "basename",
        "dirname",
        "splitext",
        # Kida-specific
        "take",
        "skip",
        "where",
        "sort_by",
        # SSG-specific (deterministic for a build)
        "dateformat",
        "date_iso",
        "date",
        "absolute_url",
        "relative_url",
        "meta_keywords",
        "jsonify",
        "markdownify",
        "slugify",
        "plainify",
        "humanize",
        "titlecase",
        "words",
    }
)

# Filters known to be impure (non-deterministic)
_KNOWN_IMPURE_FILTERS = frozenset(
    {
        "random",
        "shuffle",
    }
)

# Functions known to be pure
_KNOWN_PURE_FUNCTIONS = frozenset(
    {
        # Python builtins
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "frozenset",
        "min",
        "max",
        "sum",
        "abs",
        "round",
        "pow",
        "sorted",
        "reversed",
        "enumerate",
        "zip",
        "map",
        "filter",
        "any",
        "all",
        "range",
        "hasattr",
        "getattr",
        "isinstance",
        "type",
        "ord",
        "chr",
        "hex",
        "oct",
        "bin",
        "repr",
        "hash",
    }
)


class PurityAnalyzer:
    """Determine if an expression or block is pure (deterministic).

    Pure expressions produce the same output for the same inputs.
    This is used to determine cache safety.

    Conservative: defaults to "unknown" when uncertain.

    Example:
            >>> analyzer = PurityAnalyzer()
            >>> purity = analyzer.analyze(block_node)
            >>> print(purity)
            'pure'

    Purity Rules:
        - Constants, variables, attribute access: pure
        - Binary/unary operations, comparisons: pure
        - Known pure filters (upper, lower, sort, etc.): pure
        - Known impure filters (random, shuffle): impure
        - Unknown filters/functions: unknown

    """

    def __init__(
        self,
        extra_pure_functions: frozenset[str] | None = None,
        extra_impure_filters: frozenset[str] | None = None,
        template_resolver: Callable[[str], Any] | None = None,
    ) -> None:
        """Initialize analyzer with optional extensions.

        Args:
            extra_pure_functions: Additional functions to treat as pure.
            extra_impure_filters: Additional filters to treat as impure.
            template_resolver: Optional callback(name: str) -> Template | None
                to resolve included templates. If None, includes return "unknown".
        """
        self._pure_functions = _KNOWN_PURE_FUNCTIONS
        if extra_pure_functions:
            self._pure_functions = self._pure_functions | extra_pure_functions

        self._impure_filters = _KNOWN_IMPURE_FILTERS
        if extra_impure_filters:
            self._impure_filters = self._impure_filters | extra_impure_filters

        self._template_resolver = template_resolver
        self._visited_templates: set[str] = set()  # Track circular includes

    def analyze(self, node: Node) -> PurityLevel:
        """Analyze a node and return its purity level.

        Args:
            node: AST node to analyze.

        Returns:
            "pure", "impure", or "unknown"
        """
        return self._visit(node)

    def _visit(self, node: Node | None) -> PurityLevel:
        """Visit a node and determine purity."""
        if node is None:
            return "pure"

        node_type = type(node).__name__

        handler = getattr(self, f"_visit_{node_type.lower()}", None)
        if handler:
            return cast(PurityLevel, handler(node))

        # Default: check children
        return self._visit_children(node)

    def _visit_children(self, node: Node) -> PurityLevel:
        """Visit children and combine purity."""
        result: PurityLevel = "pure"

        for attr in ("body", "else_", "empty"):
            if hasattr(node, attr):
                children = getattr(node, attr)
                if children:
                    for child in children:
                        if hasattr(child, "lineno"):
                            result = _combine_purity(result, self._visit(child))

        for attr in (
            "test",
            "expr",
            "value",
            "iter",
            "left",
            "right",
            "operand",
            "obj",
            "key",
            "if_true",
            "if_false",
        ):
            if hasattr(node, attr):
                child = getattr(node, attr)
                if child and hasattr(child, "lineno"):
                    result = _combine_purity(result, self._visit(child))

        return result

    def _visit_const(self, node: Node) -> PurityLevel:
        """Constants are pure."""
        return "pure"

    def _visit_name(self, node: Node) -> PurityLevel:
        """Variable access is pure (reading doesn't mutate)."""
        return "pure"

    def _visit_getattr(self, node: Node) -> PurityLevel:
        """Attribute access is pure."""
        return self._visit(node.obj)

    def _visit_optionalgetattr(self, node: Node) -> PurityLevel:
        """Optional attribute access is pure."""
        return self._visit(node.obj)

    def _visit_getitem(self, node: Node) -> PurityLevel:
        """Subscript access is pure."""
        return _combine_purity(
            self._visit(node.obj),
            self._visit(node.key),
        )

    def _visit_optionalgetitem(self, node: Node) -> PurityLevel:
        """Optional subscript access is pure."""
        return _combine_purity(
            self._visit(node.obj),
            self._visit(node.key),
        )

    def _visit_binop(self, node: Node) -> PurityLevel:
        """Binary operations are pure."""
        return _combine_purity(
            self._visit(node.left),
            self._visit(node.right),
        )

    def _visit_unaryop(self, node: Node) -> PurityLevel:
        """Unary operations are pure."""
        return self._visit(node.operand)

    def _visit_compare(self, node: Node) -> PurityLevel:
        """Comparisons are pure."""
        result = self._visit(node.left)
        for comp in node.comparators:
            result = _combine_purity(result, self._visit(comp))
        return result

    def _visit_boolop(self, node: Node) -> PurityLevel:
        """Boolean operations are pure."""
        result: PurityLevel = "pure"
        for value in node.values:
            result = _combine_purity(result, self._visit(value))
        return result

    def _visit_condexpr(self, node: Node) -> PurityLevel:
        """Conditional expressions are pure if all parts are pure."""
        return _combine_purity(
            self._visit(node.test),
            _combine_purity(
                self._visit(node.if_true),
                self._visit(node.if_false),
            ),
        )

    def _visit_nullcoalesce(self, node: Node) -> PurityLevel:
        """Null coalescing is pure."""
        return _combine_purity(
            self._visit(node.left),
            self._visit(node.right),
        )

    def _visit_concat(self, node: Node) -> PurityLevel:
        """String concatenation is pure."""
        result: PurityLevel = "pure"
        for child in node.nodes:
            result = _combine_purity(result, self._visit(child))
        return result

    def _visit_range(self, node: Node) -> PurityLevel:
        """Range literals are pure."""
        result = _combine_purity(
            self._visit(node.start),
            self._visit(node.end),
        )
        if node.step:
            result = _combine_purity(result, self._visit(node.step))
        return result

    def _visit_slice(self, node: Node) -> PurityLevel:
        """Slice expressions are pure."""
        result: PurityLevel = "pure"
        if node.start:
            result = _combine_purity(result, self._visit(node.start))
        if node.stop:
            result = _combine_purity(result, self._visit(node.stop))
        if node.step:
            result = _combine_purity(result, self._visit(node.step))
        return result

    def _visit_list(self, node: Node) -> PurityLevel:
        """List literals are pure if all items are pure."""
        result: PurityLevel = "pure"
        for item in node.items:
            result = _combine_purity(result, self._visit(item))
        return result

    def _visit_tuple(self, node: Node) -> PurityLevel:
        """Tuple literals are pure if all items are pure."""
        result: PurityLevel = "pure"
        for item in node.items:
            result = _combine_purity(result, self._visit(item))
        return result

    def _visit_dict(self, node: Node) -> PurityLevel:
        """Dict literals are pure if all keys and values are pure."""
        result: PurityLevel = "pure"
        for key in node.keys:
            result = _combine_purity(result, self._visit(key))
        for value in node.values:
            result = _combine_purity(result, self._visit(value))
        return result

    def _visit_filter(self, node: Node) -> PurityLevel:
        """Filter purity depends on the filter."""
        # Check filter name
        if node.name in _KNOWN_PURE_FILTERS:
            filter_purity: PurityLevel = "pure"
        elif node.name in self._impure_filters:
            filter_purity = "impure"
        else:
            filter_purity = "unknown"  # User-defined

        # Combine with value and args
        result = _combine_purity(filter_purity, self._visit(node.value))
        for arg in node.args:
            result = _combine_purity(result, self._visit(arg))
        for value in node.kwargs.values():
            result = _combine_purity(result, self._visit(value))

        return result

    def _visit_pipeline(self, node: Node) -> PurityLevel:
        """Pipeline purity depends on all filters in the chain."""
        result = self._visit(node.value)

        for filter_name, args, kwargs in node.steps:
            # Check filter purity
            if filter_name in _KNOWN_PURE_FILTERS:
                filter_purity: PurityLevel = "pure"
            elif filter_name in self._impure_filters:
                filter_purity = "impure"
            else:
                filter_purity = "unknown"

            result = _combine_purity(result, filter_purity)

            # Check args
            for arg in args:
                result = _combine_purity(result, self._visit(arg))
            for value in kwargs.values():
                result = _combine_purity(result, self._visit(value))

        return result

    def _visit_funccall(self, node: Node) -> PurityLevel:
        """Function call purity depends on the function."""
        # Check if it's a known pure builtin
        if type(node.func).__name__ == "Name":
            func_name = node.func.name
            if func_name in self._pure_functions:
                # Pure function - check arguments
                result: PurityLevel = "pure"
                for arg in node.args:
                    result = _combine_purity(result, self._visit(arg))
                for value in node.kwargs.values():
                    result = _combine_purity(result, self._visit(value))
                return result

        # Unknown function - conservative
        return "unknown"

    def _visit_test(self, node: Node) -> PurityLevel:
        """Tests are pure (they're just predicates)."""
        result = self._visit(node.value)
        for arg in node.args:
            result = _combine_purity(result, self._visit(arg))
        return result

    def _visit_for(self, node: Node) -> PurityLevel:
        """For loops are pure if body is pure."""
        result = self._visit(node.iter)
        for child in node.body:
            result = _combine_purity(result, self._visit(child))
        empty = getattr(node, "empty", None)
        if empty:
            for child in empty:
                result = _combine_purity(result, self._visit(child))
        return result

    def _visit_if(self, node: Node) -> PurityLevel:
        """Conditionals are pure if all branches are pure."""
        result = self._visit(node.test)
        for child in node.body:
            result = _combine_purity(result, self._visit(child))
        for child in node.else_:
            result = _combine_purity(result, self._visit(child))
        # Handle elif
        elif_ = getattr(node, "elif_", None)
        if elif_:
            for test, body in elif_:
                result = _combine_purity(result, self._visit(test))
                for child in body:
                    result = _combine_purity(result, self._visit(child))
        return result

    def _visit_match(self, node: Node) -> PurityLevel:
        """Match statements are pure if all branches are pure."""
        result = self._visit(node.subject)
        for pattern, guard, body in node.cases:
            result = _combine_purity(result, self._visit(pattern))
            if guard:
                result = _combine_purity(result, self._visit(guard))
            for child in body:
                result = _combine_purity(result, self._visit(child))
        return result

    def _visit_output(self, node: Node) -> PurityLevel:
        """Output is pure if expression is pure."""
        return self._visit(node.expr)

    def _visit_data(self, node: Node) -> PurityLevel:
        """Static data is pure."""
        return "pure"

    def _visit_cache(self, node: Node) -> PurityLevel:
        """Cache blocks: the body is evaluated, but result is cached.

        The block itself is pure if the body is pure.
        """
        result = self._visit(node.key)
        for child in node.body:
            result = _combine_purity(result, self._visit(child))
        return result

    def _visit_block(self, node: Node) -> PurityLevel:
        """Block is pure if body is pure."""
        result: PurityLevel = "pure"
        for child in node.body:
            result = _combine_purity(result, self._visit(child))
        return result

    def _visit_with(self, node: Node) -> PurityLevel:
        """With blocks are pure if bindings and body are pure."""
        result: PurityLevel = "pure"
        for _name, value in node.targets:
            result = _combine_purity(result, self._visit(value))
        for child in node.body:
            result = _combine_purity(result, self._visit(child))
        return result

    def _visit_withconditional(self, node: Node) -> PurityLevel:
        """Conditional with is pure if expr and body are pure."""
        result = self._visit(node.expr)
        for child in node.body:
            result = _combine_purity(result, self._visit(child))
        return result

    def _visit_set(self, node: Node) -> PurityLevel:
        """Set is pure if value is pure."""
        return self._visit(node.value)

    def _visit_let(self, node: Node) -> PurityLevel:
        """Let is pure if value is pure."""
        return self._visit(node.value)

    def _visit_capture(self, node: Node) -> PurityLevel:
        """Capture is pure if body is pure."""
        result: PurityLevel = "pure"
        for child in node.body:
            result = _combine_purity(result, self._visit(child))
        filter_node = getattr(node, "filter", None)
        if filter_node:
            result = _combine_purity(result, self._visit(filter_node))
        return result

    def _visit_include(self, node: Node) -> PurityLevel:
        """Include purity depends on included template.

        If template_resolver is provided and template name is a constant,
        resolves and analyzes the included template. Otherwise returns "unknown".
        """
        if self._template_resolver is None:
            return "unknown"

        # Extract template name - only handle constant strings
        template_expr = node.template
        if type(template_expr).__name__ != "Const":
            # Dynamic template name - can't analyze statically
            return "unknown"

        template_name = template_expr.value
        if not isinstance(template_name, str):
            return "unknown"

        # Check for circular includes
        if template_name in self._visited_templates:
            # Circular include detected - return unknown to avoid infinite recursion
            return "unknown"

        # Resolve and analyze included template
        try:
            included_template = self._template_resolver(template_name)
            if included_template is None:
                return "unknown"

            # Get AST from included template
            if (
                not hasattr(included_template, "_optimized_ast")
                or included_template._optimized_ast is None
            ):
                return "unknown"

            included_ast = included_template._optimized_ast

            # Analyze included template's body
            self._visited_templates.add(template_name)
            try:
                result: PurityLevel = "pure"
                for child in included_ast.body:
                    result = _combine_purity(result, self._visit(child))
                return result
            finally:
                self._visited_templates.remove(template_name)

        except (TemplateNotFoundError, TemplateSyntaxError):
            # Template missing or unparseable → conservatively unknown
            return "unknown"

    def _visit_extends(self, node: Node) -> PurityLevel:
        """Extends is unknown (depends on parent template)."""
        return "unknown"

    def _visit_def(self, node: Node) -> PurityLevel:
        """Function definition is pure if body is pure."""
        result: PurityLevel = "pure"
        for child in node.body:
            result = _combine_purity(result, self._visit(child))
        for default in node.defaults:
            result = _combine_purity(result, self._visit(default))
        return result

    def _visit_macro(self, node: Node) -> PurityLevel:
        """Macro definition (same as def)."""
        return self._visit_def(node)

    def _visit_inlinedfilter(self, node: Node) -> PurityLevel:
        """Inlined filter is pure (only pure filters are inlined)."""
        return self._visit(node.value)

    def _visit_marksafe(self, node: Node) -> PurityLevel:
        """Mark safe is pure."""
        return self._visit(node.value)

    def _visit_await(self, node: Node) -> PurityLevel:
        """Await is unknown (async operations may have side effects)."""
        return "unknown"

    # Leaf nodes
    def _visit_slot(self, node: Node) -> PurityLevel:
        return "pure"

    def _visit_break(self, node: Node) -> PurityLevel:
        return "pure"

    def _visit_continue(self, node: Node) -> PurityLevel:
        return "pure"

    def _visit_raw(self, node: Node) -> PurityLevel:
        return "pure"

    def _visit_loopvar(self, node: Node) -> PurityLevel:
        return "pure"
