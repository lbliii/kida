"""Focused contracts for the constant-expression partial-eval phase."""

from __future__ import annotations

import pytest

from kida.compiler.partial_eval_constants import UNRESOLVED, compare_op, try_eval_const_only
from kida.nodes import BinOp, BoolOp, Compare, CondExpr, Const, Name, UnaryOp


def _const(value: object) -> Const:
    return Const(lineno=1, col_offset=0, value=value)


def test_nested_constant_expression_is_evaluated() -> None:
    expression = Compare(
        lineno=1,
        col_offset=0,
        left=BinOp(
            lineno=1,
            col_offset=0,
            op="+",
            left=_const(1),
            right=_const(1),
        ),
        ops=("==",),
        comparators=(_const(2),),
    )

    assert try_eval_const_only(expression) is True


def test_dynamic_name_remains_unresolved() -> None:
    expression = Name(lineno=1, col_offset=0, name="request_value")

    assert try_eval_const_only(expression) is UNRESOLVED


def test_expected_operator_failure_remains_unresolved() -> None:
    expression = BinOp(
        lineno=1,
        col_offset=0,
        op="/",
        left=_const(1),
        right=_const(0),
    )

    assert try_eval_const_only(expression) is UNRESOLVED


def test_boolean_short_circuit_does_not_touch_dynamic_operand() -> None:
    expression = BoolOp(
        lineno=1,
        col_offset=0,
        op="and",
        values=(_const(False), Name(lineno=1, col_offset=0, name="dynamic")),
    )

    assert try_eval_const_only(expression) is False


def test_conditional_expression_uses_constant_winner() -> None:
    expression = CondExpr(
        lineno=1,
        col_offset=0,
        test=UnaryOp(lineno=1, col_offset=0, op="not", operand=_const(False)),
        if_true=_const("yes"),
        if_false=_const("no"),
    )

    assert try_eval_const_only(expression) == "yes"


def test_unknown_comparison_operator_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown comparison operator"):
        compare_op("contains", 1, 2)


def test_process_control_exceptions_are_not_swallowed() -> None:
    class InterruptingValue:
        def __add__(self, other: object) -> object:
            raise KeyboardInterrupt

    expression = BinOp(
        lineno=1,
        col_offset=0,
        op="+",
        left=_const(InterruptingValue()),
        right=_const(1),
    )

    with pytest.raises(KeyboardInterrupt):
        try_eval_const_only(expression)
