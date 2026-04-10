"""Tests for compile-time partial evaluation.

Verifies that the PartialEvaluator correctly replaces static expressions
with constants in the template AST, and that the rendered output is
identical whether using partial evaluation or runtime context.

"""

from dataclasses import dataclass

from kida import Environment


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
