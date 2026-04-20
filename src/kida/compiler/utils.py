"""Compiler utilities for Kida.

Provides operator mapping utilities for AST generation. These are
module-level functions, not mixin methods — call sites import them
directly.
"""

from __future__ import annotations

import ast

_BINOPS: dict[str, ast.operator] = {
    "+": ast.Add(),
    "-": ast.Sub(),
    "*": ast.Mult(),
    "/": ast.Div(),
    "//": ast.FloorDiv(),
    "%": ast.Mod(),
    "**": ast.Pow(),
}

_UNARYOPS: dict[str, ast.unaryop] = {
    "-": ast.USub(),
    "+": ast.UAdd(),
    "not": ast.Not(),
}

_CMPOPS: dict[str, ast.cmpop] = {
    "==": ast.Eq(),
    "!=": ast.NotEq(),
    "<": ast.Lt(),
    "<=": ast.LtE(),
    ">": ast.Gt(),
    ">=": ast.GtE(),
    "in": ast.In(),
    "not in": ast.NotIn(),
    "is": ast.Is(),
    "is not": ast.IsNot(),
}


def get_binop(op: str) -> ast.operator:
    """Map binary operator string to AST operator. Raises KeyError on unknown."""
    try:
        return _BINOPS[op]
    except KeyError:
        raise KeyError(f"unknown binary operator: {op!r}") from None


def get_unaryop(op: str) -> ast.unaryop:
    """Map unary operator string to AST operator. Raises KeyError on unknown."""
    try:
        return _UNARYOPS[op]
    except KeyError:
        raise KeyError(f"unknown unary operator: {op!r}") from None


def get_cmpop(op: str) -> ast.cmpop:
    """Map comparison operator string to AST operator. Raises KeyError on unknown."""
    try:
        return _CMPOPS[op]
    except KeyError:
        raise KeyError(f"unknown comparison operator: {op!r}") from None
