"""Contract tests for literal block and fragment modifiers."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from kida import BlockModifierMetadata, DictLoader, Environment, ErrorCode
from kida.formatter import format_template
from kida.nodes import Block, BlockModifier
from kida.parser.errors import ParseError


def test_block_modifiers_preserve_types_order_and_source_locations() -> None:
    source = (
        "{% block chart\n"
        '  enhanced="sse" fallback="table" retries=3 ratio=-1.5\n'
        "  enabled=true disabled=False nullable=None %}x{% end %}"
    )

    template = Environment().from_string(source)
    metadata = template.block_metadata()["chart"]

    assert metadata.modifiers == (
        BlockModifierMetadata("enhanced", "sse", 2, 2),
        BlockModifierMetadata("fallback", "table", 2, 17),
        BlockModifierMetadata("retries", 3, 2, 34),
        BlockModifierMetadata("ratio", -1.5, 2, 44),
        BlockModifierMetadata("enabled", True, 3, 2),
        BlockModifierMetadata("disabled", False, 3, 15),
        BlockModifierMetadata("nullable", None, 3, 30),
    )
    assert metadata.get_modifier("enhanced") == metadata.modifiers[0]
    assert metadata.get_modifier("missing") is None


def test_fragment_modifiers_are_available_through_introspection() -> None:
    template = Environment().from_string(
        '{% fragment updates transport="sse" %}{{ message }}{% end %}'
    )

    metadata = template.template_metadata()

    assert metadata is not None
    assert metadata.blocks["updates"].get_modifier("transport") == BlockModifierMetadata(
        "transport", "sse", 1, 20
    )
    assert template.render(message="ignored") == ""
    assert template.render_block("updates", message="ready") == "ready"


def test_modifier_metadata_is_deeply_immutable() -> None:
    metadata = (
        Environment()
        .from_string('{% block chart enhanced="sse" %}x{% end %}')
        .block_metadata()["chart"]
    )

    with pytest.raises(FrozenInstanceError):
        metadata.modifiers = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        metadata.modifiers[0].value = "poll"  # type: ignore[misc]


def test_modifiers_do_not_change_rendering_or_structural_hashes() -> None:
    env = Environment()
    plain = env.from_string("{% block chart %}<p>{{ value }}</p>{% end %}")
    annotated = env.from_string(
        '{% block chart enhanced="sse" fallback="table" %}<p>{{ value }}</p>{% end %}'
    )

    assert plain.render(value="ok") == annotated.render(value="ok") == "<p>ok</p>"
    assert plain.render_block("chart", value="ok") == annotated.render_block("chart", value="ok")
    assert list(plain.render_stream(value="ok")) == list(annotated.render_stream(value="ok"))
    assert asyncio.run(plain.render_async(value="ok")) == asyncio.run(
        annotated.render_async(value="ok")
    )
    assert (
        plain.block_metadata()["chart"].block_hash == annotated.block_metadata()["chart"].block_hash
    )


def test_modifiers_survive_inheritance_and_partial_evaluation() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "base.html": (
                    '{% block chart enhanced="sse" %}{% if true %}{{ label }}{% end %}{% end %}'
                ),
                "child.html": '{% extends "base.html" %}',
            }
        ),
        static_context={"label": "ready"},
    )

    template = env.get_template("child.html")

    assert template.render() == "ready"
    assert template.render_block("chart") == "ready"
    assert template.block_metadata()["chart"].get_modifier("enhanced") is not None


def test_modifiers_coexist_with_imports_and_block_composition() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "macros.html": "{% def badge(label) %}<b>{{ label }}</b>{% end %}",
                "page.html": (
                    '{% from "macros.html" import badge %}'
                    '{% block content enhanced="sse" %}{{ badge("ready") }}{% end %}'
                ),
            }
        )
    )
    template = env.get_template("page.html")

    assert template.render() == "<b>ready</b>"
    assert template.render_with_blocks({}) == "<b>ready</b>"
    assert template.render_with_blocks({"content": "replacement"}) == "replacement"
    assert template.block_metadata()["content"].get_modifier("enhanced") is not None


def test_modifiers_coexist_with_block_conditions_and_formatter() -> None:
    source = '{%block chart enhanced="sse" if show%}x{%end%}'
    formatted = format_template(source)
    template = Environment().from_string(formatted)

    assert formatted == '{% block chart enhanced="sse" if show %}x{% end %}\n'
    assert template.render(show=True) == "x\n"
    assert template.render(show=False) == "\n"
    assert template.block_metadata()["chart"].get_modifier("enhanced") is not None


def test_modifier_named_if_is_distinct_from_condition() -> None:
    template = Environment().from_string('{% block chart if="metadata" if show %}x{% end %}')

    assert template.render(show=True) == "x"
    assert template.block_metadata()["chart"].get_modifier("if") == BlockModifierMetadata(
        "if", "metadata", 1, 15
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('{% block chart enhanced="sse" enhanced="poll" %}x{% end %}', "Duplicate"),
        ("{% block chart enhanced=transport %}x{% end %}", "literal scalar"),
        ("{% block chart enhanced=transport() %}x{% end %}", "literal scalar"),
        ('{% block chart enhanced=["sse"] %}x{% end %}', "literal scalar"),
        ('{% block chart enhanced={"mode": "sse"} %}x{% end %}', "literal scalar"),
        ("{% block chart enhanced %}x{% end %}", "name=value"),
        ("{% fragment updates transport %}x{% end %}", "name=value"),
    ],
)
def test_malformed_or_dynamic_modifiers_fail_during_compilation(source: str, message: str) -> None:
    with pytest.raises(ParseError, match=message) as exc_info:
        Environment().from_string(source)

    assert exc_info.value.code in (ErrorCode.UNEXPECTED_TOKEN, ErrorCode.UNSUPPORTED_SYNTAX)


def test_block_ast_exposes_immutable_modifier_nodes() -> None:
    template = Environment(preserve_ast=True).from_string(
        '{% block chart enhanced="sse" %}x{% end %}'
    )
    ast = template._optimized_ast

    assert ast is not None
    block = ast.body[0]
    assert isinstance(block, Block)
    assert block.modifiers == (BlockModifier(1, 15, "enhanced", "sse"),)
    with pytest.raises(FrozenInstanceError):
        block.modifiers[0].value = "poll"  # type: ignore[misc]
