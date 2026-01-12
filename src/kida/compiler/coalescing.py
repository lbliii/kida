"""F-String Coalescing for Kida Compiler.

RFC: fstring-code-generation

Generates Python f-strings for consecutive template output operations
instead of multiple `buf.append()` calls, reducing function call overhead
by ~37% in output-heavy templates.

Example transformation:
    Before (5 function calls):
        _append('<div id="')
        _append(_e(item["id"]))
        _append('">')
        _append(_e(item["name"]))
        _append('</div>')

    After (1 function call):
        _append(f'<div id="{_e(item["id"])}">{_e(item["name"])}</div>')

Design:
    - Only coalesce consecutive Data and simple Output nodes
    - Fall back to separate appends for complex expressions (function calls, etc.)
    - Use ast.JoinedStr for f-string generation (handles brace escaping automatically)
    - Detect backslashes in expressions (f-strings don't allow them)

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kida.environment import Environment

# Coalescing threshold - minimum nodes to trigger f-string generation
COALESCE_MIN_NODES = 2

# Built-in filters known to be pure (no side effects, deterministic)
# These filters can be safely coalesced into f-strings
_BUILTIN_PURE_FILTERS: frozenset[str] = frozenset({
    # String case transformations
    "upper", "lower", "title", "capitalize", "swapcase",
    # Whitespace handling
    "trim", "strip", "lstrip", "rstrip",
    # HTML escaping
    "escape", "e", "forceescape",
    # Default values
    "default", "d",
    # Type conversion
    "int", "float", "string", "str", "bool",
    # Collection info
    "length", "count",
    # Collection access
    "first", "last",
    # String operations
    "join", "center", "ljust", "rjust",
    # Formatting
    "truncate", "wordwrap", "indent",
    # URL encoding
    "urlencode",
})


class FStringCoalescingMixin:
    """Mixin for f-string coalescing optimization.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        _env: Environment

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Any, store: bool = False) -> ast.expr: ...

        # From Compiler (for _compile_node)
        def _compile_node(self, node: Any) -> list[ast.stmt]: ...

    def _get_pure_filters(self) -> frozenset[str]:
        """Get combined set of built-in and user-defined pure filters."""
        if self._env.pure_filters:
            return _BUILTIN_PURE_FILTERS | frozenset(self._env.pure_filters)
        return _BUILTIN_PURE_FILTERS

    def _is_coalesceable(self, node: Any) -> bool:
        """Check if node can be coalesced into an f-string.

        Coalesceable nodes:
            - Data nodes (literal text)
            - Output nodes with simple expressions

        Non-coalesceable nodes:
            - Control flow (If, For, While, etc.)
            - Output with complex expressions (function calls, etc.)
            - Any node containing backslashes in string constants
        """
        from kida.nodes import Data, Output

        if isinstance(node, Data):
            # Data nodes are coalesceable, but check for backslashes
            # which would need escaping in f-string context
            return True

        if isinstance(node, Output):
            return self._is_simple_output(node)

        return False

    def _is_simple_output(self, node: Any) -> bool:
        """Check if Output node is simple enough for f-string."""
        return self._is_simple_expr(node.expr)

    def _is_simple_expr(self, expr: Any) -> bool:
        """Recursively check if expression is simple enough for f-string.

        Simple expressions:
            - Constants (strings, numbers, booleans)
            - Names (variable references)
            - Attribute access (name.attr, name.attr.subattr)
            - Item access (name[key], name["key"])
            - Pure filters with simple arguments
            - Pipelines with all pure steps
            - InlinedFilter (method calls like .upper())

        Complex expressions (NOT coalesceable):
            - Function calls (may have side effects)
            - Ternary expressions (complex control flow)
            - Binary/unary ops (complex evaluation)
            - Expressions containing backslashes
        """
        from kida.nodes import (
            Const, Name, Getattr, Getitem, OptionalGetattr, OptionalGetitem,
            Filter, Pipeline, InlinedFilter,
        )

        # Check for backslashes in string constants
        if self._expr_contains_backslash(expr):
            return False

        # Base cases: constants and names are always simple
        if isinstance(expr, Const):
            return True

        if isinstance(expr, Name):
            return True

        # Attribute access: check base is simple
        if isinstance(expr, (Getattr, OptionalGetattr)):
            obj = expr.obj if isinstance(expr, Getattr) else expr.obj
            return self._is_simple_expr(obj)

        # Item access: check both base and key are simple
        if isinstance(expr, (Getitem, OptionalGetitem)):
            obj = expr.obj
            key = expr.key
            return (
                self._is_simple_expr(obj) and
                self._is_simple_expr(key)
            )

        # InlinedFilter: method calls like .upper() are simple if value is simple
        if isinstance(expr, InlinedFilter):
            if not self._is_simple_expr(expr.value):
                return False
            # Check all args are simple
            return all(self._is_simple_expr(arg) for arg in expr.args)

        # Filter: check filter is pure AND value/args are simple
        if isinstance(expr, Filter):
            pure_filters = self._get_pure_filters()
            if expr.name not in pure_filters:
                return False
            # Check the filtered value is simple
            if not self._is_simple_expr(expr.value):
                return False
            # Check all positional args are simple
            if not all(self._is_simple_expr(arg) for arg in expr.args):
                return False
            # Check all keyword args are simple
            if not all(self._is_simple_expr(v) for v in expr.kwargs.values()):
                return False
            return True

        # Pipeline: check all steps are pure with simple args
        if isinstance(expr, Pipeline):
            pure_filters = self._get_pure_filters()
            if not self._is_simple_expr(expr.value):
                return False
            for name, args, kwargs in expr.steps:
                if name not in pure_filters:
                    return False
                if not all(self._is_simple_expr(arg) for arg in args):
                    return False
                if not all(self._is_simple_expr(v) for v in kwargs.values()):
                    return False
            return True

        # Function calls are NOT coalesceable (may have side effects)
        # Ternary expressions are NOT coalesceable (complex control flow)
        # Binary/unary ops are NOT coalesceable (complex evaluation)
        return False

    def _expr_contains_backslash(self, expr: Any) -> bool:
        """Check if expression would generate code with backslashes.

        F-strings cannot contain backslashes in expression parts.
        This is a Python syntax limitation.
        """
        from kida.nodes import (
            Const, Name, Getattr, Getitem, OptionalGetattr, OptionalGetitem,
            Filter, Pipeline, InlinedFilter,
        )

        if isinstance(expr, Const):
            if isinstance(expr.value, str) and "\\" in expr.value:
                return True
            return False

        if isinstance(expr, Name):
            return False

        if isinstance(expr, (Getattr, OptionalGetattr)):
            return self._expr_contains_backslash(expr.obj)

        if isinstance(expr, (Getitem, OptionalGetitem)):
            return (
                self._expr_contains_backslash(expr.obj) or
                self._expr_contains_backslash(expr.key)
            )

        if isinstance(expr, InlinedFilter):
            if self._expr_contains_backslash(expr.value):
                return True
            return any(self._expr_contains_backslash(arg) for arg in expr.args)

        if isinstance(expr, Filter):
            if self._expr_contains_backslash(expr.value):
                return True
            if any(self._expr_contains_backslash(arg) for arg in expr.args):
                return True
            if any(self._expr_contains_backslash(v) for v in expr.kwargs.values()):
                return True
            return False

        if isinstance(expr, Pipeline):
            if self._expr_contains_backslash(expr.value):
                return True
            for _name, args, kwargs in expr.steps:
                if any(self._expr_contains_backslash(arg) for arg in args):
                    return True
                if any(self._expr_contains_backslash(v) for v in kwargs.values()):
                    return True
            return False

        return False

    def _compile_coalesced_output(self, nodes: list[Any]) -> ast.stmt:
        """Generate f-string append for coalesced nodes.

        Note on brace handling:
            ast.JoinedStr automatically handles brace escaping when the AST
            is compiled to bytecode. We do NOT manually escape {{ and }}.
            Literal text goes into ast.Constant nodes as-is.
            Expressions go into ast.FormattedValue nodes.

        Note on backslashes:
            F-strings cannot contain backslashes in expression parts.
            We detect backslashes during coalesceable checking and fall back.
        """
        from kida.nodes import Data, Output

        # Build f-string components
        parts: list[ast.expr] = []

        for node in nodes:
            if isinstance(node, Data):
                # Literal text - add as constant (NO manual brace escaping)
                # ast.JoinedStr handles escaping during bytecode compilation
                if node.value:  # Skip empty strings
                    parts.append(ast.Constant(value=node.value))

            elif isinstance(node, Output):
                # Expression - wrap in escape/str function
                expr = self._compile_expr(node.expr)

                if node.escape:
                    # _e() handles HTML escaping
                    expr = ast.Call(
                        func=ast.Name(id="_e", ctx=ast.Load()),
                        args=[expr],
                        keywords=[],
                    )
                else:
                    # _s() converts to string (for |safe outputs)
                    expr = ast.Call(
                        func=ast.Name(id="_s", ctx=ast.Load()),
                        args=[expr],
                        keywords=[],
                    )

                parts.append(ast.FormattedValue(
                    value=expr,
                    conversion=-1,  # No conversion (!s, !r, !a)
                    format_spec=None,
                ))

        # Create JoinedStr (f-string AST node)
        fstring = ast.JoinedStr(values=parts)

        # _append(f"...")
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id="_append", ctx=ast.Load()),
                args=[fstring],
                keywords=[],
            )
        )

    def _compile_body_with_coalescing(self, nodes: list[Any]) -> list[ast.stmt]:
        """Compile template body with f-string output coalescing.

        Groups consecutive coalesceable nodes and generates single f-string
        appends for groups of 2+ nodes. Falls back to normal compilation
        for single nodes or non-coalesceable nodes.

        Args:
            nodes: List of template AST nodes to compile

        Returns:
            List of Python AST statements
        """
        # Skip if optimization disabled
        if not self._env.fstring_coalescing:
            return [stmt for node in nodes for stmt in self._compile_node(node)]

        stmts: list[ast.stmt] = []
        i = 0

        while i < len(nodes):
            # Try to coalesce consecutive outputs
            coalesceable: list[Any] = []
            while i < len(nodes) and self._is_coalesceable(nodes[i]):
                coalesceable.append(nodes[i])
                i += 1

            if len(coalesceable) >= COALESCE_MIN_NODES:
                # Generate single f-string append
                stmts.append(self._compile_coalesced_output(coalesceable))
            elif coalesceable:
                # Single node - use normal compilation
                for node in coalesceable:
                    stmts.extend(self._compile_node(node))

            # Compile non-coalesceable node normally
            if i < len(nodes) and not self._is_coalesceable(nodes[i]):
                stmts.extend(self._compile_node(nodes[i]))
                i += 1

        return stmts
