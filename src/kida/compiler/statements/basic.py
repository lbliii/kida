"""Basic statement compilation for Kida compiler.

Provides mixin for compiling basic output statements (data, output).

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Data, Node, Output
    from kida.nodes.expressions import Expr


class BasicStatementMixin:
    """Mixin for compiling basic output statements.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.

    """

    # ─────────────────────────────────────────────────────────────────────────
    # Cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        _streaming: bool

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _emit_output(self, value_expr: ast.expr) -> ast.stmt: ...

    def _compile_data(self, node: Data) -> list[ast.stmt]:
        """Compile raw text data.

        StringBuilder mode: _append("literal text")
        Streaming mode: yield "literal text"
        """
        if not node.value:
            return []

        return [self._emit_output(ast.Constant(value=node.value))]

    @staticmethod
    def _expr_may_produce_none(node: Expr) -> bool:
        """Check if an expression involves optional chaining that may produce None.

        When optional chaining (?., ?[, ?|>) is the outermost expression in
        {{ ... }} output (not wrapped in ??), str(None) renders as "None".
        We detect this and use _str_safe to render "" instead.
        """
        from kida.nodes.expressions import (
            NullCoalesce,
            OptionalFilter,
            OptionalGetattr,
            OptionalGetitem,
            SafePipeline,
        )

        # If wrapped in ??, the user explicitly handles None — use normal str()
        if isinstance(node, NullCoalesce):
            return False
        return isinstance(node, (OptionalGetattr, OptionalGetitem, OptionalFilter, SafePipeline))

    def _compile_output(self, node: Output) -> list[ast.stmt]:
        """Compile {{ expression }} output.

        StringBuilder mode: _append(_e(expr)) or _append(_s(expr))
        Streaming mode: yield _e(expr) or yield _s(expr)

        When the expression involves optional chaining (?., ?[) without
        null coalescing (??), uses _str_safe instead of _s so that None
        renders as "" instead of "None".
        """
        expr = self._compile_expr(node.expr)

        # Wrap in escape if needed - _e handles str conversion internally
        # to properly detect Markup objects before converting to str
        if node.escape:
            # For optional chaining, convert None → "" before escaping
            if self._expr_may_produce_none(node.expr):
                expr = ast.Call(
                    func=ast.Name(id="_str_safe", ctx=ast.Load()),
                    args=[expr],
                    keywords=[],
                )
            expr = ast.Call(
                func=ast.Name(id="_e", ctx=ast.Load()),
                args=[expr],
                keywords=[],
            )
        else:
            # Use _str_safe for optional chaining so None → "" instead of "None"
            str_func = "_str_safe" if self._expr_may_produce_none(node.expr) else "_s"
            expr = ast.Call(
                func=ast.Name(id=str_func, ctx=ast.Load()),
                args=[expr],
                keywords=[],
            )

        return [self._emit_output(expr)]
