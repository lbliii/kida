"""Tests for kida.analysis.node_visitor — NodeVisitor and NodeTransformer."""

from __future__ import annotations

from kida.analysis.node_visitor import NodeTransformer, NodeVisitor
from kida.nodes import Const, Data, If, Name, Template


def _make_template(*body):
    return Template(lineno=1, col_offset=0, body=tuple(body), extends=None, context_type=None)


# ---------------------------------------------------------------------------
# NodeVisitor
# ---------------------------------------------------------------------------


class TestNodeVisitor:
    def test_generic_visit_walks_children(self):
        names = []

        class NameCollector(NodeVisitor):
            def visit_Name(self, node):  # noqa: N802
                names.append(node.name)

        tpl = _make_template(
            If(
                lineno=1,
                col_offset=0,
                test=Name(lineno=1, col_offset=0, name="x", ctx="load"),
                body=(Data(lineno=1, col_offset=0, value="yes"),),
                else_=(),
                elif_=(),
            ),
        )
        NameCollector().visit(tpl)
        assert names == ["x"]

    def test_dispatch_cache_per_subclass(self):
        class A(NodeVisitor):
            pass

        class B(NodeVisitor):
            pass

        assert A._dispatch_cache is not B._dispatch_cache


# ---------------------------------------------------------------------------
# NodeTransformer
# ---------------------------------------------------------------------------


class TestNodeTransformer:
    def test_no_change_returns_same_node(self):
        node = Const(lineno=1, col_offset=0, value="hello")
        transformer = NodeTransformer()
        result = transformer.visit(node)
        assert result is node

    def test_replace_const_value(self):
        class Upper(NodeTransformer):
            def visit_Const(self, node):  # noqa: N802
                if isinstance(node.value, str):
                    return Const(
                        lineno=node.lineno, col_offset=node.col_offset, value=node.value.upper()
                    )
                return node

        node = Const(lineno=1, col_offset=0, value="hello")
        result = Upper().visit(node)
        assert result.value == "HELLO"

    def test_transform_children_in_tuple(self):
        class UpperData(NodeTransformer):
            def visit_Data(self, node):  # noqa: N802
                return Data(
                    lineno=node.lineno, col_offset=node.col_offset, value=node.value.upper()
                )

        tpl = _make_template(
            Data(lineno=1, col_offset=0, value="hi"),
        )
        result = UpperData().visit(tpl)
        assert result.body[0].value == "HI"

    def test_remove_node_returns_none(self):
        class RemoveData(NodeTransformer):
            def visit_Data(self, node):  # noqa: N802
                return None

        tpl = _make_template(
            Data(lineno=1, col_offset=0, value="text"),
            Data(lineno=2, col_offset=0, value="kept"),
        )
        result = RemoveData().visit(tpl)
        assert len(result.body) == 0

    def test_dispatch_cache_per_subclass(self):
        class A(NodeTransformer):
            pass

        class B(NodeTransformer):
            pass

        assert A._dispatch_cache is not B._dispatch_cache

    def test_visit_field_none(self):
        transformer = NodeTransformer()
        assert transformer._visit_field(None) is None

    def test_visit_field_primitive(self):
        transformer = NodeTransformer()
        assert transformer._visit_field("hello") == "hello"
        assert transformer._visit_field(42) == 42

    def test_generic_visit_with_if_node(self):
        """Test that complex nodes with multiple child fields are traversed."""

        class DataUpper(NodeTransformer):
            def visit_Data(self, node):  # noqa: N802
                return Data(
                    lineno=node.lineno, col_offset=node.col_offset, value=node.value.upper()
                )

        if_node = If(
            lineno=1,
            col_offset=0,
            test=Name(lineno=1, col_offset=0, name="cond", ctx="load"),
            body=(Data(lineno=2, col_offset=0, value="yes"),),
            else_=(Data(lineno=3, col_offset=0, value="no"),),
            elif_=(),
        )
        result = DataUpper().visit(if_node)
        assert result.body[0].value == "YES"
        assert result.else_[0].value == "NO"
