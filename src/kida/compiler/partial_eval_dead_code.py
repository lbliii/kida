"""Const-only dead-code elimination for parsed template ASTs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida.compiler import partial_eval_constants as _constants
from kida.compiler.partial_eval_nodes import InlinedBody, flatten_inlined
from kida.nodes import (
    Block,
    Capture,
    Const,
    Data,
    Export,
    Expr,
    If,
    Let,
    Match,
    Name,
    Node,
    Output,
    Set,
    Template,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def body_has_scoping_nodes(nodes: Sequence[Node]) -> bool:
    """Return whether a body contains block-scoped assignment nodes."""
    for node in nodes:
        if isinstance(node, (Set, Let, Capture, Export)):
            return True
        if isinstance(node, Block) and body_has_scoping_nodes(node.body):
            return True
    return False


def _transform_if(node: If) -> Node | None:
    """Eliminate dead branches when the test is const-only resolvable."""
    test_val = _constants.try_eval_const_only(node.test)
    if test_val is _constants.UNRESOLVED:
        return node

    if test_val:
        if body_has_scoping_nodes(node.body):
            return node
        body = _transform_body(node.body)
        if len(body) == 1:
            return body[0]
        return InlinedBody(
            lineno=node.lineno,
            col_offset=node.col_offset,
            nodes=body,
        )

    for cond, branch_body in node.elif_:
        cond_val = _constants.try_eval_const_only(cond)
        if cond_val is _constants.UNRESOLVED:
            return node
        if cond_val:
            if body_has_scoping_nodes(branch_body):
                return node
            body = _transform_body(branch_body)
            if len(body) == 1:
                return body[0]
            return InlinedBody(
                lineno=node.lineno,
                col_offset=node.col_offset,
                nodes=body,
            )

    if node.else_:
        if body_has_scoping_nodes(node.else_):
            return node
        body = _transform_body(node.else_)
        if len(body) == 1:
            return body[0]
        return InlinedBody(
            lineno=node.lineno,
            col_offset=node.col_offset,
            nodes=body,
        )

    return None


def _transform_match(node: Match) -> Node | None:
    """Eliminate dead match/case branches for constant subjects."""
    if node.subject is None:
        return node
    subject_val = _constants.try_eval_const_only(node.subject)
    if subject_val is _constants.UNRESOLVED:
        new_cases: list[tuple[Expr, Expr | None, Sequence[Node]]] = []
        changed = False
        for pattern, guard, case_body in node.cases:
            new_body = _transform_body(case_body)
            if new_body is not case_body:
                changed = True
            new_cases.append((pattern, guard, new_body))
        if not changed:
            return node
        return Match(
            lineno=node.lineno,
            col_offset=node.col_offset,
            subject=node.subject,
            cases=tuple(new_cases),
        )

    for pattern, guard, case_body in node.cases:
        if isinstance(pattern, Name) and pattern.name == "_":
            if guard is not None:
                guard_val = _constants.try_eval_const_only(guard)
                if guard_val is _constants.UNRESOLVED:
                    return node
                if not guard_val:
                    continue
            if body_has_scoping_nodes(case_body):
                return node
            body = _transform_body(case_body)
            if len(body) == 1:
                return body[0]
            return InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=body)

        if isinstance(pattern, Const):
            if subject_val == pattern.value:
                if guard is not None:
                    guard_val = _constants.try_eval_const_only(guard)
                    if guard_val is _constants.UNRESOLVED:
                        return node
                    if not guard_val:
                        continue
                if body_has_scoping_nodes(case_body):
                    return node
                body = _transform_body(case_body)
                if len(body) == 1:
                    return body[0]
                return InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=body)
            continue

        return node

    return None


def _transform_body(body: Sequence[Node]) -> Sequence[Node]:
    """Eliminate dead nodes and flatten immediate branch replacements."""
    result: list[Node] = []
    changed = False

    for node in body:
        match node:
            case If():
                transformed = _transform_if(node)
                if transformed is None:
                    changed = True
                    continue
                if isinstance(transformed, InlinedBody):
                    changed = True
                    result.extend(transformed.nodes)
                else:
                    result.append(transformed)
            case Match():
                transformed = _transform_match(node)
                if transformed is None:
                    changed = True
                    continue
                if isinstance(transformed, InlinedBody):
                    changed = True
                    result.extend(transformed.nodes)
                else:
                    if transformed is not node:
                        changed = True
                    result.append(transformed)
            case Block():
                new_block_body = _transform_body(node.body)
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
            case Output():
                value = _constants.try_eval_const_only(node.expr)
                if value is not _constants.UNRESOLVED:
                    string_value = "" if value is None else str(value)
                    if isinstance(value, (int, float, bool)) or not node.escape:
                        changed = True
                        if string_value:
                            result.append(
                                Data(
                                    lineno=node.lineno,
                                    col_offset=node.col_offset,
                                    value=string_value,
                                )
                            )
                    else:
                        result.append(node)
                else:
                    result.append(node)
            case _:
                result.append(node)

    if not changed:
        return body
    return tuple(result)


def eliminate_dead_code(template: Template) -> Template:
    """Remove branches whose conditions are provably constant.

    Runs without static context and preserves branch structure whenever
    inlining would change block-scoping behavior.
    """
    new_body = _transform_body(template.body)
    if new_body is template.body:
        return template
    result = Template(
        lineno=template.lineno,
        col_offset=template.col_offset,
        body=new_body,
        extends=template.extends,
        context_type=template.context_type,
    )
    return flatten_inlined(result)
