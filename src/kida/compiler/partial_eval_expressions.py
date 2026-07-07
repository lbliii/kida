"""Expression-tree simplification for partial evaluation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Any

from kida.compiler import partial_eval_constants as _constants
from kida.nodes import (
    BinOp,
    BoolOp,
    Compare,
    Concat,
    CondExpr,
    Const,
    Dict,
    Expr,
    Filter,
    FuncCall,
    Getattr,
    Getitem,
    List,
    MarkSafe,
    Name,
    NullCoalesce,
    Pipeline,
    Tuple,
    UnaryOp,
)

_UNRESOLVED = _constants.UNRESOLVED


class ExpressionTransformMixin(ABC):
    """Partial-evaluator phase for recursively simplifying expressions."""

    __slots__ = ()

    @abstractmethod
    def _try_eval(self, expr: Expr, depth: int = 0) -> Any:
        """Evaluate an expression against the current static context."""

    def _transform_expr(self, expr: Expr) -> Expr:
        """Replace resolvable expressions and simplify their children."""
        match expr:
            case Const() | Name():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                return expr

            case Getattr():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_obj = self._transform_expr(expr.obj)
                if new_obj is expr.obj:
                    return expr
                return Getattr(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    obj=new_obj,
                    attr=expr.attr,
                )

            case Getitem():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_obj = self._transform_expr(expr.obj)
                new_key = self._transform_expr(expr.key)
                if new_obj is expr.obj and new_key is expr.key:
                    return expr
                return Getitem(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    obj=new_obj,
                    key=new_key,
                )

            case BinOp():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_left = self._transform_expr(expr.left)
                new_right = self._transform_expr(expr.right)
                if new_left is expr.left and new_right is expr.right:
                    return expr
                return BinOp(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    left=new_left,
                    op=expr.op,
                    right=new_right,
                )

            case NullCoalesce():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_left = self._transform_expr(expr.left)
                new_right = self._transform_expr(expr.right)
                if new_left is expr.left and new_right is expr.right:
                    return expr
                return NullCoalesce(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    left=new_left,
                    right=new_right,
                )

            case MarkSafe():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_inner = self._transform_expr(expr.value)
                if new_inner is expr.value:
                    return expr
                return MarkSafe(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=new_inner,
                )

            case Filter():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_value = self._transform_expr(expr.value)
                if new_value is expr.value:
                    return expr
                return replace(expr, value=new_value)

            case Pipeline():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_value = self._transform_expr(expr.value)
                if new_value is expr.value:
                    return expr
                return type(expr)(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=new_value,
                    steps=expr.steps,
                )

            case BoolOp():
                return self._transform_boolop(expr)

            case CondExpr():
                return self._transform_condexpr(expr)

            case UnaryOp():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_operand = self._transform_expr(expr.operand)
                if new_operand is expr.operand:
                    return expr
                return UnaryOp(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    op=expr.op,
                    operand=new_operand,
                )

            case Compare():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_left = self._transform_expr(expr.left)
                new_comparators = tuple(self._transform_expr(item) for item in expr.comparators)
                if new_left is expr.left and all(
                    new is old for new, old in zip(new_comparators, expr.comparators, strict=True)
                ):
                    return expr
                return Compare(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    left=new_left,
                    ops=expr.ops,
                    comparators=new_comparators,
                )

            case Concat():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_nodes = tuple(self._transform_expr(node) for node in expr.nodes)
                if all(new is old for new, old in zip(new_nodes, expr.nodes, strict=True)):
                    return expr
                return Concat(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    nodes=new_nodes,
                )

            case FuncCall():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_func = self._transform_expr(expr.func)
                new_args = tuple(self._transform_expr(arg) for arg in expr.args)
                new_kwargs = {
                    name: self._transform_expr(item) for name, item in expr.kwargs.items()
                }
                new_dyn_args = (
                    self._transform_expr(expr.dyn_args) if expr.dyn_args else expr.dyn_args
                )
                new_dyn_kwargs = (
                    self._transform_expr(expr.dyn_kwargs) if expr.dyn_kwargs else expr.dyn_kwargs
                )
                if (
                    new_func is expr.func
                    and all(new is old for new, old in zip(new_args, expr.args, strict=True))
                    and all(new_kwargs[name] is expr.kwargs[name] for name in expr.kwargs)
                    and new_dyn_args is expr.dyn_args
                    and new_dyn_kwargs is expr.dyn_kwargs
                ):
                    return expr
                return FuncCall(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    func=new_func,
                    args=new_args,
                    kwargs=new_kwargs,
                    dyn_args=new_dyn_args,
                    dyn_kwargs=new_dyn_kwargs,
                )

            case List():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_items = tuple(self._transform_expr(item) for item in expr.items)
                if all(new is old for new, old in zip(new_items, expr.items, strict=True)):
                    return expr
                return List(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    items=new_items,
                )

            case Tuple():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_items = tuple(self._transform_expr(item) for item in expr.items)
                if all(new is old for new, old in zip(new_items, expr.items, strict=True)):
                    return expr
                return Tuple(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    items=new_items,
                    ctx=expr.ctx,
                )

            case Dict():
                value = self._try_eval(expr)
                if value is not _UNRESOLVED:
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)
                new_keys = tuple(self._transform_expr(key) for key in expr.keys)
                new_values = tuple(self._transform_expr(item) for item in expr.values)
                if all(new is old for new, old in zip(new_keys, expr.keys, strict=True)) and all(
                    new is old for new, old in zip(new_values, expr.values, strict=True)
                ):
                    return expr
                return Dict(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    keys=new_keys,
                    values=new_values,
                )

            case _:
                return expr

    def _transform_boolop(self, expr: BoolOp) -> Expr:
        """Partially simplify a boolean operation with static operands."""
        value = self._try_eval(expr)
        if value is not _UNRESOLVED:
            return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=value)

        remaining: list[Expr] = []
        for value_node in expr.values:
            resolved = self._try_eval(value_node)
            if resolved is _UNRESOLVED:
                remaining.append(self._transform_expr(value_node))
                continue

            if expr.op == "and":
                if not resolved:
                    return Const(
                        lineno=expr.lineno,
                        col_offset=expr.col_offset,
                        value=resolved,
                    )
            elif resolved:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=resolved,
                )

        if not remaining:
            return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=resolved)
        if len(remaining) == 1:
            return remaining[0]
        if len(remaining) == len(expr.values):
            return expr
        return BoolOp(
            lineno=expr.lineno,
            col_offset=expr.col_offset,
            op=expr.op,
            values=tuple(remaining),
        )

    def _transform_condexpr(self, expr: CondExpr) -> Expr:
        """Collapse a conditional expression when its test resolves."""
        test_value = self._try_eval(expr.test)
        if test_value is _UNRESOLVED:
            return expr
        winner = expr.if_true if test_value else expr.if_false
        winner_value = self._try_eval(winner)
        if winner_value is not _UNRESOLVED:
            return Const(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                value=winner_value,
            )
        return self._transform_expr(winner)
