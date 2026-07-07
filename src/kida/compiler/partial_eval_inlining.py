"""Small component call inlining for partial evaluation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Self

from kida.compiler import partial_eval_constants as _constants
from kida.compiler.partial_eval_dead_code import body_has_scoping_nodes
from kida.compiler.partial_eval_nodes import InlinedBody
from kida.nodes import (
    Block,
    CallBlock,
    Data,
    Def,
    Expr,
    For,
    FuncCall,
    If,
    Name,
    Node,
    Slot,
    SlotBlock,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

MAX_INLINE_NODES = 20


class ComponentInliningMixin(ABC):
    """Partial-evaluator phase for small statically bound component calls."""

    __slots__ = ()

    _ctx: dict[str, Any]
    _defs: dict[str, Def]

    @abstractmethod
    def _try_eval(self, expr: Expr, depth: int = 0) -> Any:
        """Evaluate an expression against the current static context."""

    @abstractmethod
    def _transform_body(self, body: Sequence[Node]) -> Sequence[Node]:
        """Transform a sequence of template nodes."""

    @abstractmethod
    def _make_sub_evaluator(self, ctx: dict[str, Any]) -> Self:
        """Create an evaluator that shares this evaluator's configuration."""

    def _try_inline_call(self, node: CallBlock) -> Node | None:
        """Expand a small, slot-free component call when all args resolve."""
        call = node.call
        if not isinstance(call, FuncCall) or not isinstance(call.func, Name):
            return None

        defn = self._defs.get(call.func.name)
        if defn is None:
            return None

        if self._count_nodes(defn.body) > self._MAX_INLINE_NODES:
            return None
        if self._has_slot(defn.body):
            return None
        if body_has_scoping_nodes(defn.body):
            return None

        if any(not self._slot_body_is_empty(body) for body in node.slots.values()):
            return None
        if defn.vararg or defn.kwarg:
            return None

        param_names = [param.name for param in defn.params]
        arg_values: dict[str, Any] = {}

        all_args = list(call.args) + list(node.args)
        for index, arg_expr in enumerate(all_args):
            if index >= len(param_names):
                return None
            value = self._try_eval(arg_expr)
            if value is _constants.UNRESOLVED:
                return None
            arg_values[param_names[index]] = value

        for name, value_expr in call.kwargs.items():
            if name in arg_values:
                return None
            value = self._try_eval(value_expr)
            if value is _constants.UNRESOLVED:
                return None
            arg_values[name] = value

        required_count = len(param_names) - len(defn.defaults)
        for index, param_name in enumerate(param_names):
            if param_name in arg_values:
                continue
            default_index = index - required_count
            if default_index < 0:
                return None
            value = self._try_eval(defn.defaults[default_index])
            if value is _constants.UNRESOLVED:
                return None
            arg_values[param_name] = value

        sub_eval = self._make_sub_evaluator({**self._ctx, **arg_values})
        sub_eval._defs = dict(self._defs)
        inlined_body = sub_eval._transform_body(defn.body)
        if len(inlined_body) == 1:
            return inlined_body[0]
        return InlinedBody(
            lineno=node.lineno,
            col_offset=node.col_offset,
            nodes=inlined_body,
        )

    _MAX_INLINE_NODES = MAX_INLINE_NODES

    @staticmethod
    def _slot_body_is_empty(body: Sequence[Node]) -> bool:
        """Return whether a provided slot contains only whitespace data."""
        return all(isinstance(child, Data) and not child.value.strip() for child in body)

    @staticmethod
    def _count_nodes(body: Sequence[Node]) -> int:
        """Count nodes for the component inlining size guard."""
        return len(body)

    @staticmethod
    def _has_slot(body: Sequence[Node]) -> bool:
        """Return whether a component body recursively declares a slot."""
        for node in body:
            if isinstance(node, Slot):
                return True
            if isinstance(node, (Block, If, For)):
                if ComponentInliningMixin._has_slot(node.body):
                    return True
                if isinstance(node, If):
                    for _, branch_body in node.elif_:
                        if ComponentInliningMixin._has_slot(branch_body):
                            return True
                    if node.else_ and ComponentInliningMixin._has_slot(node.else_):
                        return True
                if (
                    isinstance(node, For)
                    and node.empty
                    and ComponentInliningMixin._has_slot(node.empty)
                ):
                    return True
            if isinstance(node, SlotBlock) and ComponentInliningMixin._has_slot(node.body):
                return True
        return False
