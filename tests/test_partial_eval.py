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


class TestDeadCodeElimination:
    """Const-only dead code elimination (runs without static_context)."""

    def test_if_false_removed(self):
        """{% if false %}...{% end %} is removed entirely."""
        env = _env()
        tmpl = env.from_string("a{% if false %}DEAD{% end %}b")
        assert tmpl.render() == "ab"

    def test_if_true_inlined(self):
        """{% if true %}x{% end %} is inlined to x."""
        env = _env()
        tmpl = env.from_string("a{% if true %}LIVE{% end %}b")
        assert tmpl.render() == "aLIVEb"

    def test_const_expr_eliminated(self):
        """{% if 1+1==2 %}ok{% end %} is inlined."""
        env = _env()
        tmpl = env.from_string("{% if 1 + 1 == 2 %}ok{% end %}")
        assert tmpl.render() == "ok"

    def test_scoping_preserved(self):
        """If body with Set is not inlined (block scoping)."""
        env = _env()
        tmpl = env.from_string(
            "{% set x = 'outer' %}{% if true %}{% set x = 'inner' %}{{ x }}{% end %}{{ x }}"
        )
        assert tmpl.render() == "innerouter"

    def test_nested_dead_if_removed(self):
        """{% if false %}{% if true %}x{% end %}{% end %} yields empty."""
        env = _env()
        tmpl = env.from_string("a{% if false %}{% if true %}x{% end %}{% end %}b")
        assert tmpl.render() == "ab"


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


def _inline_env() -> Environment:
    return Environment(autoescape=False, inline_components=True)


class TestComponentInlining:
    """Small defs with constant args are inlined at compile time."""

    def test_simple_inline(self):
        """A def called with all-static args is inlined."""
        env = _inline_env()
        tmpl = env.from_string(
            '{% def greeting(name) %}Hello, {{ name }}!{% end %}{{ greeting("World") }}',
            static_context={"_placeholder": True},  # Need static_context to trigger
        )
        assert tmpl.render() == "Hello, World!"

    def test_inline_with_defaults(self):
        """Default params are resolved at compile time."""
        env = _inline_env()
        tmpl = env.from_string(
            '{% def tag(text, cls="default") %}'
            '<span class="{{ cls }}">{{ text }}</span>'
            "{% end %}"
            '{{ tag("hi") }}',
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == '<span class="default">hi</span>'

    def test_inline_with_static_context(self):
        """Def body references static context vars."""
        env = _inline_env()
        tmpl = env.from_string(
            "{% def header() %}<h1>{{ site_name }}</h1>{% end %}{{ header() }}",
            static_context={"site_name": "Kida"},
        )
        assert tmpl.render() == "<h1>Kida</h1>"

    def test_no_inline_with_slots(self):
        """Defs with slots are NOT inlined (too complex)."""
        env = _inline_env()
        tmpl = env.from_string(
            "{% def card(title) %}<div>{{ title }}{% slot %}</div>{% end %}"
            "{% call card('X') %}content{% end %}",
            static_context={"_placeholder": True},
        )
        # Should still work, just not inlined
        assert "X" in tmpl.render()

    def test_no_inline_without_flag(self):
        """Inlining is off by default."""
        env = _env()
        tmpl = env.from_string(
            '{% def greeting(name) %}Hello, {{ name }}!{% end %}{{ greeting("World") }}',
            static_context={"_placeholder": True},
        )
        assert tmpl.render() == "Hello, World!"

    def test_inline_with_dynamic_args_skipped(self):
        """Calls with dynamic args are not inlined."""
        env = _inline_env()
        tmpl = env.from_string(
            "{% def greeting(name) %}Hello, {{ name }}!{% end %}{{ greeting(user_name) }}",
            static_context={"_placeholder": True},
        )
        # Dynamic arg — falls back to runtime
        assert tmpl.render(user_name="Alice") == "Hello, Alice!"


# =========================================================================
# Optimization metrics — measure AST node reduction
# =========================================================================


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


class TestStaticLoopUnrolling:
    """Static for-loops are unrolled at compile time."""

    def test_simple_unroll(self):
        """{% for x in items %}{{ x }}{% end %} with static items unrolls."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }},{% end %}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render() == "1,2,3,"

    def test_unroll_with_attribute_access(self):
        """Unrolled items support attribute access."""
        env = _env()
        nav = [{"title": "Home", "url": "/"}, {"title": "About", "url": "/about"}]
        tmpl = env.from_string(
            '{% for item in nav %}<a href="{{ item.url }}">{{ item.title }}</a>{% end %}',
            static_context={"nav": nav},
        )
        assert tmpl.render() == '<a href="/">Home</a><a href="/about">About</a>'

    def test_unroll_with_loop_index(self):
        """loop.index works in unrolled loops."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ loop.index }}:{{ x }} {% end %}",
            static_context={"items": ["a", "b", "c"]},
        )
        assert tmpl.render() == "1:a 2:b 3:c "

    def test_unroll_with_loop_first_last(self):
        """loop.first and loop.last work in unrolled loops."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}"
            "{% if loop.first %}[{% end %}"
            "{{ x }}"
            "{% if loop.last %}]{% end %}"
            "{% if not loop.last %},{% end %}"
            "{% end %}",
            static_context={"items": ["a", "b", "c"]},
        )
        assert tmpl.render() == "[a,b,c]"

    def test_unroll_empty_list(self):
        """Empty static list → empty body (or {% empty %} branch)."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% empty %}none{% end %}",
            static_context={"items": []},
        )
        assert tmpl.render() == "none"

    def test_unroll_tuple_unpacking(self):
        """{% for k, v in items %}{{ k }}={{ v }}{% end %} unrolls."""
        env = _env()
        tmpl = env.from_string(
            "{% for k, v in pairs %}{{ k }}={{ v }} {% end %}",
            static_context={"pairs": [("a", 1), ("b", 2)]},
        )
        assert tmpl.render() == "a=1 b=2 "

    def test_unroll_list_literal(self):
        """{% for x in [1, 2, 3] %} unrolls with literal list."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in [1, 2, 3] %}{{ x }}{% end %}",
        )
        assert tmpl.render() == "123"

    def test_dynamic_iter_not_unrolled(self):
        """Dynamic iterable is not unrolled — works normally at runtime."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(items=[1, 2]) == "12"

    def test_unroll_mixed_static_dynamic_body(self):
        """Unrolled loop body can mix static and dynamic expressions."""
        env = _env()
        tmpl = env.from_string(
            "{% for item in nav %}{{ site_name }}: {{ item.title }}\n{% end %}",
            static_context={
                "nav": [{"title": "Home"}, {"title": "About"}],
                "site_name": "Kida",
            },
        )
        assert tmpl.render() == "Kida: Home\nKida: About\n"


class TestUnrolledLoopLetBinding:
    """Regression tests for loop variable references in {% let %} inside unrolled loops.

    When a for-loop is unrolled but a {% let %} value can only be *partially*
    resolved (e.g. it references both the loop variable and a runtime-only
    expression), the partial evaluator must still replace the resolvable
    sub-expressions with Const nodes.  Otherwise the unrolled body references
    the loop variable outside its defining scope, causing UndefinedError.

    See: https://github.com/<owner>/<repo>/issues/78
    """

    def test_let_with_loop_var_and_dynamic_expr(self):
        """{% let %} inside unrolled loop referencing loop var + dynamic expr."""
        env = _env()
        tmpl = env.from_string(
            "{% let items = [{'u': 'a.com'}, {'u': 'b.com'}] %}"
            "{% for it in items %}"
            "{% let url = it.u ~ '?q=' ~ query %}"
            "{{ url }}\n"
            "{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(query="hello") == "a.com?q=hello\nb.com?q=hello\n"

    def test_let_with_loop_var_and_pipeline(self):
        """{% let %} with pipeline operator inside unrolled loop."""
        env = _env()
        tmpl = env.from_string(
            "{% let items = [{'u': 'a.com'}, {'u': 'b.com'}] %}"
            "{% for it in items %}"
            "{% let url = it.u ~ '?q=' ~ (query |> upper) %}"
            "{{ url }}\n"
            "{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(query="hello") == "a.com?q=HELLO\nb.com?q=HELLO\n"

    def test_multiple_loops_with_let_and_match(self):
        """Multiple unrolled loops with match + let preserve loop var bindings."""
        env = _env()
        tmpl = env.from_string(
            "{% let actions = [{'type': 'a'}, {'type': 'b'}] %}"
            "{% let targets = [{'url': 'x.com'}, {'url': 'y.com'}] %}"
            "{% for act in actions %}"
            "{% match act.type %}{% case 'a' %}A{% case 'b' %}B{% end %}"
            "{% end %}"
            "{% for t in targets %}"
            "{% let link = t.url ~ '?r=' ~ ref %}"
            "{{ link }}\n"
            "{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(ref="z") == "ABx.com?r=z\ny.com?r=z\n"

    def test_cross_template_import_let_in_loop(self):
        """Imported def with unrolled loop + partially-dynamic let."""
        from kida.environment import DictLoader

        macros_src = (
            '{% let ITEMS = [{"name": "A", "url": "a.com"}, '
            '{"name": "B", "url": "b.com"}] %}'
            "{% def show(query) %}"
            "{% for item in ITEMS %}"
            '{% let link = item.url ~ "?q=" ~ query %}'
            '<a href="{{ link }}">{{ item.name }}</a>\n'
            "{% end %}"
            "{% end %}"
        )
        main_src = '{% from "m.html" import show %}{{ show(query=q) }}'
        loader = DictLoader({"m.html": macros_src, "main.html": main_src})
        env = Environment(loader=loader, static_context={"_placeholder": True})
        tmpl = env.get_template("main.html")
        result = tmpl.render(q="hi")
        assert '<a href="a.com?q=hi">A</a>' in result
        assert '<a href="b.com?q=hi">B</a>' in result

    def test_export_with_loop_var_and_dynamic_expr(self):
        """{% export %} inside unrolled loop with partially-dynamic value."""
        env = _env()
        tmpl = env.from_string(
            '{% let items = [{"name": "A"}, {"name": "B"}] %}'
            "{% for item in items %}"
            "{% export result = item.name ~ dynamic %}"
            "{% end %}"
            "{{ result }}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(dynamic="!") == "B!"

    def test_capture_with_loop_var_and_dynamic_expr(self):
        """{% capture %} inside unrolled loop with partially-dynamic body."""
        env = _env()
        tmpl = env.from_string(
            '{% let items = [{"name": "A"}, {"name": "B"}] %}'
            "{% for item in items %}"
            "{% capture result %}{{ item.name }}:{{ dynamic }}{% end %}"
            "{% end %}"
            "{{ result }}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(dynamic="!") == "B:!"


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


# ---------------------------------------------------------------------------
# Sprint 4: Purity analysis integration — @pure decorator
# ---------------------------------------------------------------------------


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


# =============================================================================
# Phase 2, Sprint 1: With propagation + Test expression evaluation
# =============================================================================


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


# ── Sprint 2: Match Elimination + ListComp Tuple Targets ─────────────


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


# ── Sprint 3: _transform_expr Sub-Expression Widening ────────────────


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


# ------------------------------------------------------------------
# DCE: const-only dead code elimination (no static_context needed)
# ------------------------------------------------------------------


class TestDCEConstOnlyElif:
    """Dead code elimination in elif chains with constant tests."""

    def test_elif_true_inlined(self):
        """{% if false %}...{% elif true %}kept{% end %} → 'kept'."""
        env = _env()
        tmpl = env.from_string("{% if false %}dead{% elif true %}kept{% end %}")
        assert tmpl.render() == "kept"

    def test_elif_chain_second_truthy(self):
        """Second truthy elif after false first branch."""
        env = _env()
        tmpl = env.from_string("{% if false %}a{% elif false %}b{% elif 1 %}c{% end %}")
        assert tmpl.render() == "c"

    def test_all_false_else_inlined(self):
        """All branches false → else body inlined."""
        env = _env()
        tmpl = env.from_string("{% if false %}a{% elif 0 %}b{% else %}fallback{% end %}")
        assert tmpl.render() == "fallback"

    def test_elif_with_multi_node_body(self):
        """Elif body with multiple nodes produces InlinedBody."""
        env = _env()
        tmpl = env.from_string("{% if false %}x{% elif true %}hello world{% end %}")
        assert tmpl.render() == "hello world"

    def test_scoping_in_elif_preserves_node(self):
        """Scoping node (set) in elif body prevents inlining."""
        env = _env()
        tmpl = env.from_string("{% if false %}x{% elif true %}{% set y = 1 %}{{ y }}{% end %}")
        assert tmpl.render() == "1"

    def test_scoping_in_else_preserves_node(self):
        """Scoping node (set) in else body prevents inlining."""
        env = _env()
        tmpl = env.from_string("{% if false %}x{% else %}{% set y = 2 %}{{ y }}{% end %}")
        assert tmpl.render() == "2"


class TestDCEConstOnlyMatch:
    """Dead code elimination for match/case with constant subjects."""

    def test_match_const_literal_first_case(self):
        """Match on literal constant — picks correct case."""
        env = _env()
        tmpl = env.from_string('{% match "a" %}{% case "a" %}alpha{% case "b" %}beta{% end %}')
        assert tmpl.render() == "alpha"

    def test_match_const_literal_wildcard(self):
        """Match wildcard when no case matches."""
        env = _env()
        tmpl = env.from_string('{% match "z" %}{% case "a" %}alpha{% case _ %}other{% end %}')
        assert tmpl.render() == "other"

    def test_match_const_with_guard_true(self):
        """Match with guard condition that evaluates to true."""
        env = _env()
        tmpl = env.from_string("{% match 5 %}{% case 5 if true %}five{% case _ %}other{% end %}")
        assert tmpl.render() == "five"

    def test_match_const_with_guard_false_falls_through(self):
        """Match with guard=false skips the case, falls through."""
        env = _env()
        tmpl = env.from_string(
            "{% match 5 %}{% case 5 if false %}guarded{% case _ %}fallback{% end %}"
        )
        assert tmpl.render() == "fallback"

    def test_match_wildcard_with_guard(self):
        """Wildcard with guard that evaluates true."""
        env = _env()
        tmpl = env.from_string('{% match "x" %}{% case _ if true %}guarded_wild{% end %}')
        assert tmpl.render() == "guarded_wild"

    def test_match_wildcard_guard_false(self):
        """Wildcard with guard=false — skips, no output."""
        env = _env()
        tmpl = env.from_string('{% match "x" %}{% case _ if false %}guarded{% end %}')
        assert tmpl.render() == ""

    def test_match_unresolved_subject_recurses(self):
        """Unresolved subject recurses into case bodies."""
        env = _env()
        tmpl = env.from_string('{% match val %}{% case "a" %}alpha{% case _ %}other{% end %}')
        assert tmpl.render(val="a") == "alpha"

    def test_match_scoping_in_case_preserves(self):
        """Scoping node in matched case body prevents DCE inlining."""
        env = _env()
        tmpl = env.from_string('{% match "a" %}{% case "a" %}{% set x = 1 %}{{ x }}{% end %}')
        assert tmpl.render() == "1"


# ------------------------------------------------------------------
# Operator evaluation via static context
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Filter evaluation with args and kwargs
# ------------------------------------------------------------------


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
        assert tmpl.render(val=None) == "None"


# ------------------------------------------------------------------
# FuncCall evaluation (builtins)
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Range literal evaluation
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Test expression evaluation (is defined / is undefined / etc.)
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Boolean operator simplification
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# CondExpr simplification
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# For-loop unrolling edge cases
# ------------------------------------------------------------------


class TestForLoopUnrolling:
    """For-loop unrolling with static iterables."""

    def test_unroll_basic(self):
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% end %}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render() == "123"

    def test_unroll_empty_iterable(self):
        """Empty iterable → empty output."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% end %}",
            static_context={"items": []},
        )
        assert tmpl.render() == ""

    def test_unroll_empty_with_fallback(self):
        """Empty iterable with else block → else body."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% empty %}none{% end %}",
            static_context={"items": []},
        )
        assert tmpl.render() == "none"

    def test_unroll_tuple_unpacking(self):
        """Tuple unpacking in for target."""
        env = _env()
        tmpl = env.from_string(
            "{% for k, v in pairs %}{{ k }}={{ v }} {% end %}",
            static_context={"pairs": [("a", 1), ("b", 2)]},
        )
        assert tmpl.render().strip() == "a=1 b=2"

    def test_unroll_with_test_filter(self):
        """For with if-filter on items."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items if x > 2 %}{{ x }}{% end %}",
            static_context={"items": [1, 2, 3, 4]},
        )
        assert tmpl.render() == "34"

    def test_unroll_loop_properties(self):
        """Loop.first / loop.last available during unrolling."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}"
            "{% if loop.first %}[{% end %}"
            "{{ x }}"
            "{% if loop.last %}]{% end %}"
            "{% end %}",
            static_context={"items": ["a", "b", "c"]},
        )
        assert tmpl.render() == "[abc]"

    def test_unroll_too_many_items_falls_back(self):
        """More than 200 items → not unrolled, still works at runtime."""
        env = _env()
        big_list = list(range(201))
        tmpl = env.from_string(
            "{{ items | length }}",
            static_context={"items": big_list},
        )
        assert tmpl.render() == "201"


# ------------------------------------------------------------------
# With statement propagation
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Match with static_context (transform path)
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Assignment propagation edge cases
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Component inlining
# ------------------------------------------------------------------


class TestComponentInliningEdgeCases:
    """Edge cases for component inlining."""

    def test_inline_with_default_args(self):
        """Def with default args — missing args filled from defaults."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            '{% def greet(name, greeting="Hello") %}{{ greeting }} {{ name }}{% end %}'
            '{% call greet("World") %}{% end %}',
            static_context={"_inline": True},
        )
        assert "Hello World" in tmpl.render()

    def test_no_inline_with_slots(self):
        """Def with slots is not inlined but still works."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            "{% def card(title) %}<div>{{ title }}{% slot %}</div>{% end %}"
            "{% call card('Hi') %} body{% end %}"
        )
        assert "Hi" in tmpl.render()
        assert "body" in tmpl.render()

    def test_no_inline_with_scoping_nodes(self):
        """Def with scoping nodes (set) is not inlined."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            "{% def calc(x) %}{% set y = x %}{{ y }}{% end %}{% call calc(5) %}{% end %}",
            static_context={"_inline": True},
        )
        assert tmpl.render() == "5"


# ------------------------------------------------------------------
# NullCoalesce evaluation
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Concat operator evaluation
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# ListComp evaluation
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# _transform_expr partial simplification (sub-expression changes)
# ------------------------------------------------------------------


class TestTransformExprGetattr:
    """Getattr partial simplification — obj changes but attr access unresolved."""

    def test_getattr_partial_obj(self):
        """Getattr where obj sub-expr changes but full eval fails."""
        env = Environment(autoescape=False, preserve_ast=True)
        # site.title resolves, but the getattr on dynamic.x doesn't.
        # We use a complex expression where the object part can be simplified.
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


# ------------------------------------------------------------------
# BoolOp and CondExpr edge cases
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Match transform path (non-DCE, via static_context)
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# For-loop test filter and empty block
# ------------------------------------------------------------------


class TestForLoopTestFilter:
    """For-loop with test (if) filter via partial eval."""

    def test_for_test_filter_static(self):
        """For with static iterable and test filter."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items if x > 0 %}{{ x }}{% end %}",
            static_context={"items": [-1, 0, 1, 2]},
        )
        assert tmpl.render() == "12"

    def test_for_empty_static_with_empty_block(self):
        """Empty static iterable triggers empty block."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% empty %}nothing{% end %}",
            static_context={"items": []},
        )
        assert tmpl.render() == "nothing"


# ------------------------------------------------------------------
# Component inlining internals
# ------------------------------------------------------------------


class TestComponentInliningInternals:
    """Component inlining edge cases."""

    def test_inline_too_many_args(self):
        """Too many positional args — not inlined, raises at runtime."""
        from kida.environment.exceptions import TemplateRuntimeError

        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            "{% def greet(name) %}Hello {{ name }}{% end %}"
            "{% call greet('World', 'extra') %}{% end %}"
        )
        with pytest.raises(TemplateRuntimeError):
            tmpl.render()

    def test_inline_with_kwargs(self):
        """Keyword args in call — resolved for inlining."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            '{% def greet(name, greeting="Hi") %}{{ greeting }} {{ name }}{% end %}'
            '{% call greet(greeting="Hey", name="World") %}{% end %}',
            static_context={"_inline": True},
        )
        assert "Hey World" in tmpl.render()

    def test_no_inline_vararg(self):
        """Def with *args — not inlined but still works."""
        env = Environment(autoescape=False, inline_components=True)
        tmpl = env.from_string(
            "{% def greet(*names) %}Hello{% end %}{% call greet('a', 'b') %}{% end %}"
        )
        assert "Hello" in tmpl.render()


# ------------------------------------------------------------------
# Targeted transform branch coverage
# ------------------------------------------------------------------


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
