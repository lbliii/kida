"""Static for-loop unrolling for partial evaluation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from kida.compiler import partial_eval_constants as _constants
from kida.compiler.partial_eval_nodes import InlinedBody
from kida.nodes import Def, Expr, For, Name, Node, Tuple

if TYPE_CHECKING:
    from collections.abc import Sequence

MAX_UNROLL = 200


@dataclass(frozen=True, slots=True)
class LoopProperties:
    """Compile-time stand-in for runtime loop-context properties."""

    index0: int
    index: int
    first: bool
    last: bool
    length: int
    revindex: int
    revindex0: int


class LoopUnrollingMixin(ABC):
    """Partial-evaluator phase for statically known for-loops."""

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

    def _transform_for(self, node: For) -> Node | None:
        """Unroll a for-loop when its iterable is statically known."""
        iter_val = self._try_eval(node.iter)

        if iter_val is not _constants.UNRESOLVED and not node.recursive:
            unrolled = self._try_unroll_for(node, iter_val)
            if unrolled is not None:
                return unrolled

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

    def _try_unroll_for(self, node: For, iter_val: Any) -> Node | None:
        """Return statically expanded loop nodes when unrolling is safe."""
        try:
            items = list(iter_val)
        except _constants.PARTIAL_EVAL_EXCEPTIONS:
            return None

        if len(items) > MAX_UNROLL:
            return None

        if not items:
            if node.empty:
                body = self._transform_body(node.empty)
                if len(body) == 1:
                    return body[0]
                return InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=body)
            return InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=())

        target = node.target
        if isinstance(target, Name):
            target_names: tuple[str, ...] = (target.name,)
        elif isinstance(target, Tuple):
            names = []
            for item in target.items:
                if not isinstance(item, Name):
                    return None
                names.append(item.name)
            target_names = tuple(names)
        else:
            return None

        total_items = len(items)
        all_nodes: list[Node] = []

        for idx, item in enumerate(items):
            if node.test is not None:
                sub_ctx = self._build_iter_context(target_names, item)
                sub_eval = self._make_sub_evaluator(sub_ctx)
                test_val = sub_eval._try_eval(node.test)
                if test_val is _constants.UNRESOLVED:
                    return None
                if not test_val:
                    continue

            iter_ctx = self._build_iter_context(target_names, item)
            iter_ctx["loop"] = LoopProperties(
                index0=idx,
                index=idx + 1,
                first=idx == 0,
                last=idx == total_items - 1,
                length=total_items,
                revindex=total_items - idx,
                revindex0=total_items - idx - 1,
            )

            sub_eval = self._make_sub_evaluator(iter_ctx)
            sub_eval._defs = dict(self._defs)
            transformed = sub_eval._transform_body(node.body)
            all_nodes.extend(transformed)

        if len(all_nodes) == 1:
            return all_nodes[0]
        return InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=tuple(all_nodes))

    def _build_iter_context(self, target_names: tuple[str, ...], item: Any) -> dict[str, Any]:
        """Map loop target names to one statically known item."""
        ctx = dict(self._ctx)
        if len(target_names) == 1:
            ctx[target_names[0]] = item
        else:
            try:
                values = list(item)
            except _constants.PARTIAL_EVAL_EXCEPTIONS:
                return ctx
            ctx.update(dict(zip(target_names, values, strict=False)))
        return ctx
