"""Contracts for immutable def/region signature planning."""

from __future__ import annotations

import ast
import hashlib

from kida import DictLoader, Environment
from kida.compiler import Compiler
from kida.compiler.callable_plans import plan_def_signature, plan_region_signature
from kida.lexer import Lexer
from kida.nodes import Const, Def, DefParam, Region
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


def _generated_ast_hash(name: str, source: str) -> str:
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
    dump = ast.dump(module, indent=2)
    return hashlib.sha256(dump.encode()).hexdigest()[:16]


def test_def_signature_plan_preserves_generated_python_ast() -> None:
    assert _generated_ast_hash("def_signature", DEF_SIGNATURE_SOURCE) == "856978009dca02c7"


def test_region_signature_plan_preserves_generated_python_ast() -> None:
    assert _generated_ast_hash("region_signature", REGION_SIGNATURE_SOURCE) == "d49d047e1cf94283"
