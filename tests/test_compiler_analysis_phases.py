"""Focused contracts for compiler template and CSE analysis phases."""

from __future__ import annotations

import pytest

from kida import DictLoader, Environment
from kida.compiler import Compiler
from kida.compiler.analysis_phases import (
    analyze_cacheable_names,
    collect_template_blocks,
    collect_variable_references,
)
from kida.environment.exceptions import TemplateSyntaxError
from kida.nodes import Block, CallBlock, Const, Data, Def, If, Name, Set, SlotBlock
from kida.nodes.structure import Template


def _compile_nodes(*nodes) -> None:
    root = Template(
        lineno=1,
        col_offset=0,
        body=nodes,
        extends=None,
        context_type=None,
    )
    Compiler(Environment(loader=DictLoader({}))).compile(root, name="test.html")


def test_collect_template_blocks_preserves_nested_discovery_order() -> None:
    inner = Block(
        lineno=2,
        col_offset=0,
        name="inner",
        body=(Data(lineno=2, col_offset=0, value="inner"),),
    )
    outer = Block(
        lineno=1,
        col_offset=0,
        name="outer",
        body=(inner,),
    )

    blocks = collect_template_blocks(
        (outer,),
        template_name="test.html",
        filename=None,
    )

    assert list(blocks) == ["outer", "inner"]
    assert blocks == {"outer": outer, "inner": inner}


def test_invalid_block_name_raises() -> None:
    bad_block = Block(
        lineno=1,
        col_offset=0,
        name="invalid-name",
        body=(Data(lineno=2, col_offset=0, value="x"),),
    )

    with pytest.raises(TemplateSyntaxError, match=r"Invalid block name.*invalid-name"):
        _compile_nodes(bad_block)


def test_invalid_def_name_raises() -> None:
    bad_def = Def(
        lineno=1,
        col_offset=0,
        name="invalid-def",
        params=(),
        body=(Data(lineno=2, col_offset=0, value="x"),),
    )

    with pytest.raises(TemplateSyntaxError, match=r"Invalid def name.*invalid-def"):
        _compile_nodes(bad_def)


def test_invalid_slot_name_raises() -> None:
    bad_slot = SlotBlock(
        lineno=1,
        col_offset=0,
        name="bad-slot",
        body=(Data(lineno=2, col_offset=0, value="x"),),
    )

    with pytest.raises(TemplateSyntaxError, match=r"Invalid slot name.*bad-slot"):
        _compile_nodes(bad_slot)


def test_variable_reference_analysis_separates_refs_mutations_and_branches() -> None:
    user = Name(lineno=1, col_offset=0, name="user")
    nodes = (
        user,
        user,
        Set(
            lineno=1,
            col_offset=0,
            target=Name(lineno=1, col_offset=0, name="changed", ctx="store"),
            value=user,
        ),
        If(
            lineno=1,
            col_offset=0,
            test=Name(lineno=1, col_offset=0, name="enabled"),
            body=(
                Name(lineno=1, col_offset=0, name="conditional"),
                Name(lineno=1, col_offset=0, name="conditional"),
            ),
        ),
    )

    references, mutated = collect_variable_references(nodes)

    assert references == {"user": 3, "enabled": 1}
    assert mutated == {"changed"}
    assert analyze_cacheable_names(nodes, local_names=set()) == {"user"}
    assert analyze_cacheable_names(nodes, local_names={"user"}) == set()


def test_call_slot_references_are_not_eagerly_cacheable() -> None:
    call = CallBlock(
        lineno=1,
        col_offset=0,
        call=Name(lineno=1, col_offset=0, name="component"),
        slots={
            "default": (
                Name(lineno=1, col_offset=0, name="scoped"),
                Name(lineno=1, col_offset=0, name="scoped"),
            )
        },
    )

    references, mutated = collect_variable_references((call,))

    assert references == {"component": 1}
    assert mutated == set()
    assert analyze_cacheable_names((call,), local_names=set()) == set()


def test_control_flow_only_body_skips_cse_collection() -> None:
    conditional = If(
        lineno=1,
        col_offset=0,
        test=Const(lineno=1, col_offset=0, value=True),
        body=(Name(lineno=1, col_offset=0, name="conditional"),),
    )

    assert analyze_cacheable_names((conditional,), local_names=set()) == set()
