"""Sync-to-stream Python AST transformer.

Transforms compiled sync block stmts (_append calls) into streaming stmts
(yield expressions). This eliminates a redundant full Kida AST compilation
per block by deriving the stream variant from the sync compilation output.

The transform replaces:
    _append(expr)  →  yield expr
    return ''.join(buf)  →  (removed)

The preamble and return/sentinel are handled by the caller, not this transform.

Uses copy-on-write: only nodes on the path to ``_append`` call sites are
copied.  Unchanged subtrees are shared with the original AST, making this
safe to call multiple times on the same input (e.g. for stream + async
stream variants).
"""

from __future__ import annotations

import ast
import copy
from typing import Any


def sync_body_to_stream(stmts: list[ast.stmt]) -> list[ast.stmt]:
    """Transform compiled sync body statements into streaming equivalents.

    Walks the AST and replaces ``_append(expr)`` calls with ``yield expr``.
    Uses copy-on-write so the original *stmts* are never modified — safe to
    call repeatedly on the same input.

    Args:
        stmts: Compiled Python AST statements from sync block compilation.

    Returns:
        New list of statements with _append replaced by yield.
    """
    transformer = _AppendToYield()
    result: list[ast.stmt] = []
    for stmt in stmts:
        new_stmt = transformer.visit(stmt)
        if new_stmt is not None:
            result.append(new_stmt)
    return result


class _AppendToYield(ast.NodeTransformer):
    """Replace ``_append(expr)`` with ``yield expr`` in Python AST.

    Overrides ``generic_visit`` with a copy-on-write strategy: only nodes
    whose children actually changed are shallow-copied.  Unchanged subtrees
    are returned as-is (identity), so the original AST is never mutated.
    """

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
        # Not an _append call — return as-is (no mutation)
        return node

    def generic_visit(self, node: ast.AST) -> ast.AST:
        """Copy-on-write: only copy nodes whose children changed."""
        changes: dict[str, Any] = {}

        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                new_values: list[Any] = []
                changed = False
                for item in old_value:
                    if isinstance(item, ast.AST):
                        new_item = self.visit(item)
                        if new_item is not item:
                            changed = True
                        if isinstance(new_item, list):
                            new_values.extend(new_item)
                        elif new_item is not None:
                            new_values.append(new_item)
                        else:
                            changed = True  # node removed
                    else:
                        new_values.append(item)
                if changed:
                    changes[field] = new_values
            elif isinstance(old_value, ast.AST):
                new_value = self.visit(old_value)
                if new_value is not old_value:
                    changes[field] = new_value

        if not changes:
            return node  # No modifications — return same node (identity)

        # Shallow copy and apply only the changed fields
        new_node = copy.copy(node)
        for field, value in changes.items():
            setattr(new_node, field, value)
        return new_node
