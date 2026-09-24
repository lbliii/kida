"""Property tests for parser/formatter round trips on a bounded grammar."""

from __future__ import annotations

from dataclasses import fields

from hypothesis import example, given, settings

from kida.formatter import format_template
from kida.lexer import tokenize
from kida.nodes import Node, Template
from kida.parser import Parser

from .strategies import format_roundtrip_source


def _parse_template(source: str) -> Template:
    """Parse a complete template for the format round-trip property."""
    return Parser(
        tokenize(source),
        name="<format-roundtrip>",
        source=source,
    ).parse()


def _ast_shape(value: object) -> object:
    """Preserve every AST field except source positions."""
    if isinstance(value, Node):
        return (
            type(value),
            tuple(
                (field.name, _ast_shape(getattr(value, field.name)))
                for field in fields(value)
                if field.name not in {"lineno", "col_offset"}
            ),
        )
    if isinstance(value, tuple):
        return (type(value), tuple(_ast_shape(item) for item in value))
    if isinstance(value, list):
        return (type(value), tuple(_ast_shape(item) for item in value))
    if isinstance(value, dict):
        return (
            type(value),
            tuple((_ast_shape(key), _ast_shape(item)) for key, item in value.items()),
        )
    return value


class TestFormatterProperties:
    """Structural parser/formatter properties for trim-controlled templates."""

    @given(source=format_roundtrip_source)
    @settings(max_examples=100)
    @example(source="{% if outer -%}\nplain42\n{%- end -%}")
    @example(source=("{% if outer -%}\n{% if inner -%}\n{{- value -}}\n{%- end -%}\n{%- end -%}"))
    @example(source="{% if outer -%}\n{{- first -}}\n{{- second -}}\n{%- end -%}")
    @example(
        source=(
            "{% if outer -%}\n{{- then_value -}}\n{%- else -%}\n{{- else_value -}}\n{%- end -%}"
        )
    )
    @example(source="{%if   outer   -%}\n{{-  value   -}}\n{%-  end   -%}")
    def test_parse_format_parse_preserves_ast(self, source: str) -> None:
        original_ast = _ast_shape(_parse_template(source))
        formatted_source = format_template(source)
        formatted_ast = _ast_shape(_parse_template(formatted_source))

        assert formatted_ast == original_ast
