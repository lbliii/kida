"""Basic statement compilation for Kida compiler.

Provides mixin for compiling basic output statements (data, output).

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


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
        def _compile_expr(self, node: Any, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _emit_output(self, value_expr: ast.expr) -> ast.stmt: ...

    def _compile_data(self, node: Any) -> list[ast.stmt]:
        """Compile raw text data.

        StringBuilder mode: _append("literal text")
        Streaming mode: yield "literal text"
        """
        if not node.value:
            return []

        return [self._emit_output(ast.Constant(value=node.value))]

    def _compile_output(self, node: Any) -> list[ast.stmt]:
        """Compile {{ expression }} output.

        StringBuilder mode: _append(_e(expr)) or _append(_s(expr))
        Streaming mode: yield _e(expr) or yield _s(expr)
        """
        expr = self._compile_expr(node.expr)

        # Wrap in escape if needed - _e handles str conversion internally
        # to properly detect Markup objects before converting to str
        if node.escape:
            expr = ast.Call(
                func=ast.Name(id="_e", ctx=ast.Load()),
                args=[expr],
                keywords=[],
            )
        else:
            expr = ast.Call(
                func=ast.Name(id="_s", ctx=ast.Load()),
                args=[expr],
                keywords=[],
            )

        return [self._emit_output(expr)]
