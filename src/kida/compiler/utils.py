"""Typed compiler helpers shared without expanding mixin contracts."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any, Final, cast

if TYPE_CHECKING:
    from kida.exceptions import ErrorCode, TemplateWarning

# Node types whose evaluation can raise at render time. Their generated code
# updates the render context before evaluation so diagnostics point at the
# originating template line.
LINE_TRACKED_NODE_TYPES: Final = frozenset(
    {
        "Output",
        "For",
        "AsyncFor",
        "If",
        "Match",
        "Set",
        "Let",
        "CallBlock",
        "Do",
        "WithConditional",
        "Include",
        "FromImport",
        "Import",
        "Embed",
    }
)

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


def fix_missing_locations_fast[T: ast.AST](node: T) -> T:
    """Fill missing Python AST locations while preserving the concrete AST type.

    This mirrors :func:`ast.fix_missing_locations`: each child inherits the
    current parent location unless it already carries its own value. Kida emits
    large generated ASTs during compile, so the iterative traversal avoids
    recursive ``ast.iter_fields()`` overhead on the compile hot path.
    """
    stack: list[tuple[ast.AST, int, int, int, int]] = [(node, 1, 0, 1, 0)]
    while stack:
        current, lineno, col_offset, end_lineno, end_col_offset = stack.pop()
        current_any = cast("Any", current)
        attrs = current._attributes
        if "lineno" in attrs:
            if not hasattr(current, "lineno"):
                current_any.lineno = lineno
            else:
                lineno = cast("int", current_any.lineno)
        if "end_lineno" in attrs:
            if getattr(current, "end_lineno", None) is None:
                current_any.end_lineno = end_lineno
            else:
                end_lineno = cast("int", current_any.end_lineno)
        if "col_offset" in attrs:
            if not hasattr(current, "col_offset"):
                current_any.col_offset = col_offset
            else:
                col_offset = cast("int", current_any.col_offset)
        if "end_col_offset" in attrs:
            if getattr(current, "end_col_offset", None) is None:
                current_any.end_col_offset = end_col_offset
            else:
                end_col_offset = cast("int", current_any.end_col_offset)

        for field_name in reversed(current._fields):
            field = getattr(current, field_name, None)
            if isinstance(field, ast.AST):
                stack.append((field, lineno, col_offset, end_lineno, end_col_offset))
            elif isinstance(field, list):
                stack.extend(
                    (item, lineno, col_offset, end_lineno, end_col_offset)
                    for item in reversed(field)
                    if isinstance(item, ast.AST)
                )
    return node


def make_line_marker(lineno: int) -> ast.Assign:
    """Build ``_rc.line = lineno`` for render-time error attribution."""
    return ast.Assign(
        targets=[
            ast.Attribute(
                value=ast.Name(id="_rc", ctx=ast.Load()),
                attr="line",
                ctx=ast.Store(),
            )
        ],
        value=ast.Constant(value=lineno),
    )


def make_template_warning(
    code: ErrorCode,
    message: str,
    *,
    template_name: str | None,
    lineno: int | None = None,
    suggestion: str | None = None,
) -> TemplateWarning:
    """Build an immutable compiler warning with template provenance."""
    from kida.exceptions import TemplateWarning

    return TemplateWarning(
        code=code,
        message=message,
        template_name=template_name,
        lineno=lineno,
        suggestion=suggestion,
    )


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
