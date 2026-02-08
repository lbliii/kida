"""Compile-time partial evaluation of template AST.

Transforms a Kida AST by evaluating expressions whose values can be
determined from a static context (values known at compile time, not
at render time).  This replaces dynamic lookups with constant data
nodes, enabling more aggressive f-string coalescing and producing
templates where static regions are literal strings in bytecode.

Example:
    Given static_context = {"site": Site(title="My Blog")}:

    Before:  Output(expr=Getattr(Name("site"), "title"))
    After:   Data(value="My Blog")

The evaluator is conservative: if any sub-expression cannot be
resolved, the entire expression is left untouched.  This guarantees
that partial evaluation never changes observable behavior.

Integration:
    Called by ``Environment._compile()`` between parsing and compilation.
    The partially-evaluated AST is then compiled normally by the Compiler,
    which sees more Data/Const nodes and produces better coalesced output.

"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from kida.nodes import (
    BinOp,
    Block,
    BoolOp,
    Compare,
    Concat,
    CondExpr,
    Const,
    Data,
    Expr,
    For,
    Getattr,
    Getitem,
    If,
    Name,
    Node,
    Output,
    Template,
    UnaryOp,
)

# Sentinel for "evaluation failed" — distinct from None (which is a valid result)
_UNRESOLVED = object()


class PartialEvaluator:
    """Evaluate static expressions in a Kida AST at compile time.

    Walks the template AST and replaces expressions that can be fully
    resolved from the static context with their computed values.

    Args:
        static_context: Values known at compile time (e.g., site config,
            navigation data).  Keys are top-level variable names.
        escape_func: HTML escape function for Output nodes.  When None,
            static Output nodes are replaced with unescaped string values.
        pure_filters: Filter names that are safe to evaluate at compile
            time (no side effects, deterministic).

    """

    __slots__ = ("_ctx", "_escape", "_pure_filters")

    def __init__(
        self,
        static_context: dict[str, Any],
        *,
        escape_func: Any | None = None,
        pure_filters: frozenset[str] = frozenset(),
    ) -> None:
        self._ctx = static_context
        self._escape = escape_func
        self._pure_filters = pure_filters

    def evaluate(self, template: Template) -> Template:
        """Transform a template AST by evaluating static expressions.

        Returns a new Template node with static parts replaced by
        constants.  The original template is not modified.

        """
        new_body = self._transform_body(template.body)
        if new_body is template.body:
            return template
        return Template(
            lineno=template.lineno,
            col_offset=template.col_offset,
            body=new_body,
            extends=template.extends,
            context_type=template.context_type,
        )

    # ------------------------------------------------------------------
    # Expression evaluation (try to compute a value)
    # ------------------------------------------------------------------

    def _try_eval(self, expr: Expr) -> Any:
        """Try to evaluate an expression against the static context.

        Returns the computed value on success, or ``_UNRESOLVED`` if the
        expression depends on runtime values.

        """
        if isinstance(expr, Const):
            return expr.value

        if isinstance(expr, Name):
            if expr.name in self._ctx:
                return self._ctx[expr.name]
            return _UNRESOLVED

        if isinstance(expr, Getattr):
            obj = self._try_eval(expr.obj)
            if obj is _UNRESOLVED:
                return _UNRESOLVED
            try:
                # Support both object attributes and dict-style access
                if isinstance(obj, Mapping):
                    return obj[expr.attr]
                return getattr(obj, expr.attr)
            except (AttributeError, KeyError, TypeError):
                return _UNRESOLVED

        if isinstance(expr, Getitem):
            obj = self._try_eval(expr.obj)
            key = self._try_eval(expr.key)
            if obj is _UNRESOLVED or key is _UNRESOLVED:
                return _UNRESOLVED
            try:
                return obj[key]
            except (KeyError, IndexError, TypeError):
                return _UNRESOLVED

        if isinstance(expr, BinOp):
            left = self._try_eval(expr.left)
            right = self._try_eval(expr.right)
            if left is _UNRESOLVED or right is _UNRESOLVED:
                return _UNRESOLVED
            return self._eval_binop(expr.op, left, right)

        if isinstance(expr, UnaryOp):
            operand = self._try_eval(expr.operand)
            if operand is _UNRESOLVED:
                return _UNRESOLVED
            return self._eval_unaryop(expr.op, operand)

        if isinstance(expr, Compare):
            return self._eval_compare(expr)

        if isinstance(expr, BoolOp):
            return self._eval_boolop(expr)

        if isinstance(expr, CondExpr):
            test = self._try_eval(expr.test)
            if test is _UNRESOLVED:
                return _UNRESOLVED
            return self._try_eval(expr.if_true if test else expr.if_false)

        if isinstance(expr, Concat):
            parts = []
            for node in expr.nodes:
                val = self._try_eval(node)
                if val is _UNRESOLVED:
                    return _UNRESOLVED
                parts.append(str(val))
            return "".join(parts)

        # Anything else (FuncCall, Filter, Pipeline, etc.) — not resolved
        return _UNRESOLVED

    @staticmethod
    def _eval_binop(op: str, left: Any, right: Any) -> Any:
        """Evaluate a binary operation with known operands."""
        try:
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                return left / right
            if op == "//":
                return left // right
            if op == "%":
                return left % right
            if op == "**":
                return left ** right
            if op == "~":
                return str(left) + str(right)
        except Exception:
            return _UNRESOLVED
        return _UNRESOLVED

    @staticmethod
    def _eval_unaryop(op: str, operand: Any) -> Any:
        """Evaluate a unary operation with a known operand."""
        try:
            if op == "-":
                return -operand
            if op == "+":
                return +operand
            if op == "not":
                return not operand
        except Exception:
            return _UNRESOLVED
        return _UNRESOLVED

    def _eval_compare(self, expr: Compare) -> Any:
        """Evaluate a comparison chain with known operands."""
        left = self._try_eval(expr.left)
        if left is _UNRESOLVED:
            return _UNRESOLVED

        for op, comp_node in zip(expr.ops, expr.comparators, strict=True):
            right = self._try_eval(comp_node)
            if right is _UNRESOLVED:
                return _UNRESOLVED
            try:
                result = _compare_op(op, left, right)
            except Exception:
                return _UNRESOLVED
            if not result:
                return False
            left = right
        return True

    def _eval_boolop(self, expr: BoolOp) -> Any:
        """Evaluate a boolean operation with short-circuit semantics."""
        if expr.op == "and":
            for val_node in expr.values:
                val = self._try_eval(val_node)
                if val is _UNRESOLVED:
                    return _UNRESOLVED
                if not val:
                    return val
            return val  # noqa: F821 – `val` is always assigned in the loop
        # "or"
        for val_node in expr.values:
            val = self._try_eval(val_node)
            if val is _UNRESOLVED:
                return _UNRESOLVED
            if val:
                return val
        return val  # noqa: F821

    # ------------------------------------------------------------------
    # AST transformation (structural rewriting)
    # ------------------------------------------------------------------

    def _transform_body(self, body: Sequence[Node]) -> Sequence[Node]:
        """Transform a sequence of nodes, merging adjacent Data nodes."""
        new_nodes: list[Node] = []
        changed = False

        for node in body:
            transformed = self._transform_node(node)
            if transformed is not node:
                changed = True
            if transformed is None:
                changed = True
                continue
            # Merge adjacent Data nodes
            if isinstance(transformed, Data) and new_nodes and isinstance(new_nodes[-1], Data):
                prev = new_nodes[-1]
                new_nodes[-1] = Data(
                    lineno=prev.lineno,
                    col_offset=prev.col_offset,
                    value=prev.value + transformed.value,
                )
                changed = True
            else:
                new_nodes.append(transformed)

        if not changed:
            return body
        return tuple(new_nodes)

    def _transform_node(self, node: Node) -> Node | None:
        """Transform a single AST node.

        Returns the transformed node, or None to remove it.

        """
        if isinstance(node, Output):
            return self._transform_output(node)

        if isinstance(node, If):
            return self._transform_if(node)

        if isinstance(node, For):
            return self._transform_for(node)

        if isinstance(node, Block):
            new_body = self._transform_body(node.body)
            if new_body is node.body:
                return node
            return Block(
                lineno=node.lineno,
                col_offset=node.col_offset,
                name=node.name,
                body=new_body,
                scoped=node.scoped,
                required=node.required,
            )

        # Data, Raw, and other nodes pass through unchanged
        return node

    def _transform_output(self, node: Output) -> Node:
        """Try to evaluate an Output node to a Data node."""
        value = self._try_eval(node.expr)
        if value is _UNRESOLVED:
            # Can't resolve — try to partially evaluate the expression
            new_expr = self._transform_expr(node.expr)
            if new_expr is node.expr:
                return node
            return Output(
                lineno=node.lineno,
                col_offset=node.col_offset,
                expr=new_expr,
                escape=node.escape,
            )

        # Fully resolved — replace with Data
        str_value = str(value) if value is not None else ""
        if node.escape and self._escape is not None:
            str_value = str(self._escape(str_value))
        return Data(
            lineno=node.lineno,
            col_offset=node.col_offset,
            value=str_value,
        )

    def _transform_if(self, node: If) -> Node | None:
        """Try to evaluate an If node's test at compile time."""
        test_val = self._try_eval(node.test)
        if test_val is _UNRESOLVED:
            # Can't resolve test — recurse into branches
            new_body = self._transform_body(node.body)
            new_elif = tuple(
                (cond, self._transform_body(body))
                for cond, body in node.elif_
            )
            new_else = self._transform_body(node.else_) if node.else_ else node.else_
            if (
                new_body is node.body
                and new_elif == node.elif_
                and new_else is node.else_
            ):
                return node
            return If(
                lineno=node.lineno,
                col_offset=node.col_offset,
                test=node.test,
                body=new_body,
                elif_=new_elif,
                else_=new_else,
            )

        # Test resolved — eliminate dead branches
        if test_val:
            # True branch wins — inline its body
            body = self._transform_body(node.body)
            if len(body) == 1:
                return body[0]
            # Wrap multiple nodes in a sentinel (return first for simplicity)
            # Actually, _transform_body returns them, and the parent will
            # handle the sequence.  Return a special marker.
            return _InlinedBody(
                lineno=node.lineno,
                col_offset=node.col_offset,
                nodes=body,
            )

        # False — check elif branches
        for cond, branch_body in node.elif_:
            cond_val = self._try_eval(cond)
            if cond_val is _UNRESOLVED:
                # Can't resolve this elif — give up on elimination
                return node
            if cond_val:
                body = self._transform_body(branch_body)
                if len(body) == 1:
                    return body[0]
                return _InlinedBody(
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    nodes=body,
                )

        # All branches false — use else or remove
        if node.else_:
            body = self._transform_body(node.else_)
            if len(body) == 1:
                return body[0]
            return _InlinedBody(
                lineno=node.lineno,
                col_offset=node.col_offset,
                nodes=body,
            )

        # No else — remove the node entirely
        return None

    def _transform_for(self, node: For) -> Node:
        """Recurse into For loop body."""
        new_body = self._transform_body(node.body)
        new_empty = self._transform_body(node.empty) if node.empty else node.empty
        if new_body is node.body and new_empty is node.empty:
            return node
        return For(
            lineno=node.lineno,
            col_offset=node.col_offset,
            target=node.target,
            iter=node.iter,
            body=new_body,
            empty=new_empty,
            recursive=node.recursive,
            test=node.test,
        )

    def _transform_expr(self, expr: Expr) -> Expr:
        """Try to partially evaluate an expression.

        If sub-expressions can be resolved, replace them with Const nodes.

        """
        if isinstance(expr, (Const, Name)):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            return expr

        if isinstance(expr, Getattr):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_obj = self._transform_expr(expr.obj)
            if new_obj is expr.obj:
                return expr
            return Getattr(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                obj=new_obj,
                attr=expr.attr,
            )

        if isinstance(expr, Getitem):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
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

        if isinstance(expr, BinOp):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            return expr

        return expr


from dataclasses import dataclass as _dataclass


@_dataclass(frozen=True, slots=True)
class _InlinedBody(Node):
    """Temporary node for inlined If branches.

    Holds multiple nodes that replace a single If node.  The parent's
    ``_transform_body`` flattens these into the body sequence.

    """

    nodes: Sequence[Node] = ()


def _compare_op(op: str, left: Any, right: Any) -> bool:
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
    msg = f"Unknown comparison operator: {op}"
    raise ValueError(msg)


def partial_evaluate(
    template: Template,
    static_context: dict[str, Any],
    *,
    escape_func: Any | None = None,
    pure_filters: frozenset[str] = frozenset(),
) -> Template:
    """Convenience function: partially evaluate a template AST.

    Args:
        template: Parsed template AST.
        static_context: Values known at compile time.
        escape_func: HTML escape function for static Output nodes.
        pure_filters: Filter names safe for compile-time evaluation.

    Returns:
        Transformed template AST with static expressions replaced.

    """
    if not static_context:
        return template

    evaluator = PartialEvaluator(
        static_context,
        escape_func=escape_func,
        pure_filters=pure_filters,
    )
    result = evaluator.evaluate(template)

    # Flatten any _InlinedBody nodes
    return _flatten_inlined(result)


def _flatten_inlined(template: Template) -> Template:
    """Flatten _InlinedBody nodes from branch elimination."""
    new_body = _flatten_body(template.body)
    if new_body is template.body:
        return template
    return Template(
        lineno=template.lineno,
        col_offset=template.col_offset,
        body=new_body,
        extends=template.extends,
        context_type=template.context_type,
    )


def _flatten_body(body: Sequence[Node]) -> Sequence[Node]:
    """Flatten any _InlinedBody nodes in a body sequence."""
    result: list[Node] = []
    changed = False
    for node in body:
        if isinstance(node, _InlinedBody):
            changed = True
            for inner in node.nodes:
                if isinstance(inner, _InlinedBody):
                    result.extend(inner.nodes)
                else:
                    result.append(inner)
        elif isinstance(node, Block):
            new_block_body = _flatten_body(node.body)
            if new_block_body is not node.body:
                changed = True
                result.append(Block(
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    name=node.name,
                    body=new_block_body,
                    scoped=node.scoped,
                    required=node.required,
                ))
            else:
                result.append(node)
        else:
            result.append(node)

    if not changed:
        return body
    return tuple(result)
