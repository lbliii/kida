"""Tests for compile-time partial evaluation.

Verifies that the PartialEvaluator correctly replaces static expressions
with constants in the template AST, and that the rendered output is
identical whether using partial evaluation or runtime context.

"""

from dataclasses import dataclass

import pytest

from kida import Environment
from kida.exceptions import TemplateSyntaxError


@dataclass(frozen=True, slots=True)
class FakeSite:
    title: str
    url: str
    nav: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FakePage:
    title: str
    slug: str


def _env() -> Environment:
    return Environment(autoescape=False)


class TestBasicPartialEvaluation:
    """Static context values are folded into constants at compile time."""

    def test_simple_variable(self):
        env = _env()
        tmpl = env.from_string(
            "Hello, {{ name }}!",
            static_context={"name": "World"},
        )
        assert tmpl.render() == "Hello, World!"

    def test_attribute_access(self):
        env = _env()
        site = FakeSite(title="My Blog", url="https://example.com", nav=("Home", "About"))
        tmpl = env.from_string(
            "<title>{{ site.title }}</title>",
            static_context={"site": site},
        )
        assert tmpl.render() == "<title>My Blog</title>"

    def test_dict_access(self):
        env = _env()
        tmpl = env.from_string(
            "{{ config.theme }}",
            static_context={"config": {"theme": "dark"}},
        )
        assert tmpl.render() == "dark"

    def test_nested_access(self):
        env = _env()
        ctx = {"site": {"meta": {"author": "Jane"}}}
        tmpl = env.from_string(
            "By {{ site.meta.author }}",
            static_context=ctx,
        )
        assert tmpl.render() == "By Jane"

    def test_subscript_access(self):
        env = _env()
        tmpl = env.from_string(
            '{{ items["key"] }}',
            static_context={"items": {"key": "value"}},
        )
        assert tmpl.render() == "value"

    def test_integer_constant(self):
        env = _env()
        tmpl = env.from_string(
            "Count: {{ count }}",
            static_context={"count": 42},
        )
        assert tmpl.render() == "Count: 42"

    def test_none_value(self):
        env = _env()
        tmpl = env.from_string(
            "Value: {{ val }}",
            static_context={"val": None},
        )
        assert tmpl.render() == "Value: "


class TestNonConstantSafeTypes:
    """Non-constant-safe types (dict, list, etc.) are folded via precomputed constants.

    Regression tests for https://github.com/lbliii/kida/issues/68:
    Python's compile() rejects dict/list/set in ast.Constant nodes.
    The compiler emits these as precomputed module-level bindings (_pc_N).
    """

    def test_let_intermediate_dict(self):
        """{% let s = config.site %} folds dict via precomputed binding."""
        env = _env()
        tmpl = env.from_string(
            "{% let s = config.site %}{{ s.title }}",
            static_context={"config": {"site": {"title": "Test"}}},
        )
        assert tmpl.render() == "Test"

    def test_set_intermediate_dict(self):
        env = _env()
        tmpl = env.from_string(
            "{% set s = config.site %}{{ s.title }}",
            static_context={"config": {"site": {"title": "Test"}}},
        )
        assert tmpl.render() == "Test"

    def test_with_intermediate_dict(self):
        env = _env()
        tmpl = env.from_string(
            "{% with s = config.site %}{{ s.title }}{% endwith %}",
            static_context={"config": {"site": {"title": "Test"}}},
        )
        assert tmpl.render() == "Test"

    def test_nested_dict_leaf_still_folds(self):
        """Scalar leaves of nested dicts should still fold normally."""
        env = _env()
        tmpl = env.from_string(
            "{{ config.site.title }}",
            static_context={"config": {"site": {"title": "Test"}}},
        )
        assert tmpl.render() == "Test"

    def test_list_value_not_folded_to_const(self):
        env = _env()
        tmpl = env.from_string(
            "{% let items = data.tags %}{{ items | join(', ') }}",
            static_context={"data": {"tags": ["a", "b", "c"]}},
        )
        assert tmpl.render() == "a, b, c"

    def test_if_with_dict_truthiness(self):
        """Branch elimination should still work even when the value is a dict."""
        env = _env()
        tmpl = env.from_string(
            "{% if config.fonts %}yes{% else %}no{% endif %}",
            static_context={"config": {"fonts": {"body": "Arial"}}},
        )
        assert tmpl.render() == "yes"

    def test_print_intermediate_dict(self):
        """{{ s }} where s is a dict should render the dict string representation."""
        env = _env()
        tmpl = env.from_string(
            "{% let s = config.site %}{{ s }}",
            static_context={"config": {"site": {"title": "Test"}}},
        )
        assert tmpl.render() == "{'title': 'Test'}"

    def test_list_direct_output(self):
        """Lists folded via precomputed should render correctly."""
        env = _env()
        tmpl = env.from_string(
            "{{ items }}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render() == "[1, 2, 3]"

    def test_bytecode_cache_round_trip(self, tmp_path):
        """Precomputed values survive bytecode cache serialization."""
        from kida.bytecode_cache import BytecodeCache

        cache = BytecodeCache(tmp_path)
        env = Environment(autoescape=False, bytecode_cache=cache)

        # First call: cache miss → compile + cache
        t1 = env.from_string(
            "{% let s = config.site %}{{ s.title }}",
            name="cache_test.html",
            static_context={"config": {"site": {"title": "Cached"}}},
        )
        assert t1.render() == "Cached"

        # Second call: cache hit → load from cache
        t2 = env.from_string(
            "{% let s = config.site %}{{ s.title }}",
            name="cache_test.html",
            static_context={"config": {"site": {"title": "Cached"}}},
        )
        assert t2.render() == "Cached"

    def test_precomputed_not_mutated_across_renders(self):
        """Rendering should not mutate precomputed values."""
        env = _env()
        static = {"items": [1, 2, 3]}
        tmpl = env.from_string(
            "{{ items | join(',') }}",
            static_context=static,
        )
        assert tmpl.render() == "1,2,3"
        assert tmpl.render() == "1,2,3"
        assert static["items"] == [1, 2, 3]


class TestMixedContext:
    """Static and runtime values coexist correctly."""

    def test_static_and_dynamic(self):
        env = _env()
        tmpl = env.from_string(
            "{{ site.title }} - {{ page.title }}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        page = FakePage(title="Hello World", slug="hello")
        result = tmpl.render(page=page)
        assert result == "Blog - Hello World"

    def test_static_in_attribute(self):
        env = _env()
        tmpl = env.from_string(
            '<a href="{{ site.url }}">{{ page.title }}</a>',
            static_context={"site": FakeSite(title="Blog", url="https://example.com", nav=())},
        )
        result = tmpl.render(page=FakePage(title="Index", slug="index"))
        assert result == '<a href="https://example.com">Index</a>'


class TestExpressionEvaluation:
    """Compile-time evaluation of expression operators."""

    def test_string_concatenation(self):
        env = _env()
        tmpl = env.from_string(
            "{{ prefix ~ suffix }}",
            static_context={"prefix": "hello", "suffix": "world"},
        )
        assert tmpl.render() == "helloworld"

    def test_arithmetic(self):
        env = _env()
        tmpl = env.from_string(
            "{{ a + b }}",
            static_context={"a": 10, "b": 20},
        )
        assert tmpl.render() == "30"

    def test_comparison(self):
        env = _env()
        tmpl = env.from_string(
            "{% if threshold > 5 %}high{% end %}",
            static_context={"threshold": 10},
        )
        assert tmpl.render() == "high"

    def test_boolean_and(self):
        env = _env()
        tmpl = env.from_string(
            "{% if a and b %}yes{% end %}",
            static_context={"a": True, "b": True},
        )
        assert tmpl.render() == "yes"

    def test_boolean_or_short_circuit(self):
        env = _env()
        tmpl = env.from_string(
            "{% if a or b %}yes{% else %}no{% end %}",
            static_context={"a": False, "b": False},
        )
        assert tmpl.render() == "no"

    def test_negation(self):
        env = _env()
        tmpl = env.from_string(
            "{% if not flag %}off{% end %}",
            static_context={"flag": False},
        )
        assert tmpl.render() == "off"

    def test_ternary(self):
        env = _env()
        tmpl = env.from_string(
            "{{ 'yes' if enabled else 'no' }}",
            static_context={"enabled": True},
        )
        assert tmpl.render() == "yes"


class TestBranchElimination:
    """Static If/elif/else branches are eliminated at compile time."""

    def test_true_branch(self):
        env = _env()
        tmpl = env.from_string(
            "{% if show_nav %}NAV{% else %}HIDDEN{% end %}",
            static_context={"show_nav": True},
        )
        assert tmpl.render() == "NAV"

    def test_false_branch(self):
        env = _env()
        tmpl = env.from_string(
            "{% if show_nav %}NAV{% else %}HIDDEN{% end %}",
            static_context={"show_nav": False},
        )
        assert tmpl.render() == "HIDDEN"

    def test_false_no_else(self):
        env = _env()
        tmpl = env.from_string(
            "before{% if debug %} DEBUG{% end %} after",
            static_context={"debug": False},
        )
        assert tmpl.render() == "before after"

    def test_elif_branch(self):
        env = _env()
        tmpl = env.from_string(
            "{% if mode == 'a' %}A{% elif mode == 'b' %}B{% else %}C{% end %}",
            static_context={"mode": "b"},
        )
        assert tmpl.render() == "B"


class TestBlockHandling:
    """Partial evaluation works inside template blocks."""

    def test_static_in_block(self):
        env = _env()
        tmpl = env.from_string(
            "{% block title %}{{ site.title }}{% end %}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        assert tmpl.render() == "Blog"


class TestForLoopRecursion:
    """Partial evaluation recurses into for loop bodies."""

    def test_static_inside_loop(self):
        env = _env()
        tmpl = env.from_string(
            "{% for item in items %}{{ site.title }}: {{ item }}; {% end %}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        result = tmpl.render(items=["a", "b"])
        assert result == "Blog: a; Blog: b; "


class TestNoStaticContext:
    """Without static_context, templates work normally."""

    def test_no_static_context(self):
        env = _env()
        tmpl = env.from_string("{{ name }}")
        assert tmpl.render(name="World") == "World"

    def test_empty_static_context(self):
        env = _env()
        tmpl = env.from_string("{{ name }}", static_context={})
        assert tmpl.render(name="World") == "World"


class TestFilterPartialEval:
    """Filter and Pipeline evaluation in partial eval."""

    def test_filter_default(self):
        """{{ site.title | default("x") }} with static_context evaluates."""
        env = _env()
        tmpl = env.from_string(
            "{{ site.title | default('Home') }}",
            static_context={"site": FakeSite(title="My Blog", url="", nav=())},
        )
        assert tmpl.render() == "My Blog"

    def test_filter_default_fallback(self):
        """{{ missing | default("x") }} with static None uses default."""
        env = _env()
        tmpl = env.from_string(
            "{{ val | default('N/A') }}",
            static_context={"val": None},
        )
        assert tmpl.render() == "N/A"

    def test_pipeline_upper(self):
        """{{ site.title | upper }} with static_context evaluates."""
        env = _env()
        tmpl = env.from_string(
            "{{ site.title | upper }}",
            static_context={"site": FakeSite(title="hello", url="", nav=())},
        )
        assert tmpl.render() == "HELLO"

    def test_pipeline_multiple_filters(self):
        """{{ x | default("") | upper }} with static_context evaluates."""
        env = _env()
        tmpl = env.from_string(
            "{{ x | default('fallback') | upper }}",
            static_context={"x": "hello"},
        )
        assert tmpl.render() == "HELLO"

    def test_filter_with_kwargs(self):
        """{{ text | truncate(5) }} with static_context evaluates."""
        env = _env()
        tmpl = env.from_string(
            "{{ text | truncate(5) }}",
            static_context={"text": "hello world"},
        )
        # truncate(5) = first 2 chars + "..." (5 total)
        assert tmpl.render() == "he..."


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_missing_attribute_stays_dynamic(self):
        """If static context doesn't have the attr, expression stays dynamic."""
        env = _env()
        tmpl = env.from_string(
            "{{ site.title }} {{ page.title }}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        # page is dynamic, site.title is static
        result = tmpl.render(page=FakePage(title="Post", slug="post"))
        assert result == "Blog Post"

    def test_data_merging(self):
        """Adjacent static Data nodes are merged."""
        env = _env()
        tmpl = env.from_string(
            "{{ a }}{{ b }}{{ c }}",
            static_context={"a": "x", "b": "y", "c": "z"},
        )
        assert tmpl.render() == "xyz"

    def test_numeric_types_preserved(self):
        env = _env()
        tmpl = env.from_string(
            "{{ x * 2 }}",
            static_context={"x": 21},
        )
        assert tmpl.render() == "42"


class TestExtendedFilterFolding:
    """Filters from PURE_FILTERS_ALL (not just COALESCEABLE) fold at compile time."""

    def test_sort_filter(self):
        env = _env()
        tmpl = env.from_string(
            "{{ items | sort | join(', ') }}",
            static_context={"items": [3, 1, 2]},
        )
        assert tmpl.render() == "1, 2, 3"

    def test_reverse_filter(self):
        env = _env()
        tmpl = env.from_string(
            "{{ items | reverse | join(', ') }}",
            static_context={"items": ["a", "b", "c"]},
        )
        assert tmpl.render() == "c, b, a"

    def test_abs_filter(self):
        env = _env()
        tmpl = env.from_string(
            "{{ val | abs }}",
            static_context={"val": -42},
        )
        assert tmpl.render() == "42"

    def test_round_filter(self):
        env = _env()
        tmpl = env.from_string(
            "{{ val | round(1) }}",
            static_context={"val": 3.14159},
        )
        assert tmpl.render() == "3.1"

    def test_replace_filter(self):
        env = _env()
        tmpl = env.from_string(
            "{{ text | replace('world', 'kida') }}",
            static_context={"text": "hello world"},
        )
        assert tmpl.render() == "hello kida"

    def test_wordcount_filter(self):
        env = _env()
        tmpl = env.from_string(
            "{{ text | wordcount }}",
            static_context={"text": "one two three"},
        )
        assert tmpl.render() == "3"

    def test_chained_extended_filters(self):
        """Multiple PURE_FILTERS_ALL filters chain correctly."""
        env = _env()
        tmpl = env.from_string(
            "{{ items | sort | reverse | first }}",
            static_context={"items": [1, 3, 2]},
        )
        assert tmpl.render() == "3"


class TestNullCoalescePartialEval:
    """Null coalescing (??) is evaluated at compile time."""

    def test_null_coalesce_left_defined(self):
        env = _env()
        tmpl = env.from_string(
            '{{ name ?? "Anonymous" }}',
            static_context={"name": "Alice"},
        )
        assert tmpl.render() == "Alice"

    def test_null_coalesce_left_none(self):
        env = _env()
        tmpl = env.from_string(
            '{{ name ?? "Anonymous" }}',
            static_context={"name": None},
        )
        assert tmpl.render() == "Anonymous"

    def test_null_coalesce_mixed_context(self):
        """Static left, dynamic right — left wins, right never evaluated."""
        env = _env()
        tmpl = env.from_string(
            "{{ title ?? fallback }}",
            static_context={"title": "Static Title"},
        )
        assert tmpl.render(fallback="Dynamic") == "Static Title"


class TestSafePipelinePartialEval:
    """Safe pipeline (?|>) None-propagation at compile time."""

    def test_safe_pipeline_with_value(self):
        env = _env()
        tmpl = env.from_string(
            "{{ name ?|> upper ?|> trim }}",
            static_context={"name": " hello "},
        )
        assert tmpl.render() == "HELLO"

    def test_safe_pipeline_none_propagates(self):
        env = _env()
        tmpl = env.from_string(
            '{{ name ?|> upper ?? "N/A" }}',
            static_context={"name": None},
        )
        assert tmpl.render() == "N/A"


class TestOptionalFilterPartialEval:
    """Optional filter (?|) skips filter when value is None."""

    def test_optional_filter_with_value(self):
        env = _env()
        tmpl = env.from_string(
            "{{ name ?| upper }}",
            static_context={"name": "hello"},
        )
        assert tmpl.render() == "HELLO"

    def test_optional_filter_none_passthrough(self):
        env = _env()
        tmpl = env.from_string(
            '{{ name ?| upper ?? "N/A" }}',
            static_context={"name": None},
        )
        assert tmpl.render() == "N/A"


class TestMarkSafePartialEval:
    """MarkSafe (| safe) is unwrapped for compile-time evaluation."""

    def test_safe_filter_folds(self):
        env = Environment(autoescape=True)
        tmpl = env.from_string(
            "{{ content | safe }}",
            static_context={"content": "<b>bold</b>"},
        )
        assert tmpl.render() == "<b>bold</b>"


def _count_nodes_by_type(nodes, node_types):
    """Count AST nodes matching given types (recursive)."""
    from kida.nodes import Block, CallBlock, Def, For, If, SlotBlock

    count = 0
    for node in nodes:
        if isinstance(node, tuple(node_types)):
            count += 1
        # Recurse into container nodes
        if hasattr(node, "body"):
            count += _count_nodes_by_type(node.body, node_types)
        if isinstance(node, If):
            for _, branch_body in node.elif_:
                count += _count_nodes_by_type(branch_body, node_types)
            if node.else_:
                count += _count_nodes_by_type(node.else_, node_types)
        if isinstance(node, For) and node.empty:
            count += _count_nodes_by_type(node.empty, node_types)
        if isinstance(node, Def):
            count += _count_nodes_by_type(node.body, node_types)
        if isinstance(node, (Block, SlotBlock)):
            count += _count_nodes_by_type(node.body, node_types)
        if isinstance(node, CallBlock):
            for slot_body in node.slots.values():
                count += _count_nodes_by_type(slot_body, node_types)
    return count


class TestAssignmentPropagation:
    """Set/Let bindings propagate through static context."""

    def test_set_propagates_static_value(self):
        """{% set x = config.theme %} makes x available for folding."""
        env = _env()
        tmpl = env.from_string(
            "{% set theme = config.theme %}Theme: {{ theme }}",
            static_context={"config": {"theme": "dark"}},
        )
        assert tmpl.render() == "Theme: dark"

    def test_set_chain_propagates(self):
        """Multiple sets chain: each sees the previous."""
        env = _env()
        tmpl = env.from_string(
            "{% set a = x %}{% set b = a %}{{ b }}",
            static_context={"x": "hello"},
        )
        assert tmpl.render() == "hello"

    def test_set_with_filter_propagates(self):
        """{% set label = name | upper %} propagates the filtered value."""
        env = _env()
        tmpl = env.from_string(
            "{% set label = name | upper %}Label: {{ label }}",
            static_context={"name": "hello"},
        )
        assert tmpl.render() == "Label: HELLO"

    def test_let_propagates_static_value(self):
        """{% let x = config.theme %} makes x available for folding."""
        env = _env()
        tmpl = env.from_string(
            "{% let theme = config.theme %}Theme: {{ theme }}",
            static_context={"config": {"theme": "dark"}},
        )
        assert tmpl.render() == "Theme: dark"

    def test_dynamic_set_does_not_propagate(self):
        """{% set x = dynamic_val %} with no static value stays dynamic."""
        env = _env()
        tmpl = env.from_string(
            "{% set label = user_name %}{{ label }}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(user_name="Alice") == "Alice"

    def test_coalesce_set_respects_existing(self):
        """{% set x ??= fallback %} doesn't overwrite existing value."""
        env = _env()
        tmpl = env.from_string(
            "{% set x ??= 'fallback' %}{{ x }}",
            static_context={"x": "original"},
        )
        assert tmpl.render() == "original"

    def test_coalesce_set_fills_none(self):
        """{% set x ??= fallback %} fills when existing is None."""
        env = _env()
        tmpl = env.from_string(
            '{% set x ??= "fallback" %}{{ x }}',
            static_context={"x": None},
        )
        assert tmpl.render() == "fallback"


class TestListDictTupleEval:
    """List, Dict, and Tuple literals are evaluated at compile time."""

    def test_list_literal(self):
        env = _env()
        tmpl = env.from_string(
            "{{ [1, 2, 3] | join(', ') }}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == "1, 2, 3"

    def test_dict_literal(self):
        env = _env()
        tmpl = env.from_string(
            '{{ {"a": 1, "b": 2} | length }}',
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == "2"

    def test_tuple_literal(self):
        env = _env()
        tmpl = env.from_string(
            "{{ (1, 2, 3) | first }}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == "1"

    def test_list_with_static_vars(self):
        env = _env()
        tmpl = env.from_string(
            "{{ [a, b, c] | join('-') }}",
            static_context={"a": "x", "b": "y", "c": "z"},
        )
        assert tmpl.render() == "x-y-z"


class TestSafeBuiltinEvaluation:
    """Safe builtins (range, len, sorted, etc.) evaluate at compile time."""

    def test_len_of_static_list(self):
        env = _env()
        tmpl = env.from_string(
            "{{ len(items) }}",
            static_context={"items": [1, 2, 3, 4, 5]},
        )
        assert tmpl.render() == "5"

    def test_range_function(self):
        env = _env()
        tmpl = env.from_string(
            "{% for x in range(3) %}{{ x }}{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == "012"

    def test_range_with_start_stop(self):
        env = _env()
        tmpl = env.from_string(
            "{% for x in range(1, 4) %}{{ x }}{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == "123"

    def test_sorted_function(self):
        env = _env()
        tmpl = env.from_string(
            "{{ sorted(items) | join(', ') }}",
            static_context={"items": [3, 1, 2]},
        )
        assert tmpl.render() == "1, 2, 3"

    def test_min_max_functions(self):
        env = _env()
        tmpl = env.from_string(
            "min={{ min(items) }} max={{ max(items) }}",
            static_context={"items": [5, 2, 8, 1]},
        )
        assert tmpl.render() == "min=1 max=8"

    def test_sum_function(self):
        env = _env()
        tmpl = env.from_string(
            "{{ sum(items) }}",
            static_context={"items": [10, 20, 30]},
        )
        assert tmpl.render() == "60"

    def test_abs_function(self):
        env = _env()
        tmpl = env.from_string(
            "{{ abs(val) }}",
            static_context={"val": -42},
        )
        assert tmpl.render() == "42"

    def test_str_int_float_functions(self):
        env = _env()
        tmpl = env.from_string(
            '{{ int("42") }} {{ float("3.14") }} {{ str(100) }}',
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == "42 3.14 100"

    def test_range_dos_protection(self):
        """range(huge) doesn't blow up — falls back to runtime."""
        env = _env()
        tmpl = env.from_string(
            "{{ len(range(1000000)) }}",
            static_context={"_placeholder": True},
        )
        # Falls back to runtime, should still work
        assert tmpl.render() == "1000000"

    def test_dynamic_args_not_evaluated(self):
        """Builtins with dynamic args stay as runtime calls."""
        env = _env()
        tmpl = env.from_string(
            "{{ len(items) }}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(items=[1, 2, 3]) == "3"

    def test_range_literal(self):
        """Range literal (1..5) evaluates at compile time."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in 1..3 %}{{ x }}{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == "123"


class TestOptimizationMetrics:
    """Measure AST node reduction from partial evaluation."""

    def test_static_vars_fold_to_data(self):
        """Static variable expressions become Data nodes."""
        from kida.nodes import Data, Output

        env = _env()
        # Without static context: Output nodes for each {{ }}
        tpl_dynamic = env.from_string("{{ a }} {{ b }} {{ c }}")
        output_count = _count_nodes_by_type(tpl_dynamic._optimized_ast.body, [Output])
        assert output_count >= 3

        # With static context: folded to Data nodes
        tpl_static = env.from_string(
            "{{ a }} {{ b }} {{ c }}",
            static_context={"a": "x", "b": "y", "c": "z"},
        )
        data_count = _count_nodes_by_type(tpl_static._optimized_ast.body, [Data])
        output_count_after = _count_nodes_by_type(tpl_static._optimized_ast.body, [Output])
        # All outputs should be gone, replaced by Data
        assert output_count_after == 0
        assert data_count >= 1  # May be merged into fewer Data nodes

    def test_dead_branch_elimination_reduces_nodes(self):
        """False branches are eliminated entirely."""
        from kida.nodes import If

        env = _env()
        tpl = env.from_string(
            "{% if false %}DEAD1{% end %}{% if false %}DEAD2{% end %}LIVE",
        )
        if_count = _count_nodes_by_type(tpl._optimized_ast.body, [If])
        assert if_count == 0  # Both If nodes eliminated

    def test_filter_folding_reduces_outputs(self):
        """Static filters fold to Data, eliminating runtime filter calls."""
        from kida.nodes import Data, Output

        env = _env()
        tpl = env.from_string(
            "{{ name | upper }} {{ val | abs }}",
            static_context={"name": "hello", "val": -42},
        )
        output_count = _count_nodes_by_type(tpl._optimized_ast.body, [Output])
        data_count = _count_nodes_by_type(tpl._optimized_ast.body, [Data])
        assert output_count == 0
        assert data_count >= 1


class TestUserPureFilters:
    """Test that user-defined filters marked with @pure are folded at compile time."""

    def test_pure_decorator_marks_function(self):
        """The @pure decorator sets the _kida_pure attribute."""
        from kida import pure

        @pure
        def my_filter(value):
            return value.strip()

        assert getattr(my_filter, "_kida_pure", False) is True

    def test_pure_filter_via_add_filter(self):
        """A @pure filter registered via add_filter is folded at compile time."""
        from kida import pure
        from kida.nodes import Data

        @pure
        def clean(value):
            return value.strip().lower()

        env = _env()
        env.add_filter("clean", clean)
        tpl = env.from_string(
            "{{ name | clean }}",
            static_context={"name": "  HELLO  "},
        )
        # Should fold to "hello" at compile time
        assert tpl.render(name="  HELLO  ") == "hello"
        data_count = _count_nodes_by_type(tpl._optimized_ast.body, [Data])
        assert data_count >= 1

    def test_pure_filter_via_filters_registry(self):
        """A @pure filter registered via env.filters[name] = func is folded."""
        from kida import pure
        from kida.nodes import Data

        @pure
        def shout(value):
            return value.upper() + "!"

        env = _env()
        env.filters["shout"] = shout
        tpl = env.from_string(
            "{{ name | shout }}",
            static_context={"name": "hello"},
        )
        assert tpl.render(name="hello") == "HELLO!"
        data_count = _count_nodes_by_type(tpl._optimized_ast.body, [Data])
        assert data_count >= 1

    def test_non_pure_filter_not_folded(self):
        """A filter without @pure is NOT folded at compile time."""
        from kida.nodes import Output

        def not_pure(value):
            return value.upper()

        env = _env()
        env.add_filter("not_pure", not_pure)
        tpl = env.from_string(
            "{{ name | not_pure }}",
            static_context={"name": "hello"},
        )
        # Should NOT fold — filter is not in pure set
        assert tpl.render(name="hello") == "HELLO"
        output_count = _count_nodes_by_type(tpl._optimized_ast.body, [Output])
        assert output_count >= 1  # Still has an Output node (not folded to Data)

    def test_pure_filter_with_args(self):
        """A @pure filter with extra arguments is folded when all args are static."""
        from kida import pure
        from kida.nodes import Data

        @pure
        def repeat(value, times=2):
            return value * times

        env = _env()
        env.add_filter("repeat", repeat)
        tpl = env.from_string(
            "{{ word | repeat(3) }}",
            static_context={"word": "ha"},
        )
        assert tpl.render(word="ha") == "hahaha"
        data_count = _count_nodes_by_type(tpl._optimized_ast.body, [Data])
        assert data_count >= 1

    def test_pure_filter_preserves_function_behavior(self):
        """The @pure decorator does not alter the function's behavior."""
        from kida import pure

        @pure
        def add_prefix(value, prefix="pre"):
            return f"{prefix}_{value}"

        assert add_prefix("test") == "pre_test"
        assert add_prefix("test", prefix="x") == "x_test"
        assert add_prefix.__name__ == "add_prefix"


class TestWithPropagation:
    """{% with %} blocks propagate static bindings into their body."""

    def test_simple_with_propagation(self):
        env = _env()
        tmpl = env.from_string(
            "{% with title = site.title %}{{ title }}{% end %}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        assert tmpl.render() == "Blog"

    def test_with_multiple_bindings(self):
        env = _env()
        site = FakeSite(title="Blog", url="https://example.com", nav=())
        tmpl = env.from_string(
            "{% with title = site.title, url = site.url %}{{ title }} at {{ url }}{% end %}",
            static_context={"site": site},
        )
        assert tmpl.render() == "Blog at https://example.com"

    def test_with_mixed_static_dynamic(self):
        """Static bindings resolve, dynamic bindings pass through."""
        env = _env()
        tmpl = env.from_string(
            "{% with title = site.title, slug = page.slug %}{{ title }}: {{ slug }}{% end %}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        assert tmpl.render(page=FakePage(title="Post", slug="my-post")) == "Blog: my-post"

    def test_with_nested(self):
        """Nested {% with %} blocks propagate correctly."""
        env = _env()
        tmpl = env.from_string(
            "{% with a = site.title %}{% with b = site.url %}{{ a }} {{ b }}{% end %}{% end %}",
            static_context={"site": FakeSite(title="Blog", url="https://x.com", nav=())},
        )
        assert tmpl.render() == "Blog https://x.com"

    def test_with_enables_branch_elimination(self):
        """With-bound values enable if-branch elimination."""
        env = _env()
        tmpl = env.from_string(
            "{% with debug = config.debug %}{% if debug %}DEBUG{% else %}PROD{% end %}{% end %}",
            static_context={"config": {"debug": False}},
        )
        assert tmpl.render() == "PROD"

    def test_with_inside_for_loop(self):
        """With blocks inside for loops with static iterables."""
        env = _env()
        tmpl = env.from_string(
            "{% for item in items %}{% with name = item.name %}{{ name }} {% end %}{% end %}",
            static_context={"items": [{"name": "A"}, {"name": "B"}]},
        )
        assert tmpl.render() == "A B "

    def test_with_binding_value_simplified(self):
        """Even when binding can't fully resolve, value expr is simplified."""
        env = _env()
        tmpl = env.from_string(
            "{% with x = dynamic_val %}{{ x }}{% end %}",
            static_context={},
        )
        # dynamic_val not in static context — with block preserved as-is
        assert tmpl.render(dynamic_val="hello") == "hello"

    def test_with_propagation_does_not_leak(self):
        """With-bound variables don't leak into outer scope."""
        env = _env()
        tmpl = env.from_string(
            "{% with x = site.title %}{{ x }}{% end %}-{{ fallback }}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        assert tmpl.render(fallback="end") == "Blog-end"


class TestTestExpressionEvaluation:
    """Test expressions (is defined, is odd, etc.) fold at compile time."""

    def test_is_defined_present(self):
        env = _env()
        tmpl = env.from_string(
            "{% if site is defined %}YES{% else %}NO{% end %}",
            static_context={"site": "exists"},
        )
        assert tmpl.render() == "YES"

    def test_is_defined_missing(self):
        env = _env()
        tmpl = env.from_string(
            "{% if missing is defined %}YES{% else %}NO{% end %}",
            static_context={"site": "exists"},
        )
        assert tmpl.render() == "NO"

    def test_is_not_defined(self):
        env = _env()
        tmpl = env.from_string(
            "{% if missing is not defined %}MISSING{% else %}FOUND{% end %}",
            static_context={"site": "exists"},
        )
        assert tmpl.render() == "MISSING"

    def test_is_undefined(self):
        env = _env()
        tmpl = env.from_string(
            "{% if missing is undefined %}UNDEF{% else %}DEF{% end %}",
            static_context={"site": "exists"},
        )
        assert tmpl.render() == "UNDEF"

    def test_is_odd(self):
        env = _env()
        tmpl = env.from_string(
            "{% if count is odd %}ODD{% else %}EVEN{% end %}",
            static_context={"count": 7},
        )
        assert tmpl.render() == "ODD"

    def test_is_even(self):
        env = _env()
        tmpl = env.from_string(
            "{% if count is even %}EVEN{% else %}ODD{% end %}",
            static_context={"count": 4},
        )
        assert tmpl.render() == "EVEN"

    def test_is_not_odd(self):
        env = _env()
        tmpl = env.from_string(
            "{% if count is not odd %}EVEN{% else %}ODD{% end %}",
            static_context={"count": 4},
        )
        assert tmpl.render() == "EVEN"

    def test_is_string(self):
        env = _env()
        tmpl = env.from_string(
            "{% if val is string %}STR{% else %}NOT{% end %}",
            static_context={"val": "hello"},
        )
        assert tmpl.render() == "STR"

    def test_is_number(self):
        env = _env()
        tmpl = env.from_string(
            "{% if val is number %}NUM{% else %}NOT{% end %}",
            static_context={"val": 42},
        )
        assert tmpl.render() == "NUM"

    def test_is_mapping(self):
        env = _env()
        tmpl = env.from_string(
            "{% if val is mapping %}MAP{% else %}NOT{% end %}",
            static_context={"val": {"key": "value"}},
        )
        assert tmpl.render() == "MAP"

    def test_is_sequence(self):
        env = _env()
        tmpl = env.from_string(
            "{% if val is sequence %}SEQ{% else %}NOT{% end %}",
            static_context={"val": [1, 2, 3]},
        )
        assert tmpl.render() == "SEQ"

    def test_is_iterable(self):
        env = _env()
        tmpl = env.from_string(
            "{% if val is iterable %}ITER{% else %}NOT{% end %}",
            static_context={"val": [1, 2]},
        )
        assert tmpl.render() == "ITER"

    def test_is_true(self):
        env = _env()
        tmpl = env.from_string(
            "{% if val is true %}T{% else %}F{% end %}",
            static_context={"val": True},
        )
        assert tmpl.render() == "T"

    def test_is_false(self):
        env = _env()
        tmpl = env.from_string(
            "{% if val is false %}F{% else %}T{% end %}",
            static_context={"val": False},
        )
        assert tmpl.render() == "F"

    def test_is_none_via_compare(self):
        """'is none' parses as Compare, not Test — but still folds."""
        env = _env()
        tmpl = env.from_string(
            "{% if val is none %}NULL{% else %}NOT{% end %}",
            static_context={"val": None},
        )
        assert tmpl.render() == "NULL"

    def test_is_not_none_via_compare(self):
        env = _env()
        tmpl = env.from_string(
            "{% if val is not none %}YES{% else %}NO{% end %}",
            static_context={"val": "hello"},
        )
        assert tmpl.render() == "YES"

    def test_test_with_unresolved_value(self):
        """Test expressions with dynamic values are preserved."""
        env = _env()
        tmpl = env.from_string(
            "{% if dynamic is defined %}YES{% else %}NO{% end %}",
            static_context={},
        )
        # "dynamic" not in static context → Test can determine it's not defined
        assert tmpl.render() == "NO"

    def test_test_enables_cascade_elimination(self):
        """Test folding enables downstream branch elimination."""
        env = _env()
        tmpl = env.from_string(
            "{% if site is defined %}"
            "{% if site.title is string %}"
            "Title: {{ site.title }}"
            "{% end %}"
            "{% end %}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        assert tmpl.render() == "Title: Blog"


class TestWithAndTestCombined:
    """With propagation and Test evaluation work together."""

    def test_with_binding_enables_test(self):
        """Value bound via {% with %} is available for test evaluation."""
        env = _env()
        tmpl = env.from_string(
            "{% with count = config.count %}"
            "{% if count is odd %}ODD{% else %}EVEN{% end %}"
            "{% end %}",
            static_context={"config": {"count": 5}},
        )
        assert tmpl.render() == "ODD"

    def test_with_and_defined_check(self):
        env = _env()
        tmpl = env.from_string(
            "{% with title = site.title %}"
            "{% if title is defined %}{{ title }}{% else %}Untitled{% end %}"
            "{% end %}",
            static_context={"site": FakeSite(title="My Site", url="", nav=())},
        )
        assert tmpl.render() == "My Site"

    def test_with_is_none_branch_elimination(self):
        """With + is none comparison folds correctly."""
        env = _env()
        tmpl = env.from_string(
            "{% with val = config.optional %}"
            "{% if val is none %}DEFAULT{% else %}{{ val }}{% end %}"
            "{% end %}",
            static_context={"config": {"optional": None}},
        )
        assert tmpl.render() == "DEFAULT"


class TestMatchElimination:
    """Tests for Match node elimination when subject is compile-time-known."""

    def test_match_const_subject_first_case(self):
        """Match with literal subject — first case matches."""
        env = _env()
        tmpl = env.from_string(
            '{% match "dark" %}'
            '{% case "dark" %}DARK'
            '{% case "light" %}LIGHT'
            "{% case _ %}OTHER"
            "{% end %}",
        )
        assert tmpl.render() == "DARK"

    def test_match_const_subject_second_case(self):
        """Match with literal subject — second case matches."""
        env = _env()
        tmpl = env.from_string(
            '{% match "light" %}'
            '{% case "dark" %}DARK'
            '{% case "light" %}LIGHT'
            "{% case _ %}OTHER"
            "{% end %}",
        )
        assert tmpl.render() == "LIGHT"

    def test_match_const_subject_wildcard(self):
        """Match with literal subject — falls through to wildcard."""
        env = _env()
        tmpl = env.from_string(
            '{% match "blue" %}'
            '{% case "dark" %}DARK'
            '{% case "light" %}LIGHT'
            "{% case _ %}OTHER"
            "{% end %}",
        )
        assert tmpl.render() == "OTHER"

    def test_match_static_context_subject(self):
        """Match subject resolved from static context."""
        env = _env()
        tmpl = env.from_string(
            '{% match config.theme %}{% case "dark" %}DARK{% case "light" %}LIGHT{% end %}',
            static_context={"config": {"theme": "dark"}},
        )
        assert tmpl.render(config={"theme": "dark"}) == "DARK"

    def test_match_static_context_wildcard(self):
        """Static context subject falls through to wildcard."""
        env = _env()
        tmpl = env.from_string(
            '{% match config.theme %}{% case "dark" %}DARK{% case _ %}FALLBACK{% end %}',
            static_context={"config": {"theme": "neon"}},
        )
        assert tmpl.render(config={"theme": "neon"}) == "FALLBACK"

    def test_match_unresolved_subject_recurse(self):
        """Unresolved subject — recurse into case bodies."""
        env = _env()
        tmpl = env.from_string(
            '{% match user_theme %}{% case "dark" %}{{ site.title }}{% case _ %}DEFAULT{% end %}',
            static_context={"site": FakeSite(title="My Blog", url="", nav=())},
        )
        assert (
            tmpl.render(user_theme="dark", site=FakeSite(title="My Blog", url="", nav=()))
            == "My Blog"
        )

    def test_match_integer_subject(self):
        """Match with integer const subject."""
        env = _env()
        tmpl = env.from_string(
            "{% match 2 %}{% case 1 %}ONE{% case 2 %}TWO{% case 3 %}THREE{% end %}",
        )
        assert tmpl.render() == "TWO"

    def test_match_static_integer_subject(self):
        """Match with integer subject from static context."""
        env = _env()
        tmpl = env.from_string(
            "{% match config.level %}{% case 1 %}LOW{% case 2 %}MEDIUM{% case 3 %}HIGH{% end %}",
            static_context={"config": {"level": 3}},
        )
        assert tmpl.render(config={"level": 3}) == "HIGH"

    def test_match_no_matching_case(self):
        """No case matches and no wildcard — empty output."""
        env = _env()
        tmpl = env.from_string(
            '{% match "unknown" %}{% case "dark" %}DARK{% case "light" %}LIGHT{% end %}',
        )
        assert tmpl.render() == ""

    def test_match_elimination_ast(self):
        """Verify Match node is actually eliminated from AST."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            '{% match config.theme %}{% case "dark" %}DARK{% case _ %}OTHER{% end %}',
            static_context={"config": {"theme": "dark"}},
        )
        ast = tmpl._optimized_ast
        assert ast is not None
        node_types = [type(n).__name__ for n in ast.body]
        assert "Match" not in node_types, f"Match not eliminated: {node_types}"

    def test_match_dce_const_literal(self):
        """DCE eliminates Match with literal const subject (no static_context)."""
        env = Environment(autoescape=False, preserve_ast=True)
        tmpl = env.from_string(
            '{% match "dark" %}{% case "dark" %}DARK{% case "light" %}LIGHT{% end %}',
        )
        ast = tmpl._optimized_ast
        assert ast is not None
        node_types = [type(n).__name__ for n in ast.body]
        assert "Match" not in node_types, f"Match not eliminated by DCE: {node_types}"

    def test_match_with_body_content(self):
        """Match case body with multiple nodes."""
        env = _env()
        tmpl = env.from_string(
            "{% match config.theme %}"
            '{% case "dark" %}<div class="dark">{{ title }}</div>'
            "{% case _ %}<div>{{ title }}</div>"
            "{% end %}",
            static_context={"config": {"theme": "dark"}},
        )
        assert (
            tmpl.render(config={"theme": "dark"}, title="Hello") == '<div class="dark">Hello</div>'
        )


class TestListCompTupleUnpacking:
    """Tests for list comprehension tuple target unpacking."""

    def test_pair_unpacking(self):
        """Basic pair unpacking: [name for name, age in pairs]."""
        from kida.compiler.partial_eval import PartialEvaluator
        from kida.nodes import ListComp, Name
        from kida.nodes import Tuple as TupleNode

        pe = PartialEvaluator({"pairs": [("Alice", 30), ("Bob", 25)]})
        target = TupleNode(
            lineno=1,
            col_offset=0,
            items=(
                Name(lineno=1, col_offset=0, name="name"),
                Name(lineno=1, col_offset=0, name="age"),
            ),
        )
        lc = ListComp(
            lineno=1,
            col_offset=0,
            target=target,
            iter=Name(lineno=1, col_offset=0, name="pairs"),
            elt=Name(lineno=1, col_offset=0, name="name"),
            ifs=(),
        )
        result = pe._try_eval(lc)
        assert result == ["Alice", "Bob"]

    def test_pair_unpacking_second_element(self):
        """Unpack second element: [age for name, age in pairs]."""
        from kida.compiler.partial_eval import PartialEvaluator
        from kida.nodes import ListComp, Name
        from kida.nodes import Tuple as TupleNode

        pe = PartialEvaluator({"pairs": [("Alice", 30), ("Bob", 25)]})
        target = TupleNode(
            lineno=1,
            col_offset=0,
            items=(
                Name(lineno=1, col_offset=0, name="name"),
                Name(lineno=1, col_offset=0, name="age"),
            ),
        )
        lc = ListComp(
            lineno=1,
            col_offset=0,
            target=target,
            iter=Name(lineno=1, col_offset=0, name="pairs"),
            elt=Name(lineno=1, col_offset=0, name="age"),
            ifs=(),
        )
        result = pe._try_eval(lc)
        assert result == [30, 25]

    def test_triple_unpacking(self):
        """Triple unpacking: [name for name, age, role in triples]."""
        from kida.compiler.partial_eval import PartialEvaluator
        from kida.nodes import ListComp, Name
        from kida.nodes import Tuple as TupleNode

        pe = PartialEvaluator(
            {
                "records": [("Alice", 30, "admin"), ("Bob", 25, "user")],
            }
        )
        target = TupleNode(
            lineno=1,
            col_offset=0,
            items=(
                Name(lineno=1, col_offset=0, name="name"),
                Name(lineno=1, col_offset=0, name="age"),
                Name(lineno=1, col_offset=0, name="role"),
            ),
        )
        lc = ListComp(
            lineno=1,
            col_offset=0,
            target=target,
            iter=Name(lineno=1, col_offset=0, name="records"),
            elt=Name(lineno=1, col_offset=0, name="role"),
            ifs=(),
        )
        result = pe._try_eval(lc)
        assert result == ["admin", "user"]

    def test_tuple_unpack_with_filter(self):
        """Tuple unpacking with filter condition."""
        from kida.compiler.partial_eval import PartialEvaluator
        from kida.nodes import Compare, ListComp, Name
        from kida.nodes import Tuple as TupleNode

        pe = PartialEvaluator(
            {
                "pairs": [("Alice", 30), ("Bob", 25), ("Carol", 35)],
            }
        )
        target = TupleNode(
            lineno=1,
            col_offset=0,
            items=(
                Name(lineno=1, col_offset=0, name="name"),
                Name(lineno=1, col_offset=0, name="age"),
            ),
        )
        # Filter: age >= 30
        age_check = Compare(
            lineno=1,
            col_offset=0,
            left=Name(lineno=1, col_offset=0, name="age"),
            ops=(">=",),
            comparators=(
                __import__("kida.nodes", fromlist=["Const"]).Const(
                    lineno=1, col_offset=0, value=30
                ),
            ),
        )
        lc = ListComp(
            lineno=1,
            col_offset=0,
            target=target,
            iter=Name(lineno=1, col_offset=0, name="pairs"),
            elt=Name(lineno=1, col_offset=0, name="name"),
            ifs=(age_check,),
        )
        result = pe._try_eval(lc)
        assert result == ["Alice", "Carol"]

    def test_tuple_unpack_dict_items(self):
        """Simulate dict.items() unpacking: [k for k, v in items]."""
        from kida.compiler.partial_eval import PartialEvaluator
        from kida.nodes import ListComp, Name
        from kida.nodes import Tuple as TupleNode

        pe = PartialEvaluator(
            {
                "items": [("title", "Kida"), ("version", "0.3.4")],
            }
        )
        target = TupleNode(
            lineno=1,
            col_offset=0,
            items=(Name(lineno=1, col_offset=0, name="k"), Name(lineno=1, col_offset=0, name="v")),
        )
        lc = ListComp(
            lineno=1,
            col_offset=0,
            target=target,
            iter=Name(lineno=1, col_offset=0, name="items"),
            elt=Name(lineno=1, col_offset=0, name="v"),
            ifs=(),
        )
        result = pe._try_eval(lc)
        assert result == ["Kida", "0.3.4"]

    def test_tuple_unpack_length_mismatch(self):
        """Mismatched tuple length returns _UNRESOLVED."""
        from kida.compiler.partial_eval import _UNRESOLVED, PartialEvaluator
        from kida.nodes import ListComp, Name
        from kida.nodes import Tuple as TupleNode

        pe = PartialEvaluator(
            {
                "pairs": [("Alice", 30), ("Bob",)],  # second item has wrong length
            }
        )
        target = TupleNode(
            lineno=1,
            col_offset=0,
            items=(
                Name(lineno=1, col_offset=0, name="name"),
                Name(lineno=1, col_offset=0, name="age"),
            ),
        )
        lc = ListComp(
            lineno=1,
            col_offset=0,
            target=target,
            iter=Name(lineno=1, col_offset=0, name="pairs"),
            elt=Name(lineno=1, col_offset=0, name="name"),
            ifs=(),
        )
        result = pe._try_eval(lc)
        assert result is _UNRESOLVED

    def test_simple_name_target_still_works(self):
        """Ensure single Name target still works after tuple support added."""
        from kida.compiler.partial_eval import PartialEvaluator
        from kida.nodes import BinOp, Const, ListComp, Name

        pe = PartialEvaluator({"nums": [1, 2, 3]})
        lc = ListComp(
            lineno=1,
            col_offset=0,
            target=Name(lineno=1, col_offset=0, name="x"),
            iter=Name(lineno=1, col_offset=0, name="nums"),
            elt=BinOp(
                lineno=1,
                col_offset=0,
                left=Name(lineno=1, col_offset=0, name="x"),
                op="*",
                right=Const(lineno=1, col_offset=0, value=2),
            ),
            ifs=(),
        )
        result = pe._try_eval(lc)
        assert result == [2, 4, 6]


class TestMatchAndListCompCombined:
    """Combined tests ensuring Sprint 2 features work together."""

    def test_match_inside_for_static(self):
        """Match inside a for loop with static subject."""
        env = _env()
        tmpl = env.from_string(
            "{% for item in items %}"
            "{% match config.mode %}"
            '{% case "verbose" %}[{{ item }}]'
            "{% case _ %}{{ item }}"
            "{% end %}"
            "{% end %}",
            static_context={"config": {"mode": "verbose"}},
        )
        assert tmpl.render(config={"mode": "verbose"}, items=["a", "b"]) == "[a][b]"

    def test_match_with_output_folding(self):
        """Match elimination cascades into output folding."""
        env = _env()
        tmpl = env.from_string(
            '{% match site.theme %}{% case "dark" %}{{ site.title }}{% case _ %}Untitled{% end %}',
            static_context={"site": {"title": "Kida", "theme": "dark"}},
        )
        assert tmpl.render(site={"title": "Kida", "theme": "dark"}) == "Kida"


class TestOperatorEvaluation:
    """Operators evaluated at compile time with static context."""

    def test_subtraction(self):
        env = _env()
        tmpl = env.from_string("{{ a - b }}", static_context={"a": 10, "b": 3})
        assert tmpl.render() == "7"

    def test_division(self):
        env = _env()
        tmpl = env.from_string("{{ a / b }}", static_context={"a": 10, "b": 4})
        assert tmpl.render() == "2.5"

    def test_floor_division(self):
        env = _env()
        tmpl = env.from_string("{{ a // b }}", static_context={"a": 10, "b": 3})
        assert tmpl.render() == "3"

    def test_modulo(self):
        env = _env()
        tmpl = env.from_string("{{ a % b }}", static_context={"a": 10, "b": 3})
        assert tmpl.render() == "1"

    def test_power(self):
        env = _env()
        tmpl = env.from_string("{{ a ** b }}", static_context={"a": 2, "b": 8})
        assert tmpl.render() == "256"

    def test_unary_minus(self):
        env = _env()
        tmpl = env.from_string("{{ -x }}", static_context={"x": 5})
        assert tmpl.render() == "-5"

    def test_unary_plus(self):
        env = _env()
        tmpl = env.from_string("{{ +x }}", static_context={"x": 5})
        assert tmpl.render() == "5"

    def test_in_operator(self):
        env = _env()
        tmpl = env.from_string(
            "{% if item in items %}yes{% end %}",
            static_context={"item": "b", "items": ["a", "b", "c"]},
        )
        assert tmpl.render() == "yes"

    def test_not_in_operator(self):
        env = _env()
        tmpl = env.from_string(
            "{% if item not in items %}yes{% else %}no{% end %}",
            static_context={"item": "z", "items": ["a", "b"]},
        )
        assert tmpl.render() == "yes"

    def test_comparison_chain(self):
        """Chained comparison: a < b < c."""
        env = _env()
        tmpl = env.from_string(
            "{% if a < b < c %}yes{% end %}",
            static_context={"a": 1, "b": 2, "c": 3},
        )
        assert tmpl.render() == "yes"

    def test_comparison_chain_false(self):
        env = _env()
        tmpl = env.from_string(
            "{% if a < b < c %}yes{% else %}no{% end %}",
            static_context={"a": 1, "b": 5, "c": 3},
        )
        assert tmpl.render() == "no"


class TestFilterArgEvaluation:
    """Filters with arguments and keyword arguments resolved at compile time."""

    def test_filter_with_args(self):
        """Filter with positional arg resolved from static context."""
        env = _env()
        tmpl = env.from_string(
            "{{ title | truncate(10) }}",
            static_context={"title": "A very long title here"},
        )
        assert "..." in tmpl.render() or len(tmpl.render()) <= 13

    def test_filter_exception_returns_unresolved(self):
        """Filter that raises at compile time falls back to runtime."""
        env = _env()
        tmpl = env.from_string("{{ val | int }}", static_context={"val": "notanumber"})
        # int filter returns 0 for invalid input (default fallback).
        # The key assertion: compile-time partial eval didn't crash.
        assert tmpl.render(val="notanumber") == "0"

    def test_pipeline_with_args(self):
        """Pipeline steps with args evaluated at compile time."""
        env = _env()
        tmpl = env.from_string(
            "{{ title |> upper |> truncate(20) }}",
            static_context={"title": "hello world"},
        )
        result = tmpl.render()
        assert result == "HELLO WORLD"

    def test_safe_pipeline_none_short_circuits(self):
        """SafePipeline (?|>) propagates None through the chain."""
        env = _env()
        tmpl = env.from_string(
            "{{ val ?|> upper ?|> default('gone') }}",
        )
        assert tmpl.render(val=None) == ""


class TestFuncCallEvaluation:
    """Built-in function calls evaluated at compile time."""

    def test_range_basic(self):
        env = _env()
        tmpl = env.from_string(
            "{% for i in range(3) %}{{ i }}{% end %}",
            static_context={},
        )
        assert tmpl.render() == "012"

    def test_range_size_guard(self):
        """Range larger than 10000 is not evaluated at compile time."""
        env = _env()
        tmpl = env.from_string(
            "{{ range(20000) | length }}",
        )
        assert tmpl.render() == "20000"

    def test_len_builtin(self):
        env = _env()
        tmpl = env.from_string(
            "{{ len(items) }}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render() == "3"

    def test_sorted_builtin(self):
        env = _env()
        tmpl = env.from_string(
            "{{ sorted(items) }}",
            static_context={"items": [3, 1, 2]},
        )
        assert tmpl.render() == "[1, 2, 3]"

    def test_funccall_with_kwargs(self):
        """Keyword args in function calls resolved."""
        env = _env()
        tmpl = env.from_string(
            "{{ sorted(items, reverse=true) }}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render() == "[3, 2, 1]"

    def test_funccall_exception_falls_back(self):
        """Function call that raises falls back to runtime."""
        from kida.environment.exceptions import TemplateRuntimeError

        env = _env()
        tmpl = env.from_string(
            "{{ int(val) }}",
            static_context={"val": "notanumber"},
        )
        with pytest.raises(TemplateRuntimeError):
            tmpl.render(val="notanumber")


class TestRangeLiteralEvaluation:
    """Range literals (start..end, start...end) evaluated at compile time."""

    def test_inclusive_range(self):
        env = _env()
        tmpl = env.from_string(
            "{% for i in 1..3 %}{{ i }}{% end %}",
            static_context={},
        )
        assert tmpl.render() == "123"

    def test_exclusive_range(self):
        env = _env()
        tmpl = env.from_string(
            "{% for i in 1...4 %}{{ i }}{% end %}",
            static_context={},
        )
        assert tmpl.render() == "123"

    def test_range_with_step(self):
        env = _env()
        tmpl = env.from_string(
            "{% for i in range(0, 10, 2) %}{{ i }}{% end %}",
            static_context={},
        )
        assert tmpl.render() == "02468"


class TestTestExprWithArgs:
    """Test expressions with arguments and edge cases."""

    def test_defined_non_name_expr(self):
        """'is defined' on a non-Name expression (e.g., attribute)."""
        env = _env()
        tmpl = env.from_string(
            "{% if site.title is defined %}yes{% else %}no{% end %}",
            static_context={"site": {"title": "Hello"}},
        )
        assert tmpl.render() == "yes"

    def test_undefined_non_name_expr(self):
        """'is undefined' on a non-Name expression."""
        env = _env()
        tmpl = env.from_string(
            "{% if site.title is undefined %}yes{% else %}no{% end %}",
            static_context={"site": {"title": "Hello"}},
        )
        assert tmpl.render() == "no"

    def test_is_not_undefined(self):
        """'is not undefined' when present."""
        env = _env()
        tmpl = env.from_string(
            "{% if x is not undefined %}present{% end %}",
            static_context={"x": 42},
        )
        assert tmpl.render() == "present"

    def test_test_with_args_divisibleby(self):
        """Test with argument (divisibleby)."""
        env = _env()
        tmpl = env.from_string(
            "{% if n is divisibleby(3) %}yes{% else %}no{% end %}",
            static_context={"n": 9},
        )
        assert tmpl.render(n=9) == "yes"

    def test_test_unknown_name_compile_error(self):
        """Unknown test name is caught at compile time."""
        env = _env()
        with pytest.raises(TemplateSyntaxError, match="Unknown test"):
            env.from_string("{% if x is nonexistent_test %}yes{% else %}no{% end %}")

    def test_test_exception_handling(self):
        """Test that raises an exception falls back to runtime."""
        env = _env()
        tmpl = env.from_string(
            "{% if val is number %}num{% else %}not{% end %}",
            static_context={"val": 42},
        )
        assert tmpl.render() == "num"


class TestWithPropagationExtended:
    """With statement variable propagation — extended cases."""

    def test_with_static_binding(self):
        env = _env()
        tmpl = env.from_string(
            "{% with title = site.title %}{{ title }}{% endwith %}",
            static_context={"site": {"title": "Hello"}},
        )
        assert tmpl.render() == "Hello"

    def test_with_dynamic_binding_preserved(self):
        """Dynamic binding is preserved for runtime."""
        env = _env()
        tmpl = env.from_string("{% with greeting = name %}{{ greeting }}{% endwith %}")
        assert tmpl.render(name="World") == "World"


class TestMatchTransformPath:
    """Match/case elimination through _transform_match (static_context path)."""

    def test_match_static_subject_selects_case(self):
        env = _env()
        tmpl = env.from_string(
            '{% match mode %}{% case "dark" %}dark-theme{% case "light" %}light-theme{% case _ %}default{% end %}',
            static_context={"mode": "dark"},
        )
        assert tmpl.render() == "dark-theme"

    def test_match_static_subject_wildcard(self):
        env = _env()
        tmpl = env.from_string(
            '{% match mode %}{% case "a" %}A{% case _ %}wildcard{% end %}',
            static_context={"mode": "z"},
        )
        assert tmpl.render() == "wildcard"

    def test_match_unresolved_recurses_into_bodies(self):
        """Unresolved subject — bodies are still partially evaluated."""
        env = _env()
        tmpl = env.from_string(
            '{% match val %}{% case "x" %}{{ site.title }}{% case _ %}other{% end %}',
            static_context={"site": {"title": "Hi"}},
        )
        assert tmpl.render(val="x") == "Hi"


class TestAssignmentPropagationExtended:
    """Let/Set/Export propagation — extended cases."""

    def test_let_propagates_downstream(self):
        env = _env()
        tmpl = env.from_string(
            "{% let x = site.title %}{{ x }}",
            static_context={"site": {"title": "Kida"}},
        )
        assert tmpl.render() == "Kida"

    def test_coalesce_assignment_existing(self):
        """Coalesce assignment (??=) does not overwrite existing value."""
        env = _env()
        tmpl = env.from_string(
            "{% let x = 'original' %}{% let x ??= 'fallback' %}{{ x }}",
        )
        assert tmpl.render() == "original"

    def test_export_propagation(self):
        """Export promotes variable to template scope."""
        env = _env()
        tmpl = env.from_string(
            "{% if true %}{% export name = site.title %}{% end %}{{ name }}",
            static_context={"site": {"title": "Kida"}},
        )
        assert tmpl.render() == "Kida"


class TestNullCoalesceEvaluation:
    """NullCoalesce (??) evaluated at compile time."""

    def test_null_coalesce_left_none_static(self):
        """Left side None → evaluates right side."""
        env = _env()
        tmpl = env.from_string(
            '{{ val ?? "fallback" }}',
            static_context={"val": None},
        )
        assert tmpl.render() == "fallback"

    def test_null_coalesce_left_present(self):
        """Left side present → uses left side."""
        env = _env()
        tmpl = env.from_string(
            '{{ val ?? "fallback" }}',
            static_context={"val": "hello"},
        )
        assert tmpl.render() == "hello"


class TestConcatEvaluation:
    """Concat (~) operator evaluated at compile time."""

    def test_concat_static(self):
        env = _env()
        tmpl = env.from_string(
            "{{ first ~ ' ' ~ last }}",
            static_context={"first": "Jane", "last": "Doe"},
        )
        assert tmpl.render() == "Jane Doe"

    def test_concat_partial(self):
        """One side static, other dynamic — partial simplification."""
        env = _env()
        tmpl = env.from_string(
            "{{ prefix ~ name }}",
            static_context={"prefix": "Dr. "},
        )
        assert tmpl.render(name="Smith") == "Dr. Smith"


class TestListCompEvaluation:
    """List comprehension evaluated at compile time."""

    def test_listcomp_basic(self):
        env = _env()
        tmpl = env.from_string(
            "{{ [x * 2 for x in items] }}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render() == "[2, 4, 6]"

    def test_listcomp_with_filter(self):
        env = _env()
        tmpl = env.from_string(
            "{{ [x for x in items if x > 1] }}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render() == "[2, 3]"

    def test_listcomp_tuple_unpacking(self):
        env = _env()
        tmpl = env.from_string(
            "{{ [k for k, v in pairs] }}",
            static_context={"pairs": [("a", 1), ("b", 2)]},
        )
        assert tmpl.render() == "['a', 'b']"

    def test_listcomp_too_large_falls_back(self):
        """List over 200 items not evaluated at compile time."""
        env = _env()
        big = list(range(201))
        tmpl = env.from_string(
            "{{ [x for x in items] | length }}",
            static_context={"items": big},
        )
        assert tmpl.render(items=big) == "201"


class TestMatchTransformGuards:
    """Match guard evaluation through _transform_match."""

    def test_match_guard_true(self):
        env = _env()
        tmpl = env.from_string(
            '{% match mode %}{% case "a" if flag %}guarded{% case _ %}default{% end %}',
            static_context={"mode": "a", "flag": True},
        )
        assert tmpl.render() == "guarded"

    def test_match_guard_false_falls_through(self):
        env = _env()
        tmpl = env.from_string(
            '{% match mode %}{% case "a" if flag %}guarded{% case _ %}default{% end %}',
            static_context={"mode": "a", "flag": False},
        )
        assert tmpl.render() == "default"
