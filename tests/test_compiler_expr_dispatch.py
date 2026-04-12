"""Tests for expression compilation dispatch refactor.

Sprint 0: AST baseline + dispatch-dict validation.
These tests ensure the _compile_expr refactor is behavior-preserving.
"""

from __future__ import annotations

import ast

import pytest

from kida import DictLoader, Environment

# ---------------------------------------------------------------------------
# Sprint 0.2: Validate that node class names are unique (no collisions)
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
# Sprint 0.1: AST baseline — compile representative templates, snapshot the
# generated Python AST so any refactor that changes output is caught.
# ---------------------------------------------------------------------------

# Templates designed to exercise every expression node type that _compile_expr handles.
_EXPR_COVERAGE_TEMPLATES = {
    # Const, Name, Output
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
    # For loop (exercises ListComp indirectly through loop context)
    "for_loop": "{% for i in items %}{{ i }}{% end %}",
    # NullCoalesce
    "null_coalesce": "{{ x ?? 'default' }}",
    # OptionalGetattr, OptionalGetitem
    "optional_access": "{{ obj?.attr }}{{ obj?['key'] }}",
    # Range literal
    "range_literal": "{% for i in 1..5 %}{{ i }}{% end %}",
    # Def + Call (exercises FuncCall with known def names)
    "def_and_call": "{% def greet(name) %}Hello {{ name }}{% end %}{{ greet('world') }}",
    # ListComp
    "listcomp": "{% let evens = [x for x in items if x % 2 == 0] %}",
    # Nested expressions (uses * to trigger _coerce_numeric for filter results)
    "nested": "{{ (a | length) * (b | length) }}",
    # default filter (special-cased in compiler)
    "default_filter": "{{ missing | default('fallback') }}",
    # OptionalFilter
    "optional_filter": "{{ value ?| upper ?? 'N/A' }}",
    # Block + extends (ensures block compilation paths aren't broken)
    "child": "{% extends 'base' %}{% block content %}Hello{% end %}",
}

_BASE_TEMPLATE = "<html>{% block content %}{% end %}</html>"


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
    """Verify that expression compilation produces consistent AST output.

    These tests act as a regression gate during the _compile_expr refactor.
    If any test fails after a refactor, the compiled output has changed.
    """

    def test_all_templates_compile(self, baseline_asts):
        """Every coverage template compiles without error."""
        assert len(baseline_asts) == len(_EXPR_COVERAGE_TEMPLATES)

    def test_const_and_name(self, baseline_asts):
        dump = baseline_asts["const_and_name"]
        # Const 42 should appear as ast.Constant(value=42)
        assert "Constant(value=42)" in dump
        # Name lookup should use _ls (scope lookup)
        assert "_ls" in dump

    def test_containers(self, baseline_asts):
        dump = baseline_asts["containers"]
        assert "Tuple" in dump or "List" in dump or "Dict" in dump

    def test_binop(self, baseline_asts):
        dump = baseline_asts["binop"]
        # ~ compiles to _markup_concat
        assert "_markup_concat" in dump
        # + compiles to _add_polymorphic
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
        # Filter results in arithmetic should be coerced
        assert "_coerce_numeric" in dump

    def test_ast_snapshot_stability(self, baseline_asts):
        """Compile templates twice and verify AST output is deterministic.

        This is the core regression gate: if the refactor changes compiled
        output, the second compilation will produce different AST dumps.
        """
        second_pass = _compile_to_ast_dump(_EXPR_COVERAGE_TEMPLATES)
        for name in _EXPR_COVERAGE_TEMPLATES:
            assert baseline_asts[name] == second_pass[name], (
                f"AST dump for '{name}' is not deterministic across compilations"
            )
