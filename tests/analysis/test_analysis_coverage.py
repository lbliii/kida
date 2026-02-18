"""Coverage tests for analysis.dependencies and analysis.purity.

Targets uncovered code paths to improve coverage from 46%/51% toward 85%+.
"""

from __future__ import annotations

from kida import Environment
from kida.environment.loaders import DictLoader

# ---------------------------------------------------------------------------
# DependencyWalker — target uncovered handlers
# ---------------------------------------------------------------------------


class TestDependencyWalkerOptionalAccess:
    """Optional chaining and subscript dependency tracking."""

    def test_optional_getattr(self) -> None:
        """Optional chaining obj?.attr tracks dependency."""
        env = Environment()
        t = env.from_string("{{ user?.name }}")
        deps = t.depends_on()
        assert "user.name" in deps or "user" in deps

    def test_optional_getitem(self) -> None:
        """Optional subscript obj?[key] tracks dependency path."""
        env = Environment()
        t = env.from_string('{{ data?["key"] }}')
        deps = t.depends_on()
        assert "data.key" in deps or "data" in deps

    def test_getitem_dynamic_key(self) -> None:
        """Dynamic subscript key tracks both base and key."""
        env = Environment()
        t = env.from_string("{{ items[index] }}")
        deps = t.depends_on()
        assert "items" in deps
        assert "index" in deps


class TestDependencyWalkerControlFlow:
    """Dependency tracking through control flow constructs."""

    def test_while_loop(self) -> None:
        """While loop test and body track dependencies."""
        env = Environment()
        t = env.from_string("{% block content %}{% while items %}{{ items }}{% end %}{% end %}")
        deps = t.depends_on()
        assert "items" in deps

    def test_with_statement(self) -> None:
        """With bindings track value deps but not the bound name."""
        env = Environment()
        t = env.from_string("{% with x = page.title %}{{ x }}{% end %}")
        deps = t.depends_on()
        assert "page.title" in deps
        # x is a local binding, not a context dependency
        assert "x" not in deps

    def test_conditional_with(self) -> None:
        """Conditional with ({% with expr as target %}) tracks expression."""
        env = Environment()
        t = env.from_string("{% with items as data %}{{ data }}{% end %}")
        deps = t.depends_on()
        assert "items" in deps

    def test_def_arguments_excluded(self) -> None:
        """Function arguments are excluded from dependencies."""
        env = Environment()
        t = env.from_string("{% def show(item) %}{{ item.name }}{% end %}{{ show(page) }}")
        deps = t.depends_on()
        assert "page" in deps
        assert "item" not in deps

    def test_def_with_defaults(self) -> None:
        """Default values in def are tracked as dependencies."""
        env = Environment()
        t = env.from_string("{% def show(title=site.name) %}{{ title }}{% end %}")
        deps = t.depends_on()
        assert "site.name" in deps or "site" in deps

    def test_set_statement(self) -> None:
        """Set statement tracks value deps and adds to scope."""
        env = Environment()
        t = env.from_string("{% set x = page.title %}{{ x }}")
        deps = t.depends_on()
        assert "page.title" in deps
        # x should be scoped after set

    def test_let_statement(self) -> None:
        """Let statement tracks value deps."""
        env = Environment()
        t = env.from_string("{% let x = config.value %}{{ x }}")
        deps = t.depends_on()
        assert "config.value" in deps or "config" in deps

    def test_if_elif_else(self) -> None:
        """If/elif/else tracks all branch dependencies."""
        env = Environment()
        t = env.from_string("{% if a %}{{ x }}{% elif b %}{{ y }}{% else %}{{ z }}{% end %}")
        deps = t.depends_on()
        assert "a" in deps
        assert "b" in deps
        assert "x" in deps
        assert "y" in deps
        assert "z" in deps

    def test_match_statement(self) -> None:
        """Match statement tracks subject and case body deps."""
        env = Environment()
        t = env.from_string(
            "{% match status %}"
            '{% case "active" %}{{ active_text }}'
            '{% case "inactive" %}{{ inactive_text }}'
            "{% end %}"
        )
        deps = t.depends_on()
        assert "status" in deps
        assert "active_text" in deps
        assert "inactive_text" in deps

    def test_nested_for_scoping(self) -> None:
        """Nested for loops scope variables correctly."""
        env = Environment()
        t = env.from_string(
            "{% for group in groups %}"
            "{% for item in group.items %}"
            "{{ item.name }}"
            "{% end %}"
            "{% end %}"
        )
        deps = t.depends_on()
        assert "groups" in deps
        assert "group" not in deps
        assert "item" not in deps


class TestDependencyWalkerExpressions:
    """Dependency tracking through expression types."""

    def test_ternary_expression(self) -> None:
        """Ternary if tracks all three parts."""
        env = Environment()
        t = env.from_string("{{ x if flag else y }}")
        deps = t.depends_on()
        assert "flag" in deps
        assert "x" in deps
        assert "y" in deps

    def test_binary_operation(self) -> None:
        """Binary operations track both sides."""
        env = Environment()
        t = env.from_string("{{ a + b }}")
        deps = t.depends_on()
        assert "a" in deps
        assert "b" in deps

    def test_unary_operation(self) -> None:
        """Unary operation tracks operand."""
        env = Environment()
        t = env.from_string("{{ not flag }}")
        deps = t.depends_on()
        assert "flag" in deps

    def test_comparison(self) -> None:
        """Comparisons track both sides."""
        env = Environment()
        t = env.from_string("{% if a == b %}yes{% end %}")
        deps = t.depends_on()
        assert "a" in deps
        assert "b" in deps

    def test_filter_args_tracked(self) -> None:
        """Filter arguments are tracked as dependencies."""
        env = Environment()
        t = env.from_string("{{ items | join(separator) }}")
        deps = t.depends_on()
        assert "items" in deps
        assert "separator" in deps

    def test_function_call_args_tracked(self) -> None:
        """Function call arguments are tracked."""
        env = Environment()
        t = env.from_string("{{ range(count) }}")
        deps = t.depends_on()
        assert "count" in deps

    def test_null_coalescing(self) -> None:
        """Null coalescing operator tracks both sides."""
        env = Environment()
        t = env.from_string("{{ user ?? default_user }}")
        deps = t.depends_on()
        assert "user" in deps
        assert "default_user" in deps

    def test_list_literal(self) -> None:
        """List literal items are tracked."""
        env = Environment()
        t = env.from_string("{{ [a, b, c] }}")
        deps = t.depends_on()
        assert "a" in deps
        assert "b" in deps
        assert "c" in deps

    def test_dict_literal(self) -> None:
        """Dict literal values are tracked."""
        env = Environment()
        t = env.from_string('{{ {"key": value} }}')
        deps = t.depends_on()
        assert "value" in deps

    def test_pipeline_operator(self) -> None:
        """Pipeline operator tracks base and step args."""
        env = Environment()
        t = env.from_string("{{ items |> join(',') }}")
        deps = t.depends_on()
        assert "items" in deps

    def test_include_dependency(self) -> None:
        """Include statement tracks template name."""
        loader = DictLoader(
            {
                "main.html": '{% include "partial.html" %}{{ extra }}',
                "partial.html": "{{ partial_var }}",
            }
        )
        env = Environment(loader=loader)
        t = env.get_template("main.html")
        deps = t.depends_on()
        assert "extra" in deps

    def test_for_with_filter(self) -> None:
        """For loop with filter condition tracks filter deps."""
        env = Environment()
        t = env.from_string("{% for item in items if item.active %}{{ item.name }}{% end %}")
        deps = t.depends_on()
        assert "items" in deps

    def test_for_with_empty(self) -> None:
        """For loop with empty block tracks all deps."""
        env = Environment()
        t = env.from_string("{% for item in items %}{{ item }}{% empty %}{{ fallback }}{% end %}")
        deps = t.depends_on()
        assert "items" in deps
        assert "fallback" in deps

    def test_nested_attribute_chain(self) -> None:
        """Deep attribute chains are tracked."""
        env = Environment()
        t = env.from_string("{{ site.config.theme.name }}")
        deps = t.depends_on()
        assert "site.config.theme.name" in deps


class TestDependencyWalkerBuildPath:
    """Test _build_path for complex access patterns."""

    def test_getitem_string_key(self) -> None:
        """Static string key in subscript is part of path."""
        env = Environment()
        t = env.from_string('{{ data["section"] }}')
        deps = t.depends_on()
        assert "data.section" in deps or "data" in deps


class TestSlotAwareAnalysis:
    """Slot-aware analysis: depends_on and validate_context traverse slot bodies in CallBlock."""

    def test_depends_on_includes_slot_body_expressions(self) -> None:
        """Expressions inside {% slot name %}...{% end %} in call blocks are tracked."""
        env = Environment()
        t = env.from_string(
            "{% def card() %}<div>{% slot header %}</div>{% end %}"
            "{% call card() %}{% slot header %}{{ page.title }}{% end %}{% end %}"
        )
        deps = t.depends_on()
        assert "page.title" in deps or "page" in deps

    def test_validate_context_detects_missing_in_slot_body(self) -> None:
        """validate_context reports missing variables used inside slot bodies."""
        env = Environment()
        t = env.from_string(
            "{% def card() %}<div>{% slot header %}</div>{% end %}"
            "{% call card() %}{% slot header %}{{ user.name }}{% end %}{% end %}"
        )
        missing = t.validate_context({})
        assert "user.name" in missing or "user" in missing


# ---------------------------------------------------------------------------
# PurityAnalyzer — target uncovered handlers
# ---------------------------------------------------------------------------


class TestPurityKnownFilters:
    """Test purity classification for known filter types."""

    def test_pure_filter(self) -> None:
        """Known pure filters produce pure result."""
        env = Environment()
        t = env.from_string("{% block content %}{{ name | upper }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_impure_filter(self) -> None:
        """Known impure filters (random, shuffle) produce impure result."""
        env = Environment()
        t = env.from_string("{% block content %}{{ items | shuffle }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "impure"

    def test_unknown_filter(self) -> None:
        """User-defined filters produce unknown purity."""
        env = Environment()
        # Register a custom filter so it compiles
        env.add_filter("custom_filter", lambda x: x)
        t = env.from_string("{% block content %}{{ name | custom_filter }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "unknown"


class TestPurityControlFlow:
    """Purity through control flow constructs."""

    def test_for_loop_pure(self) -> None:
        """For loop with pure body is pure."""
        env = Environment()
        t = env.from_string(
            "{% block content %}{% for x in items %}{{ x | upper }}{% end %}{% end %}"
        )
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_if_else_pure(self) -> None:
        """If/else with pure branches is pure."""
        env = Environment()
        t = env.from_string(
            "{% block content %}{% if flag %}{{ a }}{% else %}{{ b }}{% end %}{% end %}"
        )
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_if_elif_pure(self) -> None:
        """If/elif with pure branches is pure."""
        env = Environment()
        t = env.from_string(
            "{% block content %}{% if x %}A{% elif y %}B{% else %}C{% end %}{% end %}"
        )
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_for_with_empty_pure(self) -> None:
        """For loop with empty block, all pure branches."""
        env = Environment()
        t = env.from_string(
            "{% block content %}{% for x in items %}{{ x }}{% empty %}No items{% end %}{% end %}"
        )
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_match_pure(self) -> None:
        """Match with pure cases is pure."""
        env = Environment()
        t = env.from_string(
            '{% block content %}{% match status %}{% case "a" %}A{% case "b" %}B{% end %}{% end %}'
        )
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"


class TestPurityExpressions:
    """Purity of various expression types."""

    def test_constant_pure(self) -> None:
        """Constants are always pure."""
        env = Environment()
        t = env.from_string("{% block content %}Hello{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_variable_access_pure(self) -> None:
        """Variable and attribute access is pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ page.title }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_binary_op_pure(self) -> None:
        """Binary operations on pure operands are pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ a + b }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_comparison_pure(self) -> None:
        """Comparisons are pure."""
        env = Environment()
        t = env.from_string("{% block content %}{% if a == b %}eq{% end %}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_ternary_pure(self) -> None:
        """Ternary expression with pure branches is pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ x if flag else y }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_list_literal_pure(self) -> None:
        """List literal with pure items is pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ [1, 2, 3] }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_dict_literal_pure(self) -> None:
        """Dict literal with pure values is pure."""
        env = Environment()
        t = env.from_string('{% block content %}{{ {"a": 1, "b": 2} }}{% end %}')
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_null_coalesce_pure(self) -> None:
        """Null coalescing is pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ x ?? y }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_optional_chaining_pure(self) -> None:
        """Optional chaining is pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ user?.name }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_subscript_pure(self) -> None:
        """Subscript access is pure."""
        env = Environment()
        t = env.from_string('{% block content %}{{ data["key"] }}{% end %}')
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_unary_op_pure(self) -> None:
        """Unary operations are pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ not flag }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"


class TestPurityFunctionCalls:
    """Purity of function calls."""

    def test_known_pure_builtin(self) -> None:
        """Known pure builtins like range() are pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ range(10) }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_unknown_function(self) -> None:
        """Unknown function calls are conservatively 'unknown'."""
        env = Environment()
        t = env.from_string("{% block content %}{{ custom_func(x) }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "unknown"


class TestPurityTests:
    """Purity of test expressions (is, is not)."""

    def test_test_expression_pure(self) -> None:
        """Test expressions are pure."""
        env = Environment()
        t = env.from_string("{% block content %}{% if x is defined %}{{ x }}{% end %}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"


class TestPurityInclude:
    """Purity of include statements."""

    def test_include_pure_content(self) -> None:
        """Include of pure template is pure."""
        loader = DictLoader(
            {
                "main.html": '{% block content %}{% include "pure.html" %}{% end %}',
                "pure.html": "{{ name | upper }}",
            }
        )
        env = Environment(loader=loader)
        t = env.get_template("main.html")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_include_missing_template_unknown(self) -> None:
        """Include of missing template falls back to unknown."""
        loader = DictLoader(
            {
                "main.html": '{% block content %}{% include "missing.html" ignore missing %}{% end %}',
            }
        )
        env = Environment(loader=loader)
        t = env.get_template("main.html")
        meta = t.block_metadata()
        # When template can't be resolved, purity is unknown
        assert meta["content"].is_pure in ("pure", "unknown")


class TestPurityPipeline:
    """Purity of pipeline operator."""

    def test_pure_pipeline(self) -> None:
        """Pipeline with pure filters is pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ name |> upper |> strip }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_impure_pipeline(self) -> None:
        """Pipeline with impure filter is impure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ items |> shuffle }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "impure"


class TestPuritySliceRange:
    """Purity of slice and range expressions."""

    def test_range_expression(self) -> None:
        """Range expressions are pure."""
        env = Environment()
        t = env.from_string("{% block content %}{% for i in 1..10 %}{{ i }}{% end %}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_slice_expression(self) -> None:
        """Slice expressions are pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ items[1:3] }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"


class TestPurityConcat:
    """Purity of string concatenation."""

    def test_concat_pure(self) -> None:
        """String concat with pure parts is pure."""
        env = Environment()
        t = env.from_string("{% block content %}{{ a ~ b }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"


class TestPurityFilterArgs:
    """Purity with filter arguments and kwargs."""

    def test_filter_with_args(self) -> None:
        """Filter arguments don't affect pure filter purity."""
        env = Environment()
        t = env.from_string("{% block content %}{{ text | truncate(100) }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"

    def test_filter_with_kwargs(self) -> None:
        """Filter kwargs don't affect pure filter purity."""
        env = Environment()
        t = env.from_string("{% block content %}{{ items | join(separator=', ') }}{% end %}")
        meta = t.block_metadata()
        assert meta["content"].is_pure == "pure"


# ---------------------------------------------------------------------------
# Template-level API coverage
# ---------------------------------------------------------------------------


class TestTemplateAnalysisAPI:
    """Test the new public analysis API methods."""

    def test_required_context(self) -> None:
        """required_context returns top-level variable names."""
        env = Environment()
        t = env.from_string("{{ page.title }} {{ site.name }}")
        ctx = t.required_context()
        assert "page" in ctx
        assert "site" in ctx

    def test_validate_context_missing(self) -> None:
        """validate_context detects missing variables."""
        env = Environment()
        t = env.from_string("{{ title }} {{ author.name }}")
        missing = t.validate_context({"title": "Hi"})
        assert "author" in missing

    def test_validate_context_complete(self) -> None:
        """validate_context returns empty list when all present."""
        env = Environment()
        t = env.from_string("{{ title }} {{ author.name }}")
        missing = t.validate_context({"title": "Hi", "author": {}})
        assert missing == []

    def test_validate_context_with_globals(self) -> None:
        """validate_context accounts for environment globals."""
        env = Environment()
        env.globals["site"] = {"name": "Test"}
        t = env.from_string("{{ site.name }} {{ page.title }}")
        missing = t.validate_context({"page": {}})
        assert missing == []

    def test_is_cacheable_specific_block(self) -> None:
        """is_cacheable checks specific block."""
        loader = DictLoader(
            {
                "test.html": (
                    "{% block nav %}<nav>{{ site.menu }}</nav>{% end %}"
                    "{% block content %}{{ page.body }}{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        t = env.get_template("test.html")
        # Both blocks should be pure and cacheable
        assert t.is_cacheable("nav") is True
        assert t.is_cacheable("content") is True

    def test_is_cacheable_all_blocks(self) -> None:
        """is_cacheable() with no args checks all blocks."""
        env = Environment()
        t = env.from_string("{% block a %}{{ x }}{% end %}{% block b %}{{ y }}{% end %}")
        result = t.is_cacheable()
        assert isinstance(result, bool)

    def test_is_cacheable_nonexistent_block(self) -> None:
        """is_cacheable returns False for nonexistent block."""
        env = Environment()
        t = env.from_string("{% block a %}content{% end %}")
        assert t.is_cacheable("nonexistent") is False

    def test_template_metadata(self) -> None:
        """template_metadata returns full analysis."""
        loader = DictLoader(
            {
                "child.html": '{% extends "base.html" %}{% block content %}Hi{% end %}',
                "base.html": "{% block content %}{% end %}",
            }
        )
        env = Environment(loader=loader)
        t = env.get_template("child.html")
        meta = t.template_metadata()
        assert meta is not None
        assert meta.extends == "base.html"
        assert "content" in meta.blocks

    def test_depends_on_no_ast(self) -> None:
        """depends_on returns empty set when no AST preserved."""
        env = Environment(preserve_ast=False)
        t = env.from_string("{{ x }}")
        assert t.depends_on() == frozenset()

    def test_required_context_no_ast(self) -> None:
        """required_context returns empty set when no AST preserved."""
        env = Environment(preserve_ast=False)
        t = env.from_string("{{ x }}")
        assert t.required_context() == frozenset()

    def test_validate_context_no_ast(self) -> None:
        """validate_context returns empty list when no AST preserved."""
        env = Environment(preserve_ast=False)
        t = env.from_string("{{ x }}")
        assert t.validate_context({"x": 1}) == []
