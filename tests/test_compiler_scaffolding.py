"""Focused contracts for compiler source-location and diagnostic helpers."""

from __future__ import annotations

import ast
from copy import deepcopy

import pytest

from kida import Environment
from kida.compiler.utils import (
    fix_missing_locations_fast,
    make_line_marker,
    make_template_warning,
)
from kida.exceptions import ErrorCode, UndefinedError


def _partially_located_module() -> ast.Module:
    return ast.Module(
        body=[
            ast.If(
                test=ast.Name(
                    id="enabled",
                    ctx=ast.Load(),
                    lineno=7,
                    col_offset=4,
                    end_lineno=7,
                    end_col_offset=11,
                ),
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Name(id="work", ctx=ast.Load()),
                            args=[],
                            keywords=[],
                        )
                    )
                ],
                orelse=[],
            )
        ],
        type_ignores=[],
    )


def test_fast_location_fill_matches_stdlib_and_preserves_concrete_type() -> None:
    module = _partially_located_module()
    expected = ast.fix_missing_locations(deepcopy(module))

    actual = fix_missing_locations_fast(module)

    assert actual is module
    assert ast.dump(actual, include_attributes=True) == ast.dump(expected, include_attributes=True)


def test_line_marker_has_stable_generated_ast_shape() -> None:
    marker = make_line_marker(42)

    assert ast.dump(marker) == (
        "Assign(targets=[Attribute(value=Name(id='_rc', ctx=Load()), "
        "attr='line', ctx=Store())], value=Constant(value=42))"
    )


def test_template_warning_helper_preserves_diagnostic_provenance() -> None:
    warning = make_template_warning(
        ErrorCode.JINJA2_SET_SCOPING,
        "nested set shadows template state",
        template_name="page.kida",
        lineno=9,
        suggestion="Use export instead.",
    )

    assert warning.code is ErrorCode.JINJA2_SET_SCOPING
    assert warning.message == "nested set shadows template state"
    assert warning.template_name == "page.kida"
    assert warning.lineno == 9
    assert warning.suggestion == "Use export instead."


def test_coalesced_output_keeps_runtime_template_line() -> None:
    template = Environment(fstring_coalescing=True).from_string(
        "safe\nprefix {{ missing }}",
        name="line.kida",
    )

    with pytest.raises(UndefinedError) as exc_info:
        template.render()

    assert exc_info.value.template == "line.kida"
    assert exc_info.value.lineno == 2
