"""Template-structure validation and block/region discovery for compilation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class JinjaSetReadFinding:
    """One proven Jinja ``if`` assignment read outside its Kida block."""

    name: str
    lineno: int
    suggestion: str
    shadow: bool = False


@dataclass(frozen=True, slots=True)
class _JinjaSetOrigin:
    name: str
    lineno: int
    suggestion: str
    shadow: bool
    identity: tuple[int, str]


@dataclass(frozen=True, slots=True)
class _OriginFlow:
    origin: _JinjaSetOrigin | None = None
    parents: tuple[_OriginFlow, ...] = ()


_KILLED_FLOW = _OriginFlow()
_OriginState = dict[str, _OriginFlow | None]


def _target_names(node: Node) -> tuple[str, ...]:
    from kida.nodes import Name, Tuple

    if isinstance(node, Name):
        return (node.name,)
    if isinstance(node, Tuple):
        return tuple(name for item in node.items for name in _target_names(item))
    return ()


def _read_names(node: Node) -> frozenset[str]:
    from kida.nodes import Name

    if isinstance(node, Name):
        return frozenset({node.name}) if node.ctx == "load" else frozenset()
    return frozenset(name for child in node.iter_child_nodes() for name in _read_names(child))


def collect_jinja_set_read_findings(nodes: Sequence[Node]) -> tuple[JinjaSetReadFinding, ...]:
    """Find proven Jinja ``if`` assignment flow that Kida block scope breaks."""
    from kida.nodes import AsyncFor, Block, Def, Export, For, If, Let, Region, Set

    findings: list[JinjaSetReadFinding] = []
    emitted: set[tuple[int, str]] = set()
    observed_read_flows: set[int] = set()
    observed_shadow_flows: set[int] = set()

    def emit(origin: _JinjaSetOrigin) -> None:
        if origin.identity in emitted:
            return
        emitted.add(origin.identity)
        findings.append(
            JinjaSetReadFinding(
                origin.name,
                origin.lineno,
                origin.suggestion,
                shadow=origin.shadow,
            )
        )

    def emit_flow(
        flow: _OriginFlow | None,
        *,
        shadow_only: bool,
    ) -> None:
        if flow is None:
            return
        visited = observed_shadow_flows if shadow_only else observed_read_flows
        stack = [flow]
        while stack:
            current = stack.pop()
            flow_id = id(current)
            if flow_id in visited:
                continue
            visited.add(flow_id)
            if current.origin is not None and (not shadow_only or current.origin.shadow):
                emit(current.origin)
            stack.extend(current.parents)

    def observe(reads: frozenset[str], state: _OriginState) -> None:
        for name in reads:
            emit_flow(state.get(name), shadow_only=False)

    def merge(branches: Sequence[_OriginState], base: _OriginState) -> _OriginState:
        merged: _OriginState = {}
        for name in {name for branch in branches for name in branch}:
            values = [branch[name] for branch in branches if name in branch]
            if any(value is None for value in values):
                merged[name] = None
                continue
            flows = [
                value
                for value in values
                if isinstance(value, _OriginFlow) and value is not _KILLED_FLOW
            ]
            if flows and len(flows) != len(values):
                base_flow = base.get(name)
                if base_flow is None or base_flow is not _KILLED_FLOW:
                    merged[name] = None
                    continue
            unique_flows = tuple({id(flow): flow for flow in flows}.values())
            if len(unique_flows) == 1:
                merged[name] = unique_flows[0]
            elif unique_flows:
                merged[name] = _OriginFlow(parents=unique_flows)
            elif values:
                merged[name] = _KILLED_FLOW
        return merged

    def analyze(
        body: Sequence[Node],
        state: _OriginState,
        bound: set[str],
        *,
        if_depth: int,
        loop_depth: int,
    ) -> tuple[_OriginState, set[str]]:
        for child in body:
            if isinstance(child, Set):
                observe(_read_names(child.value), state)
                for name in _target_names(child.target):
                    if if_depth:
                        if loop_depth:
                            suggestion = (
                                "Move the read into the same {% if %} branch or "
                                "restructure the loop-local state; {% let %} and "
                                "{% export %} would widen its scope."
                            )
                        elif name in bound:
                            suggestion = f"Use {{% export {name} = ... %}} to write to outer scope."
                        else:
                            suggestion = (
                                f"Use {{% let {name} = ... %}} to make the value template-wide."
                            )
                        origin = _JinjaSetOrigin(
                            name,
                            child.lineno,
                            suggestion,
                            name in bound and loop_depth == 0,
                            (id(child), name),
                        )
                        state[name] = _OriginFlow(origin=origin)
                    else:
                        state[name] = _KILLED_FLOW
                        bound.add(name)
                continue

            if isinstance(child, (Let, Export)):
                observe(_read_names(child.value), state)
                for name in _target_names(child.name):
                    state[name] = _KILLED_FLOW
                    bound.add(name)
                continue

            if isinstance(child, If):
                base_state = state
                observe(_read_names(child.test), state)
                for test, _branch in child.elif_:
                    observe(_read_names(test), state)
                branch_bodies = [child.body, *(branch for _test, branch in child.elif_)]
                branch_bodies.append(child.else_ or ())
                branch_results = [
                    analyze(
                        branch,
                        state.copy(),
                        bound.copy(),
                        if_depth=if_depth + 1,
                        loop_depth=loop_depth,
                    )
                    for branch in branch_bodies
                ]
                for branch_state, _branch_bound in branch_results:
                    for flow in branch_state.values():
                        emit_flow(flow, shadow_only=True)
                state = merge([result[0] for result in branch_results], base_state)
                bound = set.intersection(*(result[1] for result in branch_results))
                continue

            if isinstance(child, (For, AsyncFor)):
                observe(_read_names(child.iter), state)
                if child.test is not None:
                    observe(_read_names(child.test), state)
                loop_state = state.copy()
                loop_bound = bound.copy()
                for name in _target_names(child.target):
                    loop_state[name] = _KILLED_FLOW
                    loop_bound.add(name)
                analyze(
                    child.body,
                    loop_state,
                    loop_bound,
                    if_depth=0,
                    loop_depth=loop_depth + 1,
                )
                analyze(
                    child.empty,
                    state.copy(),
                    bound.copy(),
                    if_depth=0,
                    loop_depth=loop_depth,
                )
                continue

            if isinstance(child, (Block, Def, Region)):
                analyze(child.body, {}, set(), if_depth=0, loop_depth=0)
                continue

            if isinstance(child, With):
                for _target, value in child.targets:
                    observe(_read_names(value), state)
                with_bound = bound | {target for target, _value in child.targets}
                analyze(
                    child.body,
                    state.copy(),
                    with_bound,
                    if_depth=0,
                    loop_depth=loop_depth,
                )
                continue

            if isinstance(child, WithConditional):
                observe(_read_names(child.expr), state)
                with_state = state.copy()
                with_bound = bound.copy()
                for name in _target_names(child.target):
                    with_state[name] = _KILLED_FLOW
                    with_bound.add(name)
                analyze(
                    child.body,
                    with_state,
                    with_bound,
                    if_depth=0,
                    loop_depth=loop_depth,
                )
                analyze(
                    child.empty,
                    state.copy(),
                    bound.copy(),
                    if_depth=0,
                    loop_depth=loop_depth,
                )
                continue

            if hasattr(child, "body"):
                # Unsupported or dynamically scoped containers (while,
                # match, try, cache, capture, extension nodes, ...) are not
                # Jinja ``if`` proof. Stay silent rather than infer through
                # semantics this advisory does not model.
                continue

            observe(_read_names(child), state)

        return state, bound

    analyze(nodes, {}, set(), if_depth=0, loop_depth=0)
    findings.sort(key=lambda finding: (finding.lineno, finding.name))
    return tuple(findings)


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
