"""Sync-to-stream Python AST transformer.

Transforms compiled sync block stmts (_append calls) into streaming stmts
(yield expressions). This eliminates a redundant full Kida AST compilation
per block by deriving the stream variant from the sync compilation output.

The transform replaces:
    _append(expr)  →  yield expr
    return ''.join(buf)  →  (removed)

The preamble and return/sentinel are handled by the caller, not this transform.
"""

from __future__ import annotations

import ast
import copy


def sync_body_to_stream(stmts: list[ast.stmt]) -> list[ast.stmt]:
    """Transform compiled sync body statements into streaming equivalents.

    Walks the AST and replaces ``_append(expr)`` calls with ``yield expr``.
    Returns a deep copy — the original stmts are not modified.

    Args:
        stmts: Compiled Python AST statements from sync block compilation.

    Returns:
        New list of statements with _append replaced by yield.
    """
    transformer = _AppendToYield()
    result: list[ast.stmt] = []
    for stmt in stmts:
        new_stmt = transformer.visit(copy.deepcopy(stmt))
        if new_stmt is not None:
            result.append(new_stmt)
    return result


class _AppendToYield(ast.NodeTransformer):
    """Replace ``_append(expr)`` with ``yield expr`` in Python AST."""

    def visit_Expr(self, node: ast.Expr) -> ast.Expr:
        """Transform _append(x) expression statements to yield x."""
        # Match: _append(expr) — the standard output pattern
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_append"
            and len(node.value.args) == 1
        ):
            return ast.copy_location(
                ast.Expr(value=ast.Yield(value=node.value.args[0])),
                node,
            )
        # Not an _append call — visit children for nested _append patterns
        self.generic_visit(node)
        return node
