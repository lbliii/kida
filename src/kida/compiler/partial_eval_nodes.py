"""Temporary node helpers shared by partial-evaluation transform phases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from kida.nodes import Block, CallBlock, Node, SlotBlock, Template

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
@dataclass(frozen=True, slots=True)
class InlinedBody(Node):
    """Temporary node for multiple nodes replacing one transform input."""

    nodes: Sequence[Node] = ()


def flatten_inlined(template: Template) -> Template:
    """Flatten temporary ``InlinedBody`` nodes from branch transforms."""
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
    """Flatten temporary nodes recursively through body-owning nodes."""
    result: list[Node] = []
    changed = False
    for node in body:
        if isinstance(node, InlinedBody):
            changed = True
            for inner in node.nodes:
                if isinstance(inner, InlinedBody):
                    result.extend(inner.nodes)
                else:
                    result.append(inner)
        elif isinstance(node, Block):
            new_block_body = _flatten_body(node.body)
            if new_block_body is not node.body:
                changed = True
                result.append(
                    Block(
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        name=node.name,
                        body=new_block_body,
                        scoped=node.scoped,
                        required=node.required,
                    )
                )
            else:
                result.append(node)
        elif isinstance(node, CallBlock):
            new_slots = {name: _flatten_body(slot) for name, slot in node.slots.items()}
            if any(new_slots[name] is not node.slots[name] for name in node.slots):
                changed = True
                result.append(
                    CallBlock(
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        call=node.call,
                        slots=new_slots,
                        args=node.args,
                    )
                )
            else:
                result.append(node)
        elif isinstance(node, SlotBlock):
            new_body = _flatten_body(node.body)
            if new_body is not node.body:
                changed = True
                result.append(
                    SlotBlock(
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        name=node.name,
                        body=new_body,
                    )
                )
            else:
                result.append(node)
        else:
            result.append(node)

    if not changed:
        return body
    return tuple(result)
