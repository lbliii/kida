"""Contracts for immutable block render-mode strategy planning."""

from __future__ import annotations

import ast
import hashlib

import pytest

from kida import DictLoader, Environment
from kida.compiler import Compiler
from kida.compiler.stream_transform import (
    BlockLoweringStrategy,
    plan_block_render_modes,
)
from kida.lexer import Lexer
from kida.nodes import (
    Cache,
    Capture,
    Const,
    Data,
    Filter,
    FilterBlock,
    Node,
    Push,
    Spaceless,
)
from kida.parser import Parser

AST_CASES = (
    (
        "plain",
        {"plain": "{% block content %}Hello {{ name }}{% end %}"},
        "plain",
        "b8a82ac1d79dfff2",
        "075fbbd2e9623f2c",
    ),
    (
        "capture",
        {
            "capture": (
                "{% block content %}{% capture message %}Hi {{ name }}{% end %}"
                "{{ message }}{% end %}"
            )
        },
        "capture",
        "17feb42fcde3d9d8",
        "3d8e53fe84118875",
    ),
    (
        "region",
        {"region": ('{% region panel(name) %}<p>{{ name }}</p>{% end %}{{ panel("x") }}')},
        "region",
        "319763b427a0e90f",
        "c8690ec35716e6b2",
    ),
    (
        "async",
        {"async": ("{% block content %}{% async for item in items %}{{ item }}{% end %}{% end %}")},
        "async",
        "da10c61a10540e10",
        "fa10684b2c1e3820",
    ),
    (
        "inheritance",
        {
            "base": "{% block content %}Base{% end %}",
            "child": '{% extends "base" %}{% block content %}Child{% end %}',
        },
        "child",
        "35bdaefc06ab71da",
        "8259eda1b126565e",
    ),
    (
        "cache_filter",
        {
            "cache_filter": (
                '{% block cached %}{% cache "key" %}Hello {{ name }}{% end %}{% end %}'
                "{% block filtered %}{% filter upper %}Hi {{ name }}{% end %}{% end %}"
            )
        },
        "cache_filter",
        "256cfb522ef48654",
        "6d675c5428a45ae7",
    ),
    (
        "special_blocks",
        {
            "special_blocks": (
                "{% block content %}"
                "{% capture message %}Hi {{ name }}{% end %}"
                "{% spaceless %}<div> <span>{{ message }}</span> </div>{% end %}"
                '{% push "scripts" %}<script>{{ name }}</script>{% end %}'
                '{% stack "scripts" %}'
                "{% end %}"
            )
        },
        "special_blocks",
        "e1899843c72d64e1",
        "84cdb059d42b8e65",
    ),
)


class _FailingChildCompiler(Compiler):
    def _compile_node(self, node: Node) -> list[ast.stmt]:
        raise RuntimeError(f"stop on {type(node).__name__}")


@pytest.mark.parametrize("is_region", [False, True])
@pytest.mark.parametrize("rebinds_append", [False, True])
@pytest.mark.parametrize("template_has_regions", [False, True])
@pytest.mark.parametrize("template_has_async", [False, True])
def test_block_render_mode_plan_covers_complete_decision_matrix(
    *,
    is_region: bool,
    rebinds_append: bool,
    template_has_regions: bool,
    template_has_async: bool,
) -> None:
    plan = plan_block_render_modes(
        is_region=is_region,
        rebinds_append=rebinds_append,
        template_has_regions=template_has_regions,
        template_has_async=template_has_async,
    )

    direct_stream = is_region or rebinds_append or template_has_regions
    direct_async_stream = direct_stream or template_has_async
    assert (plan.stream is BlockLoweringStrategy.COMPILE_DIRECT) is direct_stream
    assert (plan.async_stream is BlockLoweringStrategy.COMPILE_DIRECT) is direct_async_stream


def test_block_render_mode_plan_is_frozen() -> None:
    plan = plan_block_render_modes(
        is_region=False,
        rebinds_append=False,
        template_has_regions=False,
        template_has_async=False,
    )

    assert type(plan).__dataclass_params__.frozen is True


def test_lowering_mode_restores_nested_state() -> None:
    compiler = Compiler(Environment())

    with compiler._lowering_mode(streaming=True):
        assert compiler._streaming is True
        assert compiler._async_mode is False
        with compiler._lowering_mode(streaming=False, async_mode=True):
            assert compiler._streaming is False
            assert compiler._async_mode is True
        assert compiler._streaming is True
        assert compiler._async_mode is False

    assert compiler._streaming is False
    assert compiler._async_mode is False


def test_lowering_mode_restores_state_after_exception() -> None:
    compiler = Compiler(Environment())
    compiler._streaming = True

    with (
        pytest.raises(RuntimeError, match="stop"),
        compiler._lowering_mode(streaming=False, async_mode=True),
    ):
        raise RuntimeError("stop")

    assert compiler._streaming is True
    assert compiler._async_mode is False


def test_lowering_mode_state_is_per_compiler_instance() -> None:
    first = Compiler(Environment())
    second = Compiler(Environment())

    with first._lowering_mode(streaming=True, async_mode=True):
        assert first._streaming is True
        assert first._async_mode is True
        assert second._streaming is False
        assert second._async_mode is False


@pytest.mark.parametrize(
    ("method_name", "node"),
    [
        (
            "_compile_cache",
            Cache(
                lineno=1,
                col_offset=0,
                key=Const(lineno=1, col_offset=0, value="key"),
                body=(Data(lineno=1, col_offset=0, value="body"),),
            ),
        ),
        (
            "_compile_filter_block",
            FilterBlock(
                lineno=1,
                col_offset=0,
                filter=Filter(
                    lineno=1,
                    col_offset=0,
                    value=Const(lineno=1, col_offset=0, value=""),
                    name="upper",
                ),
                body=(Data(lineno=1, col_offset=0, value="body"),),
            ),
        ),
    ],
)
def test_caching_body_failure_restores_streaming_mode(
    method_name: str,
    node: Cache | FilterBlock,
) -> None:
    compiler = _FailingChildCompiler(Environment())
    compiler._streaming = True
    compiler._async_mode = True

    with pytest.raises(RuntimeError, match="stop on Data"):
        getattr(compiler, method_name)(node)

    assert compiler._streaming is True
    assert compiler._async_mode is True


@pytest.mark.parametrize(
    ("method_name", "node"),
    [
        (
            "_compile_capture",
            Capture(
                lineno=1,
                col_offset=0,
                name="message",
                body=(Data(lineno=1, col_offset=0, value="body"),),
            ),
        ),
        (
            "_compile_spaceless",
            Spaceless(
                lineno=1,
                col_offset=0,
                body=(Data(lineno=1, col_offset=0, value="body"),),
            ),
        ),
        (
            "_compile_push",
            Push(
                lineno=1,
                col_offset=0,
                stack_name="scripts",
                body=(Data(lineno=1, col_offset=0, value="body"),),
            ),
        ),
    ],
)
def test_special_block_body_failure_restores_streaming_mode(
    method_name: str,
    node: Capture | Push | Spaceless,
) -> None:
    compiler = _FailingChildCompiler(Environment())
    compiler._streaming = True
    compiler._async_mode = True

    with pytest.raises(RuntimeError, match="stop on Data"):
        getattr(compiler, method_name)(node)

    assert compiler._streaming is True
    assert compiler._async_mode is True


def _generated_ast_hash(
    templates: dict[str, str],
    entry: str,
    *,
    include_attributes: bool,
) -> str:
    source = templates[entry]
    env = Environment(loader=DictLoader(templates))
    tokens = list(Lexer(source, env._lexer_config).tokenize())
    tree = Parser(
        tokens,
        entry,
        source=source,
        autoescape=env.select_autoescape(entry),
    ).parse()
    module = Compiler(env)._compile_template(tree)
    ast.fix_missing_locations(module)
    dump = ast.dump(module, include_attributes=include_attributes, indent=2)
    return hashlib.sha256(dump.encode()).hexdigest()[:16]


@pytest.mark.parametrize(
    ("case_name", "templates", "entry", "structural_hash", "location_hash"),
    AST_CASES,
)
def test_render_mode_plans_preserve_generated_ast_and_locations(
    case_name: str,
    templates: dict[str, str],
    entry: str,
    structural_hash: str,
    location_hash: str,
) -> None:
    assert _generated_ast_hash(templates, entry, include_attributes=False) == structural_hash, (
        case_name
    )
    assert _generated_ast_hash(templates, entry, include_attributes=True) == location_hash, (
        case_name
    )
