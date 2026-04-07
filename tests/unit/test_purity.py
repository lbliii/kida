"""Unit tests for the PurityAnalyzer."""

from __future__ import annotations

import pytest

from kida.analysis.purity import PurityAnalyzer, _combine_purity
from kida.nodes import (
    Await,
    BinOp,
    Block,
    BoolOp,
    Break,
    Cache,
    Capture,
    Compare,
    Concat,
    CondExpr,
    Const,
    Continue,
    Data,
    Def,
    Dict,
    Extends,
    Filter,
    For,
    FuncCall,
    Getattr,
    Getitem,
    If,
    Include,
    InlinedFilter,
    Let,
    List,
    LoopVar,
    MarkSafe,
    Match,
    Name,
    NullCoalesce,
    OptionalGetattr,
    OptionalGetitem,
    Output,
    Pipeline,
    Range,
    Raw,
    Set,
    Slice,
    Slot,
    Test,
    Tuple,
    UnaryOp,
    With,
    WithConditional,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

L = 1  # default lineno
C = 0  # default col_offset

_const_hello = Const(L, C, value="hello")
_const_42 = Const(L, C, value=42)
_name_x = Name(L, C, name="x")
_name_y = Name(L, C, name="y")
_data = Data(L, C, value="static text")


# ---------------------------------------------------------------------------
# _combine_purity
# ---------------------------------------------------------------------------


class TestCombinePurity:
    def test_pure_pure(self) -> None:
        assert _combine_purity("pure", "pure") == "pure"

    def test_pure_unknown(self) -> None:
        assert _combine_purity("pure", "unknown") == "unknown"

    def test_pure_impure(self) -> None:
        assert _combine_purity("pure", "impure") == "impure"

    def test_unknown_impure(self) -> None:
        assert _combine_purity("unknown", "impure") == "impure"

    def test_impure_dominates(self) -> None:
        assert _combine_purity("impure", "pure") == "impure"
        assert _combine_purity("impure", "unknown") == "impure"
        assert _combine_purity("impure", "impure") == "impure"

    def test_unknown_dominates_pure(self) -> None:
        assert _combine_purity("unknown", "pure") == "unknown"


# ---------------------------------------------------------------------------
# Leaf nodes — all should be pure
# ---------------------------------------------------------------------------


class TestLeafNodes:
    @pytest.fixture
    def analyzer(self) -> PurityAnalyzer:
        return PurityAnalyzer()

    def test_const(self, analyzer: PurityAnalyzer) -> None:
        assert analyzer.analyze(_const_hello) == "pure"

    def test_const_none(self, analyzer: PurityAnalyzer) -> None:
        assert analyzer.analyze(Const(L, C, value=None)) == "pure"

    def test_name(self, analyzer: PurityAnalyzer) -> None:
        assert analyzer.analyze(_name_x) == "pure"

    def test_data(self, analyzer: PurityAnalyzer) -> None:
        assert analyzer.analyze(_data) == "pure"

    def test_raw(self, analyzer: PurityAnalyzer) -> None:
        assert analyzer.analyze(Raw(L, C, value="{% raw %}")) == "pure"

    def test_slot(self, analyzer: PurityAnalyzer) -> None:
        assert analyzer.analyze(Slot(L, C, name="default")) == "pure"

    def test_break(self, analyzer: PurityAnalyzer) -> None:
        assert analyzer.analyze(Break(L, C)) == "pure"

    def test_continue(self, analyzer: PurityAnalyzer) -> None:
        assert analyzer.analyze(Continue(L, C)) == "pure"

    def test_loop_var(self, analyzer: PurityAnalyzer) -> None:
        assert analyzer.analyze(LoopVar(L, C, attr="index")) == "pure"


# ---------------------------------------------------------------------------
# Expression nodes
# ---------------------------------------------------------------------------


class TestExpressionPurity:
    @pytest.fixture
    def analyzer(self) -> PurityAnalyzer:
        return PurityAnalyzer()

    def test_binop(self, analyzer: PurityAnalyzer) -> None:
        node = BinOp(L, C, op="+", left=_const_42, right=_name_x)
        assert analyzer.analyze(node) == "pure"

    def test_unaryop(self, analyzer: PurityAnalyzer) -> None:
        node = UnaryOp(L, C, op="not", operand=_name_x)
        assert analyzer.analyze(node) == "pure"

    def test_compare(self, analyzer: PurityAnalyzer) -> None:
        node = Compare(L, C, left=_name_x, ops=["=="], comparators=[_const_42])
        assert analyzer.analyze(node) == "pure"

    def test_boolop(self, analyzer: PurityAnalyzer) -> None:
        node = BoolOp(L, C, op="and", values=[_name_x, _name_y])
        assert analyzer.analyze(node) == "pure"

    def test_condexpr(self, analyzer: PurityAnalyzer) -> None:
        node = CondExpr(L, C, test=_name_x, if_true=_const_hello, if_false=_const_42)
        assert analyzer.analyze(node) == "pure"

    def test_null_coalesce(self, analyzer: PurityAnalyzer) -> None:
        node = NullCoalesce(L, C, left=_name_x, right=_const_hello)
        assert analyzer.analyze(node) == "pure"

    def test_concat(self, analyzer: PurityAnalyzer) -> None:
        node = Concat(L, C, nodes=[_const_hello, _name_x])
        assert analyzer.analyze(node) == "pure"

    def test_getattr(self, analyzer: PurityAnalyzer) -> None:
        node = Getattr(L, C, obj=_name_x, attr="name")
        assert analyzer.analyze(node) == "pure"

    def test_optional_getattr(self, analyzer: PurityAnalyzer) -> None:
        node = OptionalGetattr(L, C, obj=_name_x, attr="name")
        assert analyzer.analyze(node) == "pure"

    def test_getitem(self, analyzer: PurityAnalyzer) -> None:
        node = Getitem(L, C, obj=_name_x, key=_const_42)
        assert analyzer.analyze(node) == "pure"

    def test_optional_getitem(self, analyzer: PurityAnalyzer) -> None:
        node = OptionalGetitem(L, C, obj=_name_x, key=_const_42)
        assert analyzer.analyze(node) == "pure"

    def test_range(self, analyzer: PurityAnalyzer) -> None:
        node = Range(L, C, start=_const_42, end=Const(L, C, value=100))
        assert analyzer.analyze(node) == "pure"

    def test_range_with_step(self, analyzer: PurityAnalyzer) -> None:
        node = Range(L, C, start=_const_42, end=Const(L, C, value=100), step=Const(L, C, value=2))
        assert analyzer.analyze(node) == "pure"

    def test_slice(self, analyzer: PurityAnalyzer) -> None:
        node = Slice(L, C, start=_const_42, stop=Const(L, C, value=10), step=None)
        assert analyzer.analyze(node) == "pure"

    def test_slice_empty(self, analyzer: PurityAnalyzer) -> None:
        node = Slice(L, C, start=None, stop=None, step=None)
        assert analyzer.analyze(node) == "pure"

    def test_list_literal(self, analyzer: PurityAnalyzer) -> None:
        node = List(L, C, items=[_const_42, _name_x])
        assert analyzer.analyze(node) == "pure"

    def test_tuple_literal(self, analyzer: PurityAnalyzer) -> None:
        node = Tuple(L, C, items=[_const_42, _name_x])
        assert analyzer.analyze(node) == "pure"

    def test_dict_literal(self, analyzer: PurityAnalyzer) -> None:
        node = Dict(L, C, keys=[_const_hello], values=[_const_42])
        assert analyzer.analyze(node) == "pure"

    def test_marksafe(self, analyzer: PurityAnalyzer) -> None:
        node = MarkSafe(L, C, value=_name_x)
        assert analyzer.analyze(node) == "pure"

    def test_inlined_filter(self, analyzer: PurityAnalyzer) -> None:
        node = InlinedFilter(L, C, value=_name_x, method="upper")
        assert analyzer.analyze(node) == "pure"

    def test_output(self, analyzer: PurityAnalyzer) -> None:
        node = Output(L, C, expr=_name_x)
        assert analyzer.analyze(node) == "pure"

    def test_await_is_unknown(self, analyzer: PurityAnalyzer) -> None:
        node = Await(L, C, value=_name_x)
        assert analyzer.analyze(node) == "unknown"


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestFilterPurity:
    @pytest.fixture
    def analyzer(self) -> PurityAnalyzer:
        return PurityAnalyzer()

    def test_pure_filter(self, analyzer: PurityAnalyzer) -> None:
        node = Filter(L, C, value=_name_x, name="upper")
        assert analyzer.analyze(node) == "pure"

    def test_impure_filter(self, analyzer: PurityAnalyzer) -> None:
        node = Filter(L, C, value=_name_x, name="random")
        assert analyzer.analyze(node) == "impure"

    def test_unknown_filter(self, analyzer: PurityAnalyzer) -> None:
        node = Filter(L, C, value=_name_x, name="my_custom_filter")
        assert analyzer.analyze(node) == "unknown"

    def test_pure_filter_with_impure_arg(self, analyzer: PurityAnalyzer) -> None:
        impure_arg = Filter(L, C, value=_name_x, name="random")
        node = Filter(L, C, value=_name_x, name="upper", args=[impure_arg])
        assert analyzer.analyze(node) == "impure"

    def test_filter_with_kwargs(self, analyzer: PurityAnalyzer) -> None:
        node = Filter(L, C, value=_name_x, name="default", kwargs={"value": _const_hello})
        assert analyzer.analyze(node) == "pure"

    def test_extra_impure_filters(self) -> None:
        analyzer = PurityAnalyzer(extra_impure_filters=frozenset({"my_impure"}))
        node = Filter(L, C, value=_name_x, name="my_impure")
        assert analyzer.analyze(node) == "impure"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class TestPipelinePurity:
    @pytest.fixture
    def analyzer(self) -> PurityAnalyzer:
        return PurityAnalyzer()

    def test_pure_pipeline(self, analyzer: PurityAnalyzer) -> None:
        node = Pipeline(L, C, value=_name_x, steps=[("upper", [], {}), ("trim", [], {})])
        assert analyzer.analyze(node) == "pure"

    def test_impure_pipeline(self, analyzer: PurityAnalyzer) -> None:
        node = Pipeline(L, C, value=_name_x, steps=[("upper", [], {}), ("random", [], {})])
        assert analyzer.analyze(node) == "impure"

    def test_pipeline_with_args(self, analyzer: PurityAnalyzer) -> None:
        node = Pipeline(L, C, value=_name_x, steps=[("default", [_const_hello], {})])
        assert analyzer.analyze(node) == "pure"


# ---------------------------------------------------------------------------
# Function calls
# ---------------------------------------------------------------------------


class TestFuncCallPurity:
    @pytest.fixture
    def analyzer(self) -> PurityAnalyzer:
        return PurityAnalyzer()

    def test_known_pure_function(self, analyzer: PurityAnalyzer) -> None:
        node = FuncCall(L, C, func=Name(L, C, name="range"), args=[_const_42])
        assert analyzer.analyze(node) == "pure"

    def test_unknown_function(self, analyzer: PurityAnalyzer) -> None:
        node = FuncCall(L, C, func=Name(L, C, name="my_func"))
        assert analyzer.analyze(node) == "unknown"

    def test_method_call(self, analyzer: PurityAnalyzer) -> None:
        # Attribute-based calls are always unknown
        func = Getattr(L, C, obj=_name_x, attr="method")
        node = FuncCall(L, C, func=func)
        assert analyzer.analyze(node) == "unknown"

    def test_extra_pure_functions(self) -> None:
        analyzer = PurityAnalyzer(extra_pure_functions=frozenset({"safe_fn"}))
        node = FuncCall(L, C, func=Name(L, C, name="safe_fn"))
        assert analyzer.analyze(node) == "pure"


# ---------------------------------------------------------------------------
# Control flow
# ---------------------------------------------------------------------------


class TestControlFlowPurity:
    @pytest.fixture
    def analyzer(self) -> PurityAnalyzer:
        return PurityAnalyzer()

    def test_if_pure(self, analyzer: PurityAnalyzer) -> None:
        node = If(L, C, test=_name_x, body=[_data], else_=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_if_impure_body(self, analyzer: PurityAnalyzer) -> None:
        impure = Output(L, C, expr=Filter(L, C, value=_name_x, name="random"))
        node = If(L, C, test=_name_x, body=[impure], else_=[])
        assert analyzer.analyze(node) == "impure"

    def test_if_with_elif(self, analyzer: PurityAnalyzer) -> None:
        node = If(
            L,
            C,
            test=_name_x,
            body=[_data],
            elif_=[(_name_y, [_data])],
            else_=[_data],
        )
        assert analyzer.analyze(node) == "pure"

    def test_for_pure(self, analyzer: PurityAnalyzer) -> None:
        node = For(L, C, target=_name_x, iter=_name_y, body=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_for_with_empty(self, analyzer: PurityAnalyzer) -> None:
        node = For(L, C, target=_name_x, iter=_name_y, body=[_data], empty=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_match_pure(self, analyzer: PurityAnalyzer) -> None:
        node = Match(
            L,
            C,
            subject=_name_x,
            cases=[(_const_42, None, [_data])],
        )
        assert analyzer.analyze(node) == "pure"

    def test_match_with_guard(self, analyzer: PurityAnalyzer) -> None:
        node = Match(
            L,
            C,
            subject=_name_x,
            cases=[(_const_42, _name_y, [_data])],
        )
        assert analyzer.analyze(node) == "pure"


# ---------------------------------------------------------------------------
# Template structure
# ---------------------------------------------------------------------------


class TestStructurePurity:
    @pytest.fixture
    def analyzer(self) -> PurityAnalyzer:
        return PurityAnalyzer()

    def test_block_pure(self, analyzer: PurityAnalyzer) -> None:
        node = Block(L, C, name="content", body=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_with_pure(self, analyzer: PurityAnalyzer) -> None:
        node = With(L, C, targets=[("x", _const_42)], body=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_with_conditional(self, analyzer: PurityAnalyzer) -> None:
        node = WithConditional(L, C, expr=_name_x, target=_name_y, body=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_cache_pure(self, analyzer: PurityAnalyzer) -> None:
        node = Cache(L, C, key=_const_hello, body=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_set_pure(self, analyzer: PurityAnalyzer) -> None:
        node = Set(L, C, target=_name_x, value=_const_42)
        assert analyzer.analyze(node) == "pure"

    def test_let_pure(self, analyzer: PurityAnalyzer) -> None:
        node = Let(L, C, name=_name_x, value=_const_42)
        assert analyzer.analyze(node) == "pure"

    def test_capture_pure(self, analyzer: PurityAnalyzer) -> None:
        node = Capture(L, C, name="x", body=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_extends_unknown(self, analyzer: PurityAnalyzer) -> None:
        node = Extends(L, C, template=_const_hello)
        assert analyzer.analyze(node) == "unknown"

    def test_def_pure(self, analyzer: PurityAnalyzer) -> None:
        node = Def(L, C, name="greet", params=[], defaults=[], body=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_def_with_defaults(self, analyzer: PurityAnalyzer) -> None:
        node = Def(L, C, name="greet", params=[], defaults=[_const_hello], body=[_data])
        assert analyzer.analyze(node) == "pure"

    def test_test_node(self, analyzer: PurityAnalyzer) -> None:
        node = Test(L, C, value=_name_x, name="defined")
        assert analyzer.analyze(node) == "pure"


# ---------------------------------------------------------------------------
# Include resolution
# ---------------------------------------------------------------------------


class TestIncludePurity:
    def test_include_no_resolver(self) -> None:
        analyzer = PurityAnalyzer()
        node = Include(L, C, template=_const_hello)
        assert analyzer.analyze(node) == "unknown"

    def test_include_dynamic_name(self) -> None:
        analyzer = PurityAnalyzer(template_resolver=lambda n: None)
        node = Include(L, C, template=_name_x)
        assert analyzer.analyze(node) == "unknown"

    def test_include_not_found(self) -> None:
        analyzer = PurityAnalyzer(template_resolver=lambda n: None)
        node = Include(L, C, template=Const(L, C, value="missing.html"))
        assert analyzer.analyze(node) == "unknown"

    def test_include_pure_template(self) -> None:
        from types import SimpleNamespace

        # Fake a template with a pure AST
        fake_ast = SimpleNamespace(body=[_data])
        fake_tpl = SimpleNamespace(_optimized_ast=fake_ast)

        analyzer = PurityAnalyzer(template_resolver=lambda n: fake_tpl)
        node = Include(L, C, template=Const(L, C, value="partial.html"))
        assert analyzer.analyze(node) == "pure"

    def test_include_impure_template(self) -> None:
        from types import SimpleNamespace

        impure_output = Output(L, C, expr=Filter(L, C, value=_name_x, name="random"))
        fake_ast = SimpleNamespace(body=[impure_output])
        fake_tpl = SimpleNamespace(_optimized_ast=fake_ast)

        analyzer = PurityAnalyzer(template_resolver=lambda n: fake_tpl)
        node = Include(L, C, template=Const(L, C, value="partial.html"))
        assert analyzer.analyze(node) == "impure"

    def test_include_circular_detection(self) -> None:
        from types import SimpleNamespace

        # Template that includes itself
        self_include = Include(L, C, template=Const(L, C, value="self.html"))
        fake_ast = SimpleNamespace(body=[self_include])
        fake_tpl = SimpleNamespace(_optimized_ast=fake_ast)

        analyzer = PurityAnalyzer(template_resolver=lambda n: fake_tpl)
        node = Include(L, C, template=Const(L, C, value="self.html"))
        # Should return unknown (circular) rather than infinite loop
        assert analyzer.analyze(node) == "unknown"

    def test_include_no_ast(self) -> None:
        from types import SimpleNamespace

        fake_tpl = SimpleNamespace(_optimized_ast=None)
        analyzer = PurityAnalyzer(template_resolver=lambda n: fake_tpl)
        node = Include(L, C, template=Const(L, C, value="partial.html"))
        assert analyzer.analyze(node) == "unknown"

    def test_include_non_string_const(self) -> None:
        analyzer = PurityAnalyzer(template_resolver=lambda n: None)
        node = Include(L, C, template=Const(L, C, value=42))
        assert analyzer.analyze(node) == "unknown"


# ---------------------------------------------------------------------------
# Impurity propagation
# ---------------------------------------------------------------------------


class TestImpurityPropagation:
    @pytest.fixture
    def analyzer(self) -> PurityAnalyzer:
        return PurityAnalyzer()

    def test_impure_in_for_body(self, analyzer: PurityAnalyzer) -> None:
        impure = Output(L, C, expr=Filter(L, C, value=_name_x, name="shuffle"))
        node = For(L, C, target=_name_x, iter=_name_y, body=[_data, impure])
        assert analyzer.analyze(node) == "impure"

    def test_impure_in_block(self, analyzer: PurityAnalyzer) -> None:
        impure = Output(L, C, expr=Filter(L, C, value=_name_x, name="random"))
        node = Block(L, C, name="sidebar", body=[_data, impure])
        assert analyzer.analyze(node) == "impure"

    def test_impure_in_with(self, analyzer: PurityAnalyzer) -> None:
        impure_val = Filter(L, C, value=_name_x, name="random")
        node = With(L, C, targets=[("r", impure_val)], body=[_data])
        assert analyzer.analyze(node) == "impure"

    def test_impure_in_condexpr(self, analyzer: PurityAnalyzer) -> None:
        impure = Filter(L, C, value=_name_x, name="random")
        node = CondExpr(L, C, test=_name_x, if_true=impure, if_false=_const_42)
        assert analyzer.analyze(node) == "impure"

    def test_impure_in_capture(self, analyzer: PurityAnalyzer) -> None:
        """Capture propagates impurity from its body."""
        # An impure node inside the capture body makes the capture impure.
        impure = Output(L, C, expr=Filter(L, C, value=_name_x, name="random"))
        node = Capture(L, C, name="x", body=[impure])
        assert analyzer.analyze(node) == "impure"
