"""Tests for expression compilation dispatch refactor.

Validates dispatch-dict integrity, node type coverage, and AST output
stability via committed SHA-256 snapshots.
"""

from __future__ import annotations

import ast
import hashlib

import pytest

from kida import DictLoader, Environment

# ---------------------------------------------------------------------------
# Dispatch table validation
# ---------------------------------------------------------------------------


def test_expression_node_names_are_unique():
    """All expression node classes must have unique __name__ values.

    This is a prerequisite for dispatch-dict keyed by type(node).__name__.
    """
    from kida.nodes.expressions import (
        Await,
        BinOp,
        BoolOp,
        Compare,
        Concat,
        CondExpr,
        Const,
        Dict,
        Filter,
        FuncCall,
        Getattr,
        Getitem,
        InlinedFilter,
        List,
        ListComp,
        LoopVar,
        MarkSafe,
        Name,
        NullCoalesce,
        OptionalFilter,
        OptionalGetattr,
        OptionalGetitem,
        Pipeline,
        Range,
        SafePipeline,
        Slice,
        Test,
        Tuple,
        UnaryOp,
    )

    all_expr_classes = [
        Await,
        BinOp,
        BoolOp,
        Compare,
        Concat,
        CondExpr,
        Const,
        Dict,
        Filter,
        FuncCall,
        Getattr,
        Getitem,
        InlinedFilter,
        List,
        ListComp,
        LoopVar,
        MarkSafe,
        Name,
        NullCoalesce,
        OptionalFilter,
        OptionalGetattr,
        OptionalGetitem,
        Pipeline,
        Range,
        SafePipeline,
        Slice,
        Test,
        Tuple,
        UnaryOp,
    ]

    names = [cls.__name__ for cls in all_expr_classes]
    assert len(set(names)) == len(names), (
        f"Duplicate node class names: {[n for n in names if names.count(n) > 1]}"
    )


def test_dispatch_table_keys_are_valid_expr_types():
    """Every key in _EXPR_DISPATCH must name a real Expr subclass.

    A typo in a dispatch key would silently cause that node type to fall
    through to the None fallback at compile time.
    """
    import kida.nodes.expressions as expr_mod
    from kida.compiler.expressions import ExpressionCompilationMixin
    from kida.nodes.expressions import Expr

    for node_type in ExpressionCompilationMixin._EXPR_DISPATCH:
        cls = getattr(expr_mod, node_type, None)
        assert cls is not None, (
            f"Dispatch key '{node_type}' does not match any class in kida.nodes.expressions"
        )
        assert issubclass(cls, Expr), (
            f"Dispatch key '{node_type}' maps to {cls} which is not an Expr subclass"
        )


def test_dispatch_table_methods_exist():
    """Every method in _EXPR_DISPATCH must exist on ExpressionCompilationMixin."""
    from kida.compiler.expressions import ExpressionCompilationMixin

    for node_type, method_name in ExpressionCompilationMixin._EXPR_DISPATCH.items():
        assert hasattr(ExpressionCompilationMixin, method_name), (
            f"Dispatch entry '{node_type}' → '{method_name}' but method does not exist"
        )
        assert callable(getattr(ExpressionCompilationMixin, method_name)), (
            f"Dispatch entry '{node_type}' → '{method_name}' is not callable"
        )


# ---------------------------------------------------------------------------
# AST baseline — compile representative templates and compare against
# committed SHA-256 hashes of ast.dump() output.
# ---------------------------------------------------------------------------

# Coverage templates exercise the dispatched expression node types.
# Node types covered by each template are noted in comments.
_EXPR_COVERAGE_TEMPLATES = {
    # Const, Name
    "const_and_name": "{{ 42 }}{{ name }}{{ true }}{{ none }}",
    # Tuple, List, Dict
    "containers": "{% let t = (1, 2) %}{% let l = [1, 2] %}{% let d = {'a': 1} %}",
    # Getattr, Getitem, Slice
    "access": "{{ obj.attr }}{{ obj['key'] }}{{ items[1:3] }}",
    # BinOp (arithmetic, concat, polymorphic +)
    "binop": "{{ a + b }}{{ a - b }}{{ a * b }}{{ a ~ b }}",
    # UnaryOp, Compare, BoolOp, CondExpr
    "operators": "{{ not x }}{{ a > b }}{{ a and b }}{{ x if cond else y }}",
    # Filter, Pipeline
    "filters": "{{ name | upper }}{{ name |> lower |> title }}",
    # Test
    "tests": "{% if x is defined %}yes{% end %}{% if x is not none %}no{% end %}",
    # FuncCall
    "funccall": "{{ range(10) }}{{ items | join(', ') }}",
    # For loop (exercises loop context)
    "for_loop": "{% for i in items %}{{ i }}{% end %}",
    # NullCoalesce
    "null_coalesce": "{{ x ?? 'default' }}",
    # OptionalGetattr, OptionalGetitem
    "optional_access": "{{ obj?.attr }}{{ obj?['key'] }}",
    # Range
    "range_literal": "{% for i in 1..5 %}{{ i }}{% end %}",
    # FuncCall with known def names
    "def_and_call": "{% def greet(name) %}Hello {{ name }}{% end %}{{ greet('world') }}",
    # ListComp
    "listcomp": "{% let evens = [x for x in items if x % 2 == 0] %}",
    # BinOp with _coerce_numeric (Filter in arithmetic)
    "nested": "{{ (a | length) * (b | length) }}",
    # Filter (default special case)
    "default_filter": "{{ missing | default('fallback') }}",
    # OptionalFilter
    "optional_filter": "{{ value ?| upper ?? 'N/A' }}",
    # Block + extends
    "child": "{% extends 'base' %}{% block content %}Hello{% end %}",
    # SafePipeline (?|>)
    "safe_pipeline": "{{ name ?|> lower ?|> title }}",
}

_BASE_TEMPLATE = "<html>{% block content %}{% end %}</html>"

# Committed SHA-256 hashes (first 16 hex chars) of ast.dump() output.
# To regenerate after an intentional compilation change, run the tests
# with --update-snapshots (not implemented) or copy hashes from the
# failure output.
_EXPECTED_AST_HASHES: dict[str, str] = {
    "access": "71fc549f50efb593",
    "binop": "c44d54e6197f759f",
    "child": "7866afbc6d92b913",
    "const_and_name": "eb85c44d327fe665",
    "containers": "4aeb3987abfd6e5a",
    "def_and_call": "fcf2611c427b1fc3",
    "default_filter": "24396f574facd156",
    "filters": "619237bf9d159a10",
    "for_loop": "62fb937187a114fd",
    "funccall": "2893731dd74f67e9",
    "listcomp": "265b0ac499dde785",
    "nested": "b375919b692f1c7f",
    "null_coalesce": "7c595473ee6e6efa",
    "operators": "88521c06e38ee0ce",
    "optional_access": "a65a5bfb9bf29f48",
    "optional_filter": "2cd7710940fb25b6",
    "range_literal": "9e1252f82c695e77",
    "safe_pipeline": "e488e7f6739b692d",
    "tests": "a32034534ad48641",
}


def _compile_to_ast_dump(templates: dict[str, str]) -> dict[str, str]:
    """Compile each template and return ast.dump() of generated Python AST."""
    from kida.compiler import Compiler
    from kida.lexer import Lexer
    from kida.parser import Parser

    all_templates = {"base": _BASE_TEMPLATE, **templates}
    env = Environment(loader=DictLoader(all_templates))
    results = {}
    for name in templates:
        source = all_templates[name]
        lexer = Lexer(source, env._lexer_config)
        tokens = list(lexer.tokenize())
        parser = Parser(tokens, name, source=source, autoescape=env.select_autoescape(name))
        ast_node = parser.parse()
        compiler = Compiler(env)
        module = compiler._compile_template(ast_node)
        ast.fix_missing_locations(module)
        results[name] = ast.dump(module, indent=2)
    return results


@pytest.fixture(scope="module")
def baseline_asts():
    """Compile all coverage templates and return their AST dumps."""
    return _compile_to_ast_dump(_EXPR_COVERAGE_TEMPLATES)


class TestASTBaseline:
    """Verify expression compilation against committed AST snapshots.

    Each template's ast.dump() output is hashed and compared to the
    committed hash in _EXPECTED_AST_HASHES. This catches both accidental
    changes and intentional ones (which require updating the hashes).
    """

    def test_all_templates_compile(self, baseline_asts):
        """Every coverage template compiles without error."""
        assert len(baseline_asts) == len(_EXPR_COVERAGE_TEMPLATES)

    def test_const_and_name(self, baseline_asts):
        dump = baseline_asts["const_and_name"]
        assert "Constant(value=42)" in dump
        assert "_ls" in dump

    def test_containers(self, baseline_asts):
        dump = baseline_asts["containers"]
        assert "Tuple" in dump or "List" in dump or "Dict" in dump

    def test_binop(self, baseline_asts):
        dump = baseline_asts["binop"]
        assert "_markup_concat" in dump
        assert "_add_polymorphic" in dump

    def test_filters(self, baseline_asts):
        dump = baseline_asts["filters"]
        assert "_filters" in dump

    def test_tests(self, baseline_asts):
        dump = baseline_asts["tests"]
        assert "_is_defined" in dump

    def test_null_coalesce(self, baseline_asts):
        dump = baseline_asts["null_coalesce"]
        assert "_null_coalesce" in dump

    def test_optional_access(self, baseline_asts):
        dump = baseline_asts["optional_access"]
        assert "_getattr_none" in dump

    def test_default_filter(self, baseline_asts):
        dump = baseline_asts["default_filter"]
        assert "_default_safe" in dump

    def test_def_and_call(self, baseline_asts):
        dump = baseline_asts["def_and_call"]
        assert "greet" in dump

    def test_nested_arithmetic_with_filters(self, baseline_asts):
        dump = baseline_asts["nested"]
        assert "_coerce_numeric" in dump

    def test_safe_pipeline(self, baseline_asts):
        dump = baseline_asts["safe_pipeline"]
        assert "_filters" in dump

    def test_ast_hashes_match_committed_snapshots(self, baseline_asts):
        """Verify compiled AST output matches committed SHA-256 hashes.

        This is the true regression gate: it catches any change to compiled
        output, whether the change is deterministic or not. If an intentional
        compilation change breaks this test, update _EXPECTED_AST_HASHES.
        """
        for name, dump in baseline_asts.items():
            actual = hashlib.sha256(dump.encode()).hexdigest()[:16]
            expected = _EXPECTED_AST_HASHES.get(name)
            assert expected is not None, (
                f"No committed hash for template '{name}' — add it to _EXPECTED_AST_HASHES"
            )
            assert actual == expected, (
                f"AST hash mismatch for '{name}': expected {expected}, got {actual}. "
                f"If this is intentional, update _EXPECTED_AST_HASHES."
            )
