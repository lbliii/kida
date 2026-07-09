"""Tests for the expression-transform partial-evaluation phase."""

from kida import Environment


def _env() -> Environment:
    return Environment(autoescape=False)


class TestPartialBoolOp:
    """BoolOp short-circuits when one operand is statically known."""

    def test_false_and_dynamic(self):
        """false and X → False (short-circuit)."""
        env = _env()
        tmpl = env.from_string(
            "{% if show and has_content %}yes{% else %}no{% end %}",
            static_context={"show": False},
        )
        assert tmpl.render(has_content=True) == "no"

    def test_true_or_dynamic(self):
        """true or X → True (short-circuit)."""
        env = _env()
        tmpl = env.from_string(
            "{% if is_admin or is_guest %}access{% else %}denied{% end %}",
            static_context={"is_admin": True},
        )
        assert tmpl.render(is_guest=False) == "access"

    def test_true_and_dynamic_simplifies(self):
        """true and X → X (true is removed from 'and' chain)."""
        env = _env()
        tmpl = env.from_string(
            "{% if enabled and has_data %}yes{% else %}no{% end %}",
            static_context={"enabled": True},
        )
        assert tmpl.render(has_data=True) == "yes"
        assert tmpl.render(has_data=False) == "no"

    def test_false_or_dynamic_simplifies(self):
        """false or X → X (false is removed from 'or' chain)."""
        env = _env()
        tmpl = env.from_string(
            "{% if disabled or active %}yes{% else %}no{% end %}",
            static_context={"disabled": False},
        )
        assert tmpl.render(active=True) == "yes"
        assert tmpl.render(active=False) == "no"

    def test_mixed_boolop_chain(self):
        """Multiple operands: some static, some dynamic."""
        env = _env()
        tmpl = env.from_string(
            "{% if a and b and c %}yes{% else %}no{% end %}",
            static_context={"a": True, "c": True},
        )
        assert tmpl.render(b=True) == "yes"
        assert tmpl.render(b=False) == "no"


class TestPartialCondExpr:
    """CondExpr collapses when test is statically known."""

    def test_true_test_takes_if_branch(self):
        """{{ X if true else Y }} → X."""
        env = _env()
        tmpl = env.from_string(
            "{{ value if enabled else 'disabled' }}",
            static_context={"enabled": True},
        )
        assert tmpl.render(value="hello") == "hello"

    def test_false_test_takes_else_branch(self):
        """{{ X if false else Y }} → Y."""
        env = _env()
        tmpl = env.from_string(
            "{{ value if enabled else 'disabled' }}",
            static_context={"enabled": False},
        )
        assert tmpl.render(value="hello") == "disabled"

    def test_condexpr_with_static_result(self):
        """Both test and result are static → folds to constant."""
        env = _env()
        tmpl = env.from_string(
            "{{ 'yes' if flag else 'no' }}",
            static_context={"flag": True},
        )
        assert tmpl.render() == "yes"


class TestSubExprBinOp:
    """Tests for BinOp sub-expression simplification."""

    def test_binop_both_static(self):
        """Both operands static — fully folds to Const."""
        env = _env()
        tmpl = env.from_string(
            "{{ site.count + config.offset }}",
            static_context={"site": {"count": 10}, "config": {"offset": 5}},
        )
        assert tmpl.render(site={"count": 10}, config={"offset": 5}) == "15"

    def test_binop_left_static(self):
        """Left operand static, right dynamic — left simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ site.count + dynamic_val }}",
            static_context={"site": {"count": 10}},
        )
        ast = tmpl._optimized_ast
        assert ast is not None
        # The output expr should be a BinOp with Const left
        out = ast.body[0]
        assert type(out).__name__ == "Output"
        binop = out.expr
        assert type(binop).__name__ == "BinOp"
        assert type(binop.left).__name__ == "Const"
        assert binop.left.value == 10

    def test_binop_concat_partial(self):
        """String concat (~) with mixed static/dynamic operands."""
        env = _env()
        tmpl = env.from_string(
            '{{ site.title ~ " | " ~ page_title }}',
            static_context={"site": {"title": "Kida"}},
        )
        assert tmpl.render(site={"title": "Kida"}, page_title="Home") == "Kida | Home"

    def test_binop_concat_ast_simplification(self):
        """Nested ~ BinOps: static sub-tree folds to single Const."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            '{{ site.title ~ " | " ~ page_title }}',
            static_context={"site": {"title": "Kida"}},
        )
        ast = tmpl._optimized_ast
        assert ast is not None
        out = ast.body[0]
        binop = out.expr
        assert type(binop).__name__ == "BinOp"
        # Left should be Const("Kida | ") — inner BinOp fully folded
        assert type(binop.left).__name__ == "Const"
        assert binop.left.value == "Kida | "


class TestSubExprUnaryOp:
    """Tests for UnaryOp sub-expression simplification."""

    def test_unary_not_static(self):
        """Fully static `not` folds to Const."""
        env = _env()
        tmpl = env.from_string(
            "{% if not site.debug %}PROD{% end %}",
            static_context={"site": {"debug": False}},
        )
        assert tmpl.render(site={"debug": False}) == "PROD"

    def test_unary_not_dynamic(self):
        """Dynamic operand — not folded but operand preserved."""
        env = _env()
        tmpl = env.from_string(
            "{% if not is_debug %}PROD{% else %}DEBUG{% end %}",
        )
        assert tmpl.render(is_debug=False) == "PROD"
        assert tmpl.render(is_debug=True) == "DEBUG"

    def test_unary_negative_static(self):
        """Unary minus on static value."""
        env = _env()
        tmpl = env.from_string(
            "{{ -config.offset }}",
            static_context={"config": {"offset": 5}},
        )
        assert tmpl.render(config={"offset": 5}) == "-5"


class TestSubExprCompare:
    """Tests for Compare sub-expression simplification."""

    def test_compare_both_static(self):
        """Both sides static — folds to branch elimination."""
        env = _env()
        tmpl = env.from_string(
            "{% if site.count > 5 %}BIG{% else %}SMALL{% end %}",
            static_context={"site": {"count": 10}},
        )
        assert tmpl.render(site={"count": 10}) == "BIG"

    def test_compare_left_static(self):
        """Left side static, right dynamic — left simplified to Const."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{% if site.count > threshold %}BIG{% else %}SMALL{% end %}",
            static_context={"site": {"count": 10}},
        )
        # Can't fully resolve (threshold is dynamic), but left is simplified
        assert tmpl.render(site={"count": 10}, threshold=5) == "BIG"
        assert tmpl.render(site={"count": 10}, threshold=15) == "SMALL"


class TestSubExprConcat:
    """Tests for Concat node sub-expression simplification."""

    def test_concat_all_static(self):
        """All nodes static — fully folds."""
        env = _env()
        tmpl = env.from_string(
            "{{ site.title ~ site.version }}",
            static_context={"site": {"title": "Kida ", "version": "0.3.4"}},
        )
        assert tmpl.render(site={"title": "Kida ", "version": "0.3.4"}) == "Kida 0.3.4"


class TestSubExprFuncCall:
    """Tests for FuncCall sub-expression simplification."""

    def test_funccall_static_args(self):
        """len() with static arg — fully folds."""
        env = _env()
        tmpl = env.from_string(
            "{{ len(items) }}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render(items=[1, 2, 3]) == "3"

    def test_funccall_dynamic_arg(self):
        """len() with dynamic arg — can't fold."""
        env = _env()
        tmpl = env.from_string("{{ len(items) }}")
        assert tmpl.render(items=[1, 2, 3]) == "3"

    def test_funccall_mixed_args(self):
        """FuncCall with mixed static/dynamic args — args simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ range(site.count) }}",
            static_context={"site": {"count": 3}},
        )
        # range(3) with static arg should fold fully
        assert tmpl.render(site={"count": 3}) == "range(0, 3)"


class TestSubExprList:
    """Tests for List sub-expression simplification."""

    def test_list_all_static(self):
        """All items static — folds to Const."""
        env = _env()
        tmpl = env.from_string(
            "{{ [site.title, site.version] }}",
            static_context={"site": {"title": "Kida", "version": "0.3.4"}},
        )
        assert tmpl.render(site={"title": "Kida", "version": "0.3.4"}) == "['Kida', '0.3.4']"

    def test_list_mixed_items(self):
        """Mixed static/dynamic items — static items simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ [site.title, page_name] }}",
            static_context={"site": {"title": "Kida"}},
        )
        ast = tmpl._optimized_ast
        assert ast is not None
        out = ast.body[0]
        list_expr = out.expr
        assert type(list_expr).__name__ == "List"
        assert type(list_expr.items[0]).__name__ == "Const"
        assert list_expr.items[0].value == "Kida"
        assert type(list_expr.items[1]).__name__ == "Name"


class TestSubExprTuple:
    """Tests for Tuple sub-expression simplification."""

    def test_tuple_all_static(self):
        """All items static — folds to Const."""
        env = _env()
        tmpl = env.from_string(
            "{{ (site.title, site.version) }}",
            static_context={"site": {"title": "Kida", "version": "0.3.4"}},
        )
        assert tmpl.render(site={"title": "Kida", "version": "0.3.4"}) == "('Kida', '0.3.4')"

    def test_tuple_mixed_items(self):
        """Mixed static/dynamic — static items simplified to Const."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ (site.title, page_name) }}",
            static_context={"site": {"title": "Kida"}},
        )
        ast = tmpl._optimized_ast
        assert ast is not None
        out = ast.body[0]
        tup_expr = out.expr
        assert type(tup_expr).__name__ == "Tuple"
        assert type(tup_expr.items[0]).__name__ == "Const"
        assert tup_expr.items[0].value == "Kida"
        assert type(tup_expr.items[1]).__name__ == "Name"


class TestSubExprDict:
    """Tests for Dict sub-expression simplification."""

    def test_dict_all_static(self):
        """All keys/values static — folds to Const."""
        env = _env()
        tmpl = env.from_string(
            '{{ {"title": site.title, "version": site.version} }}',
            static_context={"site": {"title": "Kida", "version": "0.3.4"}},
        )
        result = tmpl.render(site={"title": "Kida", "version": "0.3.4"})
        assert "'title': 'Kida'" in result
        assert "'version': '0.3.4'" in result

    def test_dict_mixed_values(self):
        """Mixed static/dynamic values — static values simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            '{{ {"title": site.title, "author": page_author} }}',
            static_context={"site": {"title": "Kida"}},
        )
        ast = tmpl._optimized_ast
        assert ast is not None
        out = ast.body[0]
        dict_expr = out.expr
        assert type(dict_expr).__name__ == "Dict"
        # First value (site.title) should be Const
        assert type(dict_expr.values[0]).__name__ == "Const"
        assert dict_expr.values[0].value == "Kida"
        # Second value (page_author) should be Name
        assert type(dict_expr.values[1]).__name__ == "Name"


class TestSubExprMarkSafe:
    """Tests for MarkSafe sub-expression simplification."""

    def test_marksafe_static(self):
        """Static MarkSafe — fully folds."""
        env = Environment(autoescape=True, preserve_ast=True)
        tmpl = env.from_string(
            "{{ site.html | safe }}",
            static_context={"site": {"html": "<b>Bold</b>"}},
        )
        assert tmpl.render(site={"html": "<b>Bold</b>"}) == "<b>Bold</b>"


class TestSubExprFilterPipeline:
    """Tests for Filter/Pipeline sub-expression simplification."""

    def test_filter_static_value(self):
        """Static value through filter — fully folds."""
        env = _env()
        tmpl = env.from_string(
            "{{ site.title | upper }}",
            static_context={"site": {"title": "kida"}},
        )
        assert tmpl.render(site={"title": "kida"}) == "KIDA"

    def test_filter_dynamic_value_preserved(self):
        """Dynamic value through filter — preserved."""
        env = _env()
        tmpl = env.from_string("{{ name | upper }}")
        assert tmpl.render(name="kida") == "KIDA"


class TestBoolOpSimplification:
    """Partial simplification of boolean operators."""

    def test_and_short_circuit_false(self):
        """false and dynamic → false."""
        env = _env()
        tmpl = env.from_string(
            "{% if flag and other %}yes{% else %}no{% end %}",
            static_context={"flag": False},
        )
        assert tmpl.render(other=True) == "no"

    def test_or_short_circuit_true(self):
        """true or dynamic → true."""
        env = _env()
        tmpl = env.from_string(
            "{% if flag or other %}yes{% else %}no{% end %}",
            static_context={"flag": True},
        )
        assert tmpl.render(other=False) == "yes"

    def test_and_truthy_static_filters_out(self):
        """true and dynamic → dynamic (truthy static operand filtered)."""
        env = _env()
        tmpl = env.from_string(
            "{% if flag and other %}yes{% else %}no{% end %}",
            static_context={"flag": True},
        )
        assert tmpl.render(other=True) == "yes"
        assert tmpl.render(other=False) == "no"

    def test_or_falsy_static_filters_out(self):
        """false or dynamic → dynamic (falsy static operand filtered)."""
        env = _env()
        tmpl = env.from_string(
            "{% if flag or other %}yes{% else %}no{% end %}",
            static_context={"flag": False},
        )
        assert tmpl.render(other=True) == "yes"
        assert tmpl.render(other=False) == "no"

    def test_all_static_and_non_terminating(self):
        """All operands static and truthy in 'and' → last value."""
        env = _env()
        tmpl = env.from_string(
            "{% if a and b and c %}yes{% end %}",
            static_context={"a": 1, "b": 2, "c": 3},
        )
        assert tmpl.render() == "yes"

    def test_mixed_boolop_partial_simplification(self):
        """Some static, some dynamic — produces simplified BoolOp."""
        env = _env()
        tmpl = env.from_string(
            "{% if a and b and c %}yes{% else %}no{% end %}",
            static_context={"a": True, "b": True},
        )
        assert tmpl.render(c=True) == "yes"
        assert tmpl.render(c=False) == "no"


class TestCondExprSimplification:
    """Ternary expression simplification at compile time."""

    def test_condexpr_static_test_true(self):
        """Static true test → evaluates if_true branch."""
        env = _env()
        tmpl = env.from_string(
            "{{ 'yes' if flag else 'no' }}",
            static_context={"flag": True},
        )
        assert tmpl.render() == "yes"

    def test_condexpr_static_test_false(self):
        """Static false test → evaluates if_false branch."""
        env = _env()
        tmpl = env.from_string(
            "{{ 'yes' if flag else 'no' }}",
            static_context={"flag": False},
        )
        assert tmpl.render() == "no"

    def test_condexpr_dynamic_winner(self):
        """Static test, dynamic winning branch → preserves winner expr."""
        env = _env()
        tmpl = env.from_string(
            "{{ name if flag else 'anonymous' }}",
            static_context={"flag": True},
        )
        assert tmpl.render(name="Alice") == "Alice"


class TestTransformExprGetattr:
    """Getattr partial simplification — obj changes but attr access unresolved."""

    def test_getattr_partial_obj(self):
        """Getattr where obj sub-expr changes but full eval fails."""
        # Opt into lenient mode: the test's intent is that the partial evaluator
        # simplifies the static sub-expression even when the full getattr misses.
        # Under strict mode the missing attribute access raises; lenient mode
        # lets us observe the rendered output.
        env = Environment(autoescape=False, preserve_ast=True, strict_undefined=False)
        tmpl = env.from_string(
            "{{ (site.title ~ x).attr }}",
            static_context={"site": {"title": "Hi"}},
        )
        # site.title resolves, but the getattr on the computed string doesn't.
        # The optimizer can still simplify the static sub-expression.
        # At runtime, string concatenation produces "HiLo" and .attr is empty.
        assert tmpl.render(site={"title": "Hi"}, x="Lo") == ""


class TestTransformExprGetitem:
    """Getitem partial simplification."""

    def test_getitem_partial_key(self):
        """Getitem where key sub-expr changes but full eval fails."""
        env = _env()
        tmpl = env.from_string(
            "{{ items[idx] }}",
            static_context={"items": {"a": 1, "b": 2}},
        )
        assert tmpl.render(items={"a": 1, "b": 2}, idx="a") == "1"


class TestTransformExprNullCoalesce:
    """NullCoalesce partial simplification."""

    def test_null_coalesce_dynamic_both(self):
        """Both sides dynamic — preserved but sub-exprs walked."""
        env = _env()
        tmpl = env.from_string("{{ a ?? b }}")
        assert tmpl.render(a=None, b="fallback") == "fallback"

    def test_null_coalesce_partial_right(self):
        """Left dynamic, right static — right side simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ x ?? site.default }}",
            static_context={"site": {"default": "none"}},
        )
        assert tmpl.render(x=None, site={"default": "none"}) == "none"


class TestTransformExprMarkSafe:
    """MarkSafe partial simplification."""

    def test_marksafe_dynamic_inner(self):
        """Dynamic value through | safe — inner expression walked."""
        env = _env()
        tmpl = env.from_string("{{ name | safe }}")
        assert tmpl.render(name="<b>hi</b>") == "<b>hi</b>"


class TestTransformExprFilter:
    """Filter partial simplification — value changes but filter unresolved."""

    def test_filter_partial_value(self):
        """Static value through impure filter — value simplified, filter kept."""
        env = _env()
        tmpl = env.from_string(
            "{{ name | upper }}",
        )
        assert tmpl.render(name="kida") == "KIDA"


class TestTransformExprPipeline:
    """Pipeline partial simplification."""

    def test_pipeline_partial_value(self):
        """Pipeline with dynamic value — value simplified."""
        env = _env()
        tmpl = env.from_string("{{ name |> upper |> lower }}")
        assert tmpl.render(name="KIDA") == "kida"


class TestTransformExprUnaryOp:
    """UnaryOp partial simplification — operand changes."""

    def test_unary_not_partial(self):
        """Not with partially-simplifiable operand."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{% if not (a and b) %}yes{% else %}no{% end %}",
            static_context={"a": True},
        )
        ast = tmpl._optimized_ast
        assert ast is not None
        assert tmpl.render(a=True, b=False) == "yes"


class TestTransformExprCompare:
    """Compare partial simplification — operands change."""

    def test_compare_partial_operand(self):
        """Left static, right dynamic — left simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{% if site.count > threshold %}big{% else %}small{% end %}",
            static_context={"site": {"count": 100}},
        )
        assert tmpl.render(site={"count": 100}, threshold=50) == "big"
        assert tmpl.render(site={"count": 100}, threshold=200) == "small"


class TestTransformExprConcat:
    """Concat partial simplification — some nodes change."""

    def test_concat_partial_nodes(self):
        """Some concat nodes static, some dynamic — partial simplification."""
        env = _env()
        tmpl = env.from_string(
            "{{ first ~ middle ~ last }}",
            static_context={"first": "A"},
        )
        assert tmpl.render(first="A", middle="B", last="C") == "ABC"


class TestTransformExprFuncCall:
    """FuncCall partial simplification — some args change."""

    def test_funccall_partial_args(self):
        """Func call with mix of static and dynamic args."""
        env = _env()
        tmpl = env.from_string(
            "{{ range(start, stop) | list }}",
            static_context={"start": 0},
        )
        assert tmpl.render(start=0, stop=3) == "[0, 1, 2]"


class TestTransformExprList:
    """List literal partial simplification."""

    def test_list_partial_items(self):
        """List with mix of static and dynamic items."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ [site.x, dynamic] }}",
            static_context={"site": {"x": 1}},
        )
        assert tmpl.render(site={"x": 1}, dynamic=2) == "[1, 2]"


class TestTransformExprTuple:
    """Tuple literal partial simplification."""

    def test_tuple_partial_items(self):
        """Tuple with mix of static and dynamic items."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ (site.x, dynamic) }}",
            static_context={"site": {"x": 1}},
        )
        assert tmpl.render(site={"x": 1}, dynamic=2) == "(1, 2)"


class TestTransformExprDict:
    """Dict literal partial simplification."""

    def test_dict_partial_values(self):
        """Dict with mix of static and dynamic values."""
        env = _env()
        tmpl = env.from_string(
            '{{ {"a": site.x, "b": dynamic} }}',
            static_context={"site": {"x": 1}},
        )
        result = tmpl.render(site={"x": 1}, dynamic=2)
        assert "'a': 1" in result
        assert "'b': 2" in result


class TestBoolOpEdgeCases:
    """Additional BoolOp simplification paths."""

    def test_boolop_fully_resolves(self):
        """All operands static — fully folds to Const."""
        env = _env()
        tmpl = env.from_string(
            "{% if a and b %}yes{% end %}",
            static_context={"a": True, "b": True},
        )
        assert tmpl.render() == "yes"

    def test_boolop_or_all_falsy_static(self):
        """All operands falsy in 'or' — returns last value."""
        env = _env()
        tmpl = env.from_string(
            "{% if a or b or c %}yes{% else %}no{% end %}",
            static_context={"a": 0, "b": False, "c": ""},
        )
        assert tmpl.render() == "no"

    def test_boolop_reduced_to_single(self):
        """After filtering static operands, only one remains."""
        env = _env()
        tmpl = env.from_string(
            "{% if a and b %}yes{% else %}no{% end %}",
            static_context={"a": True},
        )
        # a is truthy → filtered out, leaving just b
        assert tmpl.render(b=True) == "yes"
        assert tmpl.render(b=False) == "no"

    def test_boolop_new_node_fewer_operands(self):
        """Multiple remaining operands after simplification → new BoolOp."""
        env = _env()
        tmpl = env.from_string(
            "{% if a and b and c and d %}yes{% else %}no{% end %}",
            static_context={"a": True, "c": True},
        )
        assert tmpl.render(a=True, b=True, c=True, d=True) == "yes"
        assert tmpl.render(a=True, b=True, c=True, d=False) == "no"


class TestCondExprEdgeCases:
    """CondExpr partial simplification edge cases."""

    def test_condexpr_winner_fully_resolves(self):
        """Winner branch fully resolves to Const."""
        env = _env()
        tmpl = env.from_string(
            "{{ site.title if flag else 'anon' }}",
            static_context={"flag": True, "site": {"title": "Kida"}},
        )
        assert tmpl.render() == "Kida"

    def test_condexpr_winner_dynamic(self):
        """Winner branch is dynamic — returned as-is after transform."""
        env = _env()
        tmpl = env.from_string(
            "{{ name if flag else 'anon' }}",
            static_context={"flag": True},
        )
        assert tmpl.render(name="Alice") == "Alice"


class TestTransformExprChangedBranches:
    """Tests that hit the 'changed' return branches in _transform_expr."""

    def test_marksafe_inner_changed(self):
        """MarkSafe with partially-simplifiable inner expression."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ (site.prefix ~ name) | safe }}",
            static_context={"site": {"prefix": "Dr. "}},
        )
        assert tmpl.render(site={"prefix": "Dr. "}, name="Smith") == "Dr. Smith"

    def test_concat_nodes_changed(self):
        """Concat where sub-nodes are partially simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ site.a ~ dynamic ~ site.b }}",
            static_context={"site": {"a": "X", "b": "Z"}},
        )
        assert tmpl.render(site={"a": "X", "b": "Z"}, dynamic="Y") == "XYZ"

    def test_list_items_changed(self):
        """List with sub-items that get simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ [site.a, x, site.b] }}",
            static_context={"site": {"a": 1, "b": 3}},
        )
        assert tmpl.render(site={"a": 1, "b": 3}, x=2) == "[1, 2, 3]"

    def test_tuple_items_changed(self):
        """Tuple with sub-items that get simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ (site.a, x, site.b) }}",
            static_context={"site": {"a": 1, "b": 3}},
        )
        assert tmpl.render(site={"a": 1, "b": 3}, x=2) == "(1, 2, 3)"

    def test_dict_values_changed(self):
        """Dict with values that get simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            '{{ {"x": site.a, "y": val} }}',
            static_context={"site": {"a": 10}},
        )
        result = tmpl.render(site={"a": 10}, val=20)
        assert "'x': 10" in result
        assert "'y': 20" in result

    def test_unaryop_operand_changed(self):
        """UnaryOp where operand is partially simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{% if not (site.flag and x) %}yes{% else %}no{% end %}",
            static_context={"site": {"flag": True}},
        )
        assert tmpl.render(site={"flag": True}, x=False) == "yes"

    def test_compare_operands_changed(self):
        """Compare where operands are partially simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{% if site.min < val < site.max %}in range{% else %}out{% end %}",
            static_context={"site": {"min": 0, "max": 100}},
        )
        assert tmpl.render(site={"min": 0, "max": 100}, val=50) == "in range"
        assert tmpl.render(site={"min": 0, "max": 100}, val=200) == "out"

    def test_funccall_args_changed(self):
        """FuncCall where some args are partially simplified."""
        env = _env()
        tmpl = env.from_string(
            "{{ range(site.start, n) | list }}",
            static_context={"site": {"start": 0}},
        )
        assert tmpl.render(site={"start": 0}, n=3) == "[0, 1, 2]"

    def test_filter_value_changed(self):
        """Filter where value sub-expr is partially simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ (site.title ~ name) | upper }}",
            static_context={"site": {"title": "Dr "}},
        )
        assert tmpl.render(site={"title": "Dr "}, name="Who") == "DR WHO"

    def test_pipeline_value_changed(self):
        """Pipeline where value sub-expr is partially simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ (site.title ~ name) |> upper }}",
            static_context={"site": {"title": "Dr "}},
        )
        assert tmpl.render(site={"title": "Dr "}, name="Who") == "DR WHO"

    def test_getattr_obj_changed(self):
        """Getattr where obj sub-expr is partially simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ items[site.key] }}",
            static_context={"site": {"key": "name"}},
        )
        assert tmpl.render(site={"key": "name"}, items={"name": "Alice"}) == "Alice"

    def test_null_coalesce_sides_changed(self):
        """NullCoalesce where both sides are partially simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            "{{ x ?? site.fallback }}",
            static_context={"site": {"fallback": "default"}},
        )
        assert tmpl.render(x=None, site={"fallback": "default"}) == "default"
