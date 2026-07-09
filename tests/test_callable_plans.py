"""Contracts for immutable callable planning."""

from __future__ import annotations

import ast
import hashlib

from kida import DictLoader, Environment
from kida.compiler import Compiler
from kida.compiler.callable_plans import (
    plan_call_block,
    plan_def_signature,
    plan_region_signature,
    plan_slot_render,
)
from kida.lexer import Lexer
from kida.nodes import CallBlock, Const, Data, Def, DefParam, Region, Slot
from kida.parser import Parser

DEF_SIGNATURE_SOURCE = (
    "{% def render(title: str, count: int = 2, *items, **attrs) %}"
    "{{ title }}{{ count }}{{ items | length }}{{ attrs | length }}"
    '{% end %}{{ render("x") }}'
)
REGION_SIGNATURE_SOURCE = (
    "{% region panel(title: str, count: int = 2, *items, **attrs) %}"
    "{{ title }}{{ count }}{{ items | length }}{{ attrs | length }}"
    '{% end %}{{ panel("x") }}'
)
SCOPED_CALL_SLOT_SOURCE = (
    "{% def items(data) %}{% for item in data %}"
    "{% slot row let:item=item %}({{ item }}){% end %}{% end %}{% end %}"
    '{% call items(["a", "b"]) %}'
    "{% slot row let:item %}[{{ item }}]{% end %}tail{% end %}"
)
NESTED_CALL_SLOT_SOURCE = (
    "{% def inner() %}<i>{% slot named %}</i>{% end %}"
    "{% def wrapper() %}{% call inner() %}"
    "{% slot named %}   {% end %}{% end %}{% end %}"
    "{% call wrapper() %}{% slot named %}value{% end %}{% end %}"
)


def _params() -> tuple[DefParam, ...]:
    return (
        DefParam(lineno=1, col_offset=0, name="title", annotation="str"),
        DefParam(lineno=1, col_offset=0, name="count", annotation="int"),
        DefParam(lineno=1, col_offset=0, name="tone", annotation=None),
    )


def _defaults() -> tuple[Const, ...]:
    return (
        Const(lineno=1, col_offset=0, value=2),
        Const(lineno=1, col_offset=0, value="neutral"),
    )


def test_def_signature_plan_maps_defaults_variadics_and_annotations() -> None:
    node = Def(
        lineno=1,
        col_offset=0,
        name="card",
        params=_params(),
        body=(),
        defaults=_defaults(),
        vararg="items",
        kwarg="attrs",
    )

    plan = plan_def_signature(node)

    assert plan.public_name == "card"
    assert plan.function_name == "_def_card"
    assert plan.parameter_names == ("title", "count", "tone")
    assert tuple(parameter.annotation for parameter in plan.parameters) == ("str", "int", None)
    assert plan.default_parameter_names == ("count", "tone")
    assert plan.bound_names == ("title", "count", "tone", "items", "attrs")
    assert type(plan).__dataclass_params__.frozen is True


def test_region_signature_plan_handles_no_defaults_without_slicing_all_params() -> None:
    node = Region(
        lineno=1,
        col_offset=0,
        name="panel",
        params=_params(),
        body=(),
        defaults=(),
        vararg=None,
        kwarg=None,
    )

    plan = plan_region_signature(node)

    assert plan.function_name == "_region_panel"
    assert plan.default_parameter_names == ()
    assert plan.bound_names == ("title", "count", "tone")

    aliased_plan = plan_region_signature(node, emitted_name="layout_panel")
    assert aliased_plan.public_name == "panel"
    assert aliased_plan.function_name == "_region_layout_panel"


def test_call_block_plan_preserves_order_names_and_empty_delegation() -> None:
    whitespace = Data(lineno=1, col_offset=0, value=" \n ")
    content = Data(lineno=1, col_offset=0, value="content")
    call = Const(lineno=1, col_offset=0, value=None)
    node = CallBlock(
        lineno=1,
        col_offset=0,
        call=call,
        slots={"header-actions": (whitespace,), "default": (content,)},
        args=(),
    )

    plan = plan_call_block(node)

    assert plan.call is call
    assert tuple(slot.name for slot in plan.slots) == ("header-actions", "default")
    assert tuple(slot.function_name for slot in plan.slots) == (
        "_caller_header_actions",
        "_caller_default",
    )
    assert tuple(slot.delegates_when_nested for slot in plan.slots) == (True, False)
    assert plan.slot_function_items == (
        ("header-actions", "_caller_header_actions"),
        ("default", "_caller_default"),
    )
    assert type(plan).__dataclass_params__.frozen is True


def test_slot_render_plan_freezes_bindings_and_default_body() -> None:
    expression = Const(lineno=1, col_offset=0, value="value")
    body = Data(lineno=1, col_offset=0, value="default")
    node = Slot(
        lineno=1,
        col_offset=0,
        name="row",
        bindings=(("item", expression),),
        body=(body,),
    )

    plan = plan_slot_render(node)

    assert plan.name == "row"
    assert plan.binding_names == ("item",)
    assert plan.bindings[0].expression is expression
    assert plan.body == (body,)
    assert type(plan).__dataclass_params__.frozen is True


def _generated_ast_hash(
    name: str,
    source: str,
    *,
    include_attributes: bool = False,
) -> str:
    env = Environment(loader=DictLoader({name: source}))
    tokens = list(Lexer(source, env._lexer_config).tokenize())
    tree = Parser(
        tokens,
        name,
        source=source,
        autoescape=env.select_autoescape(name),
    ).parse()
    module = Compiler(env)._compile_template(tree)
    ast.fix_missing_locations(module)
    dump = ast.dump(module, include_attributes=include_attributes, indent=2)
    return hashlib.sha256(dump.encode()).hexdigest()[:16]


def test_def_signature_plan_preserves_generated_python_ast() -> None:
    assert _generated_ast_hash("def_signature", DEF_SIGNATURE_SOURCE) == "856978009dca02c7"


def test_region_signature_plan_preserves_generated_python_ast() -> None:
    assert _generated_ast_hash("region_signature", REGION_SIGNATURE_SOURCE) == "d49d047e1cf94283"


def test_scoped_call_slot_plans_preserve_generated_python_ast() -> None:
    assert _generated_ast_hash("scoped_call_slot", SCOPED_CALL_SLOT_SOURCE) == "81877fce9690daf9"
    assert (
        _generated_ast_hash(
            "scoped_call_slot",
            SCOPED_CALL_SLOT_SOURCE,
            include_attributes=True,
        )
        == "a87738b271750427"
    )


def test_nested_call_slot_plans_preserve_generated_python_ast() -> None:
    assert _generated_ast_hash("nested_call_slot", NESTED_CALL_SLOT_SOURCE) == "7794e434b2ae552f"
    assert (
        _generated_ast_hash(
            "nested_call_slot",
            NESTED_CALL_SLOT_SOURCE,
            include_attributes=True,
        )
        == "02121ac06a6b375a"
    )
