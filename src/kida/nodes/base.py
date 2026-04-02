"""Base node class for Kida AST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True, slots=True)
class Node:
    """Base class for all AST nodes.

    All nodes track their source location for error reporting.
    Nodes are immutable for thread-safety.

    """

    lineno: int
    col_offset: int

    def iter_child_nodes(self) -> Iterator[Node]:
        """Yield all direct child AST nodes.

        Uses ``__dataclass_fields__`` introspection so adding a node type
        requires zero changes to visitor/transformer code.
        """
        for field_name in self.__dataclass_fields__:
            if field_name in ("lineno", "col_offset"):
                continue
            value = getattr(self, field_name)
            if value is None:
                continue
            if isinstance(value, Node):
                yield value
            elif isinstance(value, (list, tuple)):
                yield from _iter_sequence(value)
            elif isinstance(value, dict):
                for v in value.values():
                    if isinstance(v, Node):
                        yield v
                    elif isinstance(v, (list, tuple)):
                        yield from _iter_sequence(v)


def _iter_sequence(seq: list | tuple) -> Iterator[Node]:
    """Yield Node instances from a (possibly nested) sequence."""
    for item in seq:
        if isinstance(item, Node):
            yield item
        elif isinstance(item, (list, tuple)):
            yield from _iter_sequence(item)
        elif isinstance(item, dict):
            for v in item.values():
                if isinstance(v, Node):
                    yield v
                elif isinstance(v, (list, tuple)):
                    yield from _iter_sequence(v)
