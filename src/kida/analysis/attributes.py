"""Static extraction of literal HTML attributes from template data nodes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, final

from kida.nodes import Data, Node, Raw

if TYPE_CHECKING:
    from collections.abc import Iterable

_TAG_RE = re.compile(r"<\s*(?P<tag>[A-Za-z][\w:-]*)(?P<attrs>[^>]*)>")
_ATTR_RE = re.compile(
    r"""(?P<name>[:A-Za-z_][\w:.-]*)"""
    r"""(?:\s*=\s*(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>[^\s"'=<>`]+)))?"""
)


@final
@dataclass(frozen=True, slots=True)
class LiteralAttribute:
    """Literal HTML attribute found in static template text."""

    name: str
    value: str | None
    tag: str
    template_name: str | None = None
    lineno: int | None = None
    col_offset: int | None = None


def _line_col(base_line: int, base_col: int, text: str, offset: int) -> tuple[int, int]:
    """Return 1-based line and 0-based column for an offset in a data node."""
    before = text[:offset]
    line_delta = before.count("\n")
    if line_delta == 0:
        return base_line, base_col + offset
    return base_line + line_delta, len(before.rsplit("\n", 1)[-1])


def _matches(name: str, names: set[str] | None, prefixes: tuple[str, ...]) -> bool:
    if names is not None and name not in names:
        return False
    return not (prefixes and not name.startswith(prefixes))


def _walk(node: Node) -> Iterable[Node]:
    yield node
    for child in node.iter_child_nodes():
        yield from _walk(child)


def extract_literal_attributes(
    template_or_ast: Any,
    *,
    names: Iterable[str] | None = None,
    prefixes: Iterable[str] | None = None,
) -> list[LiteralAttribute]:
    """Extract literal HTML attributes from static template text.

    Dynamic attributes built through expressions, filters, or helpers are not
    inferred. This helper intentionally reports only facts visible in raw
    template text so framework adapters can layer their own semantics on top.
    """
    ast = getattr(template_or_ast, "_optimized_ast", template_or_ast)
    if ast is None:
        return []
    template_name = getattr(template_or_ast, "name", None)
    name_filter = set(names) if names is not None else None
    prefix_filter = tuple(prefixes or ())

    found: list[LiteralAttribute] = []
    for node in _walk(ast):
        if not isinstance(node, (Data, Raw)):
            continue
        for tag_match in _TAG_RE.finditer(node.value):
            tag = tag_match.group("tag")
            attrs = tag_match.group("attrs")
            attr_base = tag_match.start("attrs")
            for attr_match in _ATTR_RE.finditer(attrs):
                name = attr_match.group("name")
                if name == "/" or not _matches(name, name_filter, prefix_filter):
                    continue
                value = (
                    attr_match.group("dq")
                    if attr_match.group("dq") is not None
                    else attr_match.group("sq")
                    if attr_match.group("sq") is not None
                    else attr_match.group("bare")
                )
                lineno, col_offset = _line_col(
                    node.lineno,
                    node.col_offset,
                    node.value,
                    attr_base + attr_match.start("name"),
                )
                found.append(
                    LiteralAttribute(
                        name=name,
                        value=value,
                        tag=tag,
                        template_name=template_name,
                        lineno=lineno,
                        col_offset=col_offset,
                    )
                )
    return found
