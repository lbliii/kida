"""Template-structure validation and block/region discovery for compilation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from kida.exceptions import ErrorCode, TemplateSyntaxError
from kida.nodes import (
    AsyncFor,
    Block,
    CallBlock,
    Capture,
    Data,
    Def,
    Export,
    For,
    FromImport,
    If,
    Import,
    Let,
    ListComp,
    Match,
    Name,
    Region,
    Set,
    Slot,
    SlotBlock,
    While,
)
from kida.nodes.structure import With, WithConditional

if TYPE_CHECKING:
    from kida.nodes import Node

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _raise_invalid_identifier(
    kind: str,
    value: str,
    *,
    lineno: int,
    template_name: str | None,
    filename: str | None,
) -> None:
    err = TemplateSyntaxError(
        f"Invalid {kind} name '{value}': must be identifier-like (e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
        lineno=lineno,
        name=template_name,
        filename=filename,
    )
    err.code = ErrorCode.INVALID_IDENTIFIER
    raise err


def _raise_duplicate(
    name: str,
    *,
    lineno: int,
    template_name: str | None,
    filename: str | None,
) -> None:
    err = TemplateSyntaxError(
        f"Duplicate block/region name '{name}'",
        lineno=lineno,
        name=template_name,
        filename=filename,
    )
    err.code = ErrorCode.INVALID_IDENTIFIER
    raise err


def collect_template_blocks(
    nodes: Sequence[Node],
    *,
    template_name: str | None,
    filename: str | None,
) -> dict[str, Block | Region]:
    """Validate identifiers and collect all compile-time block/region owners."""
    blocks: dict[str, Block | Region] = {}

    def collect(body_nodes: Sequence[Node]) -> None:
        for node in body_nodes:
            if isinstance(node, Block):
                if not _IDENTIFIER_RE.match(node.name):
                    _raise_invalid_identifier(
                        "block",
                        node.name,
                        lineno=node.lineno,
                        template_name=template_name,
                        filename=filename,
                    )
                if node.name in blocks and isinstance(blocks[node.name], Region):
                    _raise_duplicate(
                        node.name,
                        lineno=node.lineno,
                        template_name=template_name,
                        filename=filename,
                    )
                blocks[node.name] = node
                collect(node.body)
            elif isinstance(node, Def):
                if not _IDENTIFIER_RE.match(node.name):
                    _raise_invalid_identifier(
                        "def",
                        node.name,
                        lineno=node.lineno,
                        template_name=template_name,
                        filename=filename,
                    )
                collect(node.body)
            elif isinstance(node, Region):
                if not _IDENTIFIER_RE.match(node.name):
                    _raise_invalid_identifier(
                        "region",
                        node.name,
                        lineno=node.lineno,
                        template_name=template_name,
                        filename=filename,
                    )
                if node.name in blocks:
                    _raise_duplicate(
                        node.name,
                        lineno=node.lineno,
                        template_name=template_name,
                        filename=filename,
                    )
                blocks[node.name] = node
                collect(node.body)
            elif isinstance(node, CallBlock):
                for slot_name in node.slots:
                    if slot_name != "default" and not _IDENTIFIER_RE.match(slot_name):
                        _raise_invalid_identifier(
                            "slot",
                            slot_name,
                            lineno=node.lineno,
                            template_name=template_name,
                            filename=filename,
                        )
                for slot_body in node.slots.values():
                    collect(slot_body)
            elif isinstance(node, SlotBlock):
                if node.name != "default" and not _IDENTIFIER_RE.match(node.name):
                    _raise_invalid_identifier(
                        "slot",
                        node.name,
                        lineno=node.lineno,
                        template_name=template_name,
                        filename=filename,
                    )
                collect(node.body)
            elif isinstance(node, Slot):
                if node.name != "default" and not _IDENTIFIER_RE.match(node.name):
                    _raise_invalid_identifier(
                        "slot",
                        node.name,
                        lineno=node.lineno,
                        template_name=template_name,
                        filename=filename,
                    )
            elif hasattr(node, "body"):
                nested_body = node.body
                if isinstance(nested_body, Sequence):
                    collect(cast("Sequence[Node]", nested_body))
                else_body = getattr(node, "else_", None)
                if isinstance(else_body, Sequence):
                    collect(cast("Sequence[Node]", else_body))
                empty_body = getattr(node, "empty", None)
                if isinstance(empty_body, Sequence):
                    collect(cast("Sequence[Node]", empty_body))
                elif_body = getattr(node, "elif_", None)
                if elif_body:
                    for _, branch_body in elif_body:
                        collect(branch_body)

    collect(nodes)
    return blocks


def has_unconditional_expressions(body: Sequence[Any]) -> bool:
    """Return whether top-level nodes can produce unconditional name refs."""
    skip = (
        For,
        AsyncFor,
        If,
        While,
        Match,
        Set,
        Let,
        Export,
        Capture,
        With,
        WithConditional,
        Import,
        FromImport,
        Def,
        Block,
        Data,
    )
    return any(not isinstance(node, skip) for node in body)


def collect_variable_references(nodes: Any) -> tuple[dict[str, int], set[str]]:
    """Collect unconditional name-reference counts and mutations from Kida AST."""
    ref_counts: dict[str, int] = {}
    mutated: set[str] = set()

    def collect_target_names(target: Any) -> None:
        if isinstance(target, Name):
            mutated.add(target.name)
        elif hasattr(target, "items"):
            for item in target.items:
                collect_target_names(item)

    def walk(node: Any, *, count_refs: bool = True) -> None:
        if node is None:
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item, count_refs=count_refs)
            return
        if isinstance(node, dict):
            for value in node.values():
                walk(value, count_refs=count_refs)
            return

        if isinstance(node, Name) and node.ctx == "load":
            if count_refs:
                ref_counts[node.name] = ref_counts.get(node.name, 0) + 1
            return

        if isinstance(node, Set):
            if isinstance(node.target, Name):
                mutated.add(node.target.name)
            walk(node.value, count_refs=count_refs)
            return
        if isinstance(node, Let):
            if isinstance(node.name, Name):
                mutated.add(node.name.name)
            walk(node.value, count_refs=count_refs)
            return
        if isinstance(node, Export):
            if isinstance(node.name, Name):
                mutated.add(node.name.name)
            walk(node.value, count_refs=count_refs)
            return
        if isinstance(node, Capture):
            mutated.add(node.name)
            walk(node.body, count_refs=False)
            return

        if isinstance(node, ListComp):
            collect_target_names(node.target)
            walk(node.iter, count_refs=count_refs)
            walk(node.elt, count_refs=False)
            for if_expr in node.ifs:
                walk(if_expr, count_refs=False)
            return

        if isinstance(node, (For, AsyncFor)):
            collect_target_names(node.target)
            mutated.add("loop")
            walk(node.iter, count_refs=count_refs)
            walk(node.body, count_refs=False)
            walk(node.empty, count_refs=False)
            return

        if isinstance(node, With):
            for target_name, expr in node.targets:
                mutated.add(target_name)
                walk(expr, count_refs=count_refs)
            walk(node.body, count_refs=False)
            return
        if isinstance(node, WithConditional):
            if isinstance(node.target, Name):
                mutated.add(node.target.name)
            walk(node.expr, count_refs=count_refs)
            walk(node.body, count_refs=False)
            if node.empty:
                walk(node.empty, count_refs=False)
            return

        if isinstance(node, Import):
            mutated.add(node.target)
            walk(node.template, count_refs=count_refs)
            return
        if isinstance(node, FromImport):
            for name, alias in node.names:
                mutated.add(alias or name)
            walk(node.template, count_refs=count_refs)
            return

        if isinstance(node, If):
            walk(node.test, count_refs=count_refs)
            walk(node.body, count_refs=False)
            for elif_test, elif_body in node.elif_:
                walk(elif_test, count_refs=False)
                walk(elif_body, count_refs=False)
            if node.else_:
                walk(node.else_, count_refs=False)
            return
        if isinstance(node, While):
            walk(node.test, count_refs=count_refs)
            walk(node.body, count_refs=False)
            return

        if isinstance(node, Match):
            if node.subject is not None:
                walk(node.subject, count_refs=count_refs)
            for pattern, guard, case_body in node.cases:
                collect_target_names(pattern)
                if guard is not None:
                    walk(guard, count_refs=False)
                walk(case_body, count_refs=False)
            return

        if isinstance(node, CallBlock):
            walk(node.call, count_refs=count_refs)
            for slot_body in node.slots.values():
                walk(slot_body, count_refs=False)
            return

        if isinstance(node, Def):
            mutated.add(node.name)
            return
        if isinstance(node, Block):
            return

        if not hasattr(node, "__dataclass_fields__"):
            return
        for field_name in node.__dataclass_fields__:
            child = getattr(node, field_name, None)
            if child is not None:
                walk(child, count_refs=count_refs)

    walk(nodes)
    return ref_counts, mutated


def analyze_cacheable_names(
    body_nodes: Sequence[Any],
    *,
    local_names: set[str],
) -> set[str]:
    """Return names safe and profitable to cache as compiler locals."""
    if not has_unconditional_expressions(body_nodes):
        return set()
    ref_counts, mutated = collect_variable_references(body_nodes)
    return {
        name
        for name, count in ref_counts.items()
        if count >= 2 and name not in mutated and name not in local_names
    }
