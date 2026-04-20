"""Tests for kida.compiler.stream_transform.

Covers the sync→stream AST transformation used to derive streaming block
variants from sync compilation output. Key invariants:
- ``_append(expr)`` Expr statements become ``yield expr``
- Other statements pass through unchanged
- Copy-on-write: unchanged subtrees are returned by identity (no mutation
  of the input AST), allowing the transform to be called repeatedly on
  the same input.
"""

from __future__ import annotations

import ast

from kida.compiler.stream_transform import sync_body_to_stream


def _parse_body(source: str) -> list[ast.stmt]:
    return ast.parse(source).body


def _is_yield_of(stmt: ast.stmt, expected_name: str) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Yield)
        and isinstance(stmt.value.value, ast.Name)
        and stmt.value.value.id == expected_name
    )


class TestSyncBodyToStream:
    def test_empty_body_returns_empty_list(self) -> None:
        assert sync_body_to_stream([]) == []

    def test_single_append_becomes_yield(self) -> None:
        body = _parse_body("_append(x)")

        result = sync_body_to_stream(body)

        assert len(result) == 1
        assert _is_yield_of(result[0], "x")

    def test_non_append_call_is_unchanged(self) -> None:
        body = _parse_body("other_func(x)")

        result = sync_body_to_stream(body)

        assert result[0] is body[0]  # identity — no copy

    def test_assignment_with_append_call_is_unchanged(self) -> None:
        # _append(y) embedded in an assignment is NOT an Expr statement,
        # so it must not be transformed.
        body = _parse_body("x = _append(y)")

        result = sync_body_to_stream(body)

        assert result[0] is body[0]

    def test_multi_arg_append_is_unchanged(self) -> None:
        # The transformer only matches single-argument _append calls.
        body = _parse_body("_append(x, y)")

        result = sync_body_to_stream(body)

        assert result[0] is body[0]

    def test_append_inside_if_is_transformed(self) -> None:
        body = _parse_body(
            """
if cond:
    _append(x)
else:
    _append(y)
"""
        )

        result = sync_body_to_stream(body)

        if_stmt = result[0]
        assert isinstance(if_stmt, ast.If)
        assert _is_yield_of(if_stmt.body[0], "x")
        assert _is_yield_of(if_stmt.orelse[0], "y")

    def test_append_inside_for_is_transformed(self) -> None:
        body = _parse_body(
            """
for item in items:
    _append(item)
"""
        )

        result = sync_body_to_stream(body)

        for_stmt = result[0]
        assert isinstance(for_stmt, ast.For)
        assert _is_yield_of(for_stmt.body[0], "item")

    def test_deeply_nested_append_is_transformed(self) -> None:
        body = _parse_body(
            """
for item in items:
    if item.active:
        for child in item.children:
            _append(child)
"""
        )

        result = sync_body_to_stream(body)

        outer_for = result[0]
        assert isinstance(outer_for, ast.For)
        if_stmt = outer_for.body[0]
        assert isinstance(if_stmt, ast.If)
        inner_for = if_stmt.body[0]
        assert isinstance(inner_for, ast.For)
        assert _is_yield_of(inner_for.body[0], "child")

    def test_mixed_statements_only_append_transformed(self) -> None:
        body = _parse_body(
            """
x = 1
_append(x)
log("done")
"""
        )

        result = sync_body_to_stream(body)

        assert len(result) == 3
        assert result[0] is body[0]  # assignment unchanged (identity)
        assert _is_yield_of(result[1], "x")
        assert result[2] is body[2]  # log() call unchanged (identity)


class TestCopyOnWrite:
    def test_input_ast_is_not_mutated(self) -> None:
        body = _parse_body(
            """
for item in items:
    _append(item)
"""
        )
        # Snapshot the input as a string so we can detect any mutation.
        before = ast.dump(body[0])

        sync_body_to_stream(body)

        after = ast.dump(body[0])
        assert before == after, "input AST was mutated by sync_body_to_stream"

    def test_unchanged_subtree_returned_by_identity(self) -> None:
        # An if-statement whose body has no _append calls should be
        # returned by identity (not even shallow-copied).
        body = _parse_body(
            """
if cond:
    log("hi")
""",
        )

        result = sync_body_to_stream(body)

        assert result[0] is body[0]

    def test_partial_change_only_copies_path(self) -> None:
        # If only the inner body changes, the outer If is shallow-copied
        # but its `test` and `orelse` should still share identity with
        # the originals.
        body = _parse_body(
            """
if cond:
    _append(x)
else:
    log("untouched")
"""
        )
        original_if = body[0]
        assert isinstance(original_if, ast.If)
        original_test = original_if.test
        original_orelse_stmt = original_if.orelse[0]

        result = sync_body_to_stream(body)

        new_if = result[0]
        assert isinstance(new_if, ast.If)
        # If was shallow-copied (body changed)…
        assert new_if is not original_if
        # …but its `test` and untouched `orelse` are shared by identity.
        assert new_if.test is original_test
        assert new_if.orelse[0] is original_orelse_stmt

    def test_repeatable_on_same_input(self) -> None:
        body = _parse_body(
            """
for item in items:
    _append(item)
"""
        )

        result_1 = sync_body_to_stream(body)
        result_2 = sync_body_to_stream(body)

        assert ast.dump(result_1[0]) == ast.dump(result_2[0])
