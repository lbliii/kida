"""Constant-expression primitives shared by partial-evaluation phases.

This module owns the literal-only evaluator used by dead-code elimination and
the sentinel/error policy used by the static-context evaluator. Keeping these
primitives separate makes the phase boundary explicit without changing the
public ``partial_evaluate()`` or ``eliminate_dead_code()`` entrypoints.
"""

from __future__ import annotations

from typing import Any

from kida.nodes import BinOp, BoolOp, Compare, CondExpr, Const, Expr, UnaryOp

# Distinct from None, which is a valid compile-time result.
UNRESOLVED = object()

# Expected failures fall back to runtime evaluation. Process-control exceptions
# such as KeyboardInterrupt and SystemExit must continue to propagate.
PARTIAL_EVAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TypeError,
    KeyError,
    IndexError,
    AttributeError,
    ValueError,
    OverflowError,
    ZeroDivisionError,
)


def compare_op(op: str, left: Any, right: Any) -> bool:
    """Evaluate a comparison operator."""
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "in":
        return left in right
    if op == "not in":
        return left not in right
    if op == "is":
        return left is right
    if op == "is not":
        return left is not right
    msg = f"Unknown comparison operator: {op}"
    raise ValueError(msg)


def try_eval_const_only(expr: Expr) -> Any:
    """Evaluate an expression using only literals and constant operators.

    Name, attribute, and item lookups intentionally remain unresolved because
    they require a static context. Dead-code elimination uses this narrower
    evaluator even when no static context is configured.
    """
    match expr:
        case Const():
            return expr.value

        case BinOp():
            left = try_eval_const_only(expr.left)
            right = try_eval_const_only(expr.right)
            if left is UNRESOLVED or right is UNRESOLVED:
                return UNRESOLVED
            try:
                if expr.op == "+":
                    return left + right
                if expr.op == "-":
                    return left - right
                if expr.op == "*":
                    return left * right
                if expr.op == "/":
                    return left / right
                if expr.op == "//":
                    return left // right
                if expr.op == "%":
                    return left % right
                if expr.op == "**":
                    return left**right
                if expr.op == "~":
                    # Compile-time operands are constants, never Markup.
                    return str(left) + str(right)
            except PARTIAL_EVAL_EXCEPTIONS:
                return UNRESOLVED
            return UNRESOLVED

        case UnaryOp():
            operand = try_eval_const_only(expr.operand)
            if operand is UNRESOLVED:
                return UNRESOLVED
            try:
                if expr.op == "-":
                    return -operand
                if expr.op == "+":
                    return +operand
                if expr.op == "not":
                    return not operand
            except PARTIAL_EVAL_EXCEPTIONS:
                return UNRESOLVED
            return UNRESOLVED

        case Compare():
            left = try_eval_const_only(expr.left)
            if left is UNRESOLVED:
                return UNRESOLVED
            for op, comp_node in zip(expr.ops, expr.comparators, strict=True):
                right = try_eval_const_only(comp_node)
                if right is UNRESOLVED:
                    return UNRESOLVED
                try:
                    result = compare_op(op, left, right)
                except PARTIAL_EVAL_EXCEPTIONS:
                    return UNRESOLVED
                if not result:
                    return False
                left = right
            return True

        case BoolOp():
            if expr.op == "and":
                for val_node in expr.values:
                    val = try_eval_const_only(val_node)
                    if val is UNRESOLVED:
                        return UNRESOLVED
                    if not val:
                        return val
                return val
            for val_node in expr.values:
                val = try_eval_const_only(val_node)
                if val is UNRESOLVED:
                    return UNRESOLVED
                if val:
                    return val
            return val

        case CondExpr():
            test = try_eval_const_only(expr.test)
            if test is UNRESOLVED:
                return UNRESOLVED
            return try_eval_const_only(expr.if_true if test else expr.if_false)

        case _:
            return UNRESOLVED
