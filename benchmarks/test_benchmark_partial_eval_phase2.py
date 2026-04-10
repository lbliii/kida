"""Benchmark partial evaluator Phase 2 optimization gaps.

Establishes baselines for the 4 optimization surfaces targeted by
epic-partial-eval-phase-2.md:
  1. With-block propagation
  2. Match statement elimination
  3. Test expression folding (is defined, is none, etc.)
  4. Mixed-expression sub-expression simplification

Each benchmark pair compares dynamic (no static_context) vs static
(with static_context) rendering. Phase 2 should close the gap between
the two where Phase 1 currently leaves them equivalent.

Run with: pytest benchmarks/test_benchmark_partial_eval_phase2.py --benchmark-only -v
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kida import Environment

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pytest_benchmark.fixture import BenchmarkFixture

    from kida.nodes import Node


# =============================================================================
# Helpers
# =============================================================================


def _count_ast_nodes(body: Sequence[Node]) -> dict[str, int]:
    """Count node types in a template body (shallow + one level deep)."""
    counts: dict[str, int] = {}
    for node in body:
        name = type(node).__name__
        counts[name] = counts.get(name, 0) + 1
        # Recurse into child bodies
        for attr in ("body", "else_", "empty"):
            children = getattr(node, attr, None)
            if children and isinstance(children, (list, tuple)):
                for child in children:
                    if hasattr(child, "lineno"):
                        child_name = type(child).__name__
                        counts[child_name] = counts.get(child_name, 0) + 1
    return counts


def _count_const_and_data(body: Sequence[Node]) -> int:
    """Count Const and Data nodes (the output of successful partial eval)."""
    counts = _count_ast_nodes(body)
    return counts.get("Const", 0) + counts.get("Data", 0)


# =============================================================================
# Static data fixtures
# =============================================================================


@dataclass(frozen=True, slots=True)
class SiteConfig:
    title: str = "Kida Docs"
    theme: str = "dark"
    lang: str = "en"
    debug: bool = False
    version: str = "0.3.4"
    features: tuple[str, ...] = ("streaming", "async", "terminal")


SITE = SiteConfig()

CONFIG = {
    "theme": "dark",
    "sidebar": True,
    "analytics": True,
    "max_items": 50,
    "locale": "en_US",
}

USERS = [
    {"name": "Alice", "age": 30, "role": "admin"},
    {"name": "Bob", "age": 25, "role": "user"},
    {"name": "Carol", "age": 35, "role": "editor"},
]


# =============================================================================
# 1. With-block propagation benchmark
# =============================================================================

WITH_TEMPLATE = """\
{% with title = site.title %}\
{% with theme = site.theme %}\
{% with version = site.version %}\
<header>{{ title }} ({{ version }})</header>
<body class="theme-{{ theme }}">
{% with debug = site.debug %}\
{% if debug %}<div class="debug">Debug ON</div>{% end %}\
{% end %}\
<main>{{ page_content }}</main>
<footer>{{ title }} v{{ version }}</footer>
{% end %}\
{% end %}\
{% end %}\
"""


class TestWithPropagation:
    """Benchmark {% with %} blocks that alias static context values.

    Phase 1 status: With blocks are NOT traversed by _transform_node.
    Expected Phase 2 improvement: title, theme, version, debug all resolve
    at compile time, enabling branch elimination and Data folding.
    """

    def test_with_dynamic(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: everything resolved at runtime."""
        env = Environment(autoescape=False)
        tpl = env.from_string(WITH_TEMPLATE)

        result = benchmark(tpl.render, site=SITE, page_content="Hello")
        assert "Kida Docs" in result
        assert "Debug ON" not in result  # debug=False

    def test_with_static(self, benchmark: BenchmarkFixture) -> None:
        """With static_context: site is known at compile time."""
        env = Environment(autoescape=False)
        tpl = env.from_string(
            WITH_TEMPLATE,
            static_context={"site": SITE},
        )

        result = benchmark(tpl.render, site=SITE, page_content="Hello")
        assert "Kida Docs" in result
        assert "Debug ON" not in result

    def test_with_node_counts(self) -> None:
        """Verify node count baseline (non-benchmark, for metrics)."""
        env = Environment(autoescape=False, preserve_ast=True)

        tpl_dynamic = env.from_string(WITH_TEMPLATE)
        tpl_static = env.from_string(
            WITH_TEMPLATE,
            static_context={"site": SITE},
        )

        dynamic_ast = tpl_dynamic._optimized_ast
        static_ast = tpl_static._optimized_ast

        assert dynamic_ast is not None
        assert static_ast is not None

        dynamic_data = _count_const_and_data(dynamic_ast.body)
        static_data = _count_const_and_data(static_ast.body)

        # Record for comparison. Phase 2 should increase static_data.
        print(
            f"\n  With propagation — dynamic Data+Const: {dynamic_data}, "
            f"static Data+Const: {static_data}"
        )


# =============================================================================
# 2. Match statement elimination benchmark
# =============================================================================

MATCH_TEMPLATE = """\
{% match config.theme %}\
{% case "dark" %}\
<body class="dark-theme">
  <link rel="stylesheet" href="/css/dark.css">
{% case "light" %}\
<body class="light-theme">
  <link rel="stylesheet" href="/css/light.css">
{% case "auto" %}\
<body class="auto-theme">
  <link rel="stylesheet" href="/css/auto.css">
{% case _ %}\
<body class="default-theme">
  <link rel="stylesheet" href="/css/default.css">
{% end %}\
<main>{{ page_content }}</main>
</body>
"""


class TestMatchElimination:
    """Benchmark {% match %} on compile-time-known subjects.

    Phase 1 status: Match nodes are NOT handled by _transform_node or DCE.
    Expected Phase 2 improvement: when config.theme is static, only the
    matching case branch survives; other 3 branches eliminated entirely.
    """

    def test_match_dynamic(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: theme resolved at runtime."""
        env = Environment(autoescape=False)
        tpl = env.from_string(MATCH_TEMPLATE)

        result = benchmark(tpl.render, config=CONFIG, page_content="Hello")
        assert "dark-theme" in result
        assert "light-theme" not in result

    def test_match_static(self, benchmark: BenchmarkFixture) -> None:
        """With static_context: config is known at compile time."""
        env = Environment(autoescape=False)
        tpl = env.from_string(
            MATCH_TEMPLATE,
            static_context={"config": CONFIG},
        )

        result = benchmark(tpl.render, config=CONFIG, page_content="Hello")
        assert "dark-theme" in result
        assert "light-theme" not in result

    def test_match_node_counts(self) -> None:
        """Verify node count baseline."""
        env = Environment(autoescape=False, preserve_ast=True)

        tpl_dynamic = env.from_string(MATCH_TEMPLATE)
        tpl_static = env.from_string(
            MATCH_TEMPLATE,
            static_context={"config": CONFIG},
        )

        dynamic_ast = tpl_dynamic._optimized_ast
        static_ast = tpl_static._optimized_ast

        assert dynamic_ast is not None
        assert static_ast is not None

        dynamic_counts = _count_ast_nodes(dynamic_ast.body)
        static_counts = _count_ast_nodes(static_ast.body)

        print(f"\n  Match elimination — dynamic nodes: {dynamic_counts}")
        print(f"  Match elimination — static  nodes: {static_counts}")


# =============================================================================
# 3. Test expression folding benchmark
# =============================================================================

TEST_GUARD_TEMPLATE = """\
{% if site is defined %}\
<meta name="generator" content="Kida">
{% end %}\
{% if site.debug is none %}\
<meta name="debug" content="not configured">
{% end %}\
{% if config.max_items is number %}\
<meta name="max-items" content="{{ config.max_items }}">
{% end %}\
{% for user in users %}\
{% if loop.index is odd %}\
<div class="odd">{{ user.name }}</div>
{% else %}\
<div class="even">{{ user.name }}</div>
{% end %}\
{% end %}\
{% if missing_var is defined %}\
<div class="hidden">Should not appear</div>
{% end %}\
"""


class TestTestExpressionFolding:
    """Benchmark `is defined`, `is none`, `is number`, `is odd` guards.

    Phase 1 status: Test expressions return _UNRESOLVED from _try_eval.
    Expected Phase 2 improvement: `site is defined` → True (folded),
    `missing_var is defined` → False (branch removed), type tests folded.
    """

    def test_guards_dynamic(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: all tests evaluated at runtime."""
        env = Environment(autoescape=False)
        tpl = env.from_string(TEST_GUARD_TEMPLATE)

        result = benchmark(tpl.render, site=SITE, config=CONFIG, users=USERS)
        assert "Kida" in result
        assert "Should not appear" not in result

    def test_guards_static(self, benchmark: BenchmarkFixture) -> None:
        """With static_context: site and config known at compile time."""
        env = Environment(autoescape=False)
        tpl = env.from_string(
            TEST_GUARD_TEMPLATE,
            static_context={"site": SITE, "config": CONFIG},
        )

        result = benchmark(tpl.render, site=SITE, config=CONFIG, users=USERS)
        assert "Kida" in result
        assert "Should not appear" not in result

    def test_guards_node_counts(self) -> None:
        """Verify node count baseline."""
        env = Environment(autoescape=False, preserve_ast=True)

        tpl_dynamic = env.from_string(TEST_GUARD_TEMPLATE)
        tpl_static = env.from_string(
            TEST_GUARD_TEMPLATE,
            static_context={"site": SITE, "config": CONFIG},
        )

        dynamic_ast = tpl_dynamic._optimized_ast
        static_ast = tpl_static._optimized_ast

        assert dynamic_ast is not None
        assert static_ast is not None

        dynamic_counts = _count_ast_nodes(dynamic_ast.body)
        static_counts = _count_ast_nodes(static_ast.body)

        # Count If nodes specifically — Phase 2 should reduce these
        print(
            f"\n  Test guards — dynamic If count: {dynamic_counts.get('If', 0)}, "
            f"static If count: {static_counts.get('If', 0)}"
        )


# =============================================================================
# 4. Mixed-expression sub-expression simplification benchmark
# =============================================================================

MIXED_EXPR_TEMPLATE = """\
<title>{{ site.title ~ " | " ~ page_title }}</title>
<meta name="features" content="{{ site.features | join(", ") }}">
<meta name="item-count" content="{{ len(users) + config.max_items }}">
<div class="{{ "sidebar-" ~ config.theme if config.sidebar else "no-sidebar" }}">
{% for user in users %}\
<span>{{ site.title ~ ": " ~ user.name }}</span>
{% end %}\
</div>
"""


class TestMixedExprSimplification:
    """Benchmark expressions mixing static and dynamic operands.

    Phase 1 status: _transform_expr falls through for Concat, FuncCall,
    CondExpr sub-expressions — the whole expression stays dynamic even
    when sub-parts (site.title, config.theme) are resolvable.
    Expected Phase 2 improvement: static sub-expressions folded to Const,
    enabling more f-string coalescing downstream.
    """

    def test_mixed_dynamic(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: everything resolved at runtime."""
        env = Environment(autoescape=False)
        tpl = env.from_string(MIXED_EXPR_TEMPLATE)

        result = benchmark(
            tpl.render,
            site=SITE,
            config=CONFIG,
            users=USERS,
            page_title="Home",
        )
        assert "Kida Docs | Home" in result

    def test_mixed_static(self, benchmark: BenchmarkFixture) -> None:
        """With static_context: site and config known at compile time."""
        env = Environment(autoescape=False)
        tpl = env.from_string(
            MIXED_EXPR_TEMPLATE,
            static_context={"site": SITE, "config": CONFIG},
        )

        result = benchmark(
            tpl.render,
            site=SITE,
            config=CONFIG,
            users=USERS,
            page_title="Home",
        )
        assert "Kida Docs | Home" in result

    def test_mixed_node_counts(self) -> None:
        """Verify node count baseline."""
        env = Environment(autoescape=False, preserve_ast=True)

        tpl_dynamic = env.from_string(MIXED_EXPR_TEMPLATE)
        tpl_static = env.from_string(
            MIXED_EXPR_TEMPLATE,
            static_context={"site": SITE, "config": CONFIG},
        )

        dynamic_ast = tpl_dynamic._optimized_ast
        static_ast = tpl_static._optimized_ast

        assert dynamic_ast is not None
        assert static_ast is not None

        dynamic_data = _count_const_and_data(dynamic_ast.body)
        static_data = _count_const_and_data(static_ast.body)

        print(
            f"\n  Mixed expr — dynamic Data+Const: {dynamic_data}, static Data+Const: {static_data}"
        )


# =============================================================================
# 5. Coverage map: which _try_eval paths return _UNRESOLVED?
# =============================================================================


class TestTryEvalCoverageMap:
    """Non-benchmark tests that document which node types fall through.

    These tests compile templates with static_context and inspect the
    resulting AST to verify which expressions were folded vs preserved.
    This establishes the Phase 1 baseline for Phase 2 to improve.
    """

    def test_with_blocks_not_propagated(self) -> None:
        """With blocks currently don't propagate into body."""
        env = Environment(autoescape=False, preserve_ast=True)
        tpl = env.from_string(
            "{% with x = site.title %}{{ x }}{% end %}",
            static_context={"site": SITE},
        )
        ast = tpl._optimized_ast
        assert ast is not None

        # Check if the Output node was folded to Data
        has_output = any(type(n).__name__ == "With" for n in ast.body)
        has_data_only = all(type(n).__name__ == "Data" for n in ast.body)

        # Phase 1: With block preserved, Output inside not folded
        # Phase 2: should fold to Data("Kida Docs")
        print(f"\n  With propagation: has_with={has_output}, all_data={has_data_only}")

    def test_match_not_eliminated(self) -> None:
        """Match statements currently not eliminated by DCE or partial eval."""
        env = Environment(autoescape=False, preserve_ast=True)
        tpl = env.from_string(
            '{% match "dark" %}{% case "dark" %}DARK{% case "light" %}LIGHT{% case _ %}OTHER{% end %}',
            static_context={},
        )
        ast = tpl._optimized_ast
        assert ast is not None

        has_match = any(type(n).__name__ == "Match" for n in ast.body)
        # Phase 1: Match preserved (not eliminated)
        # Phase 2: should fold to Data("DARK")
        print(f"\n  Match elimination: has_match={has_match}")

    def test_test_expr_not_folded(self) -> None:
        """Test expressions (is defined) not folded by _try_eval."""
        env = Environment(autoescape=False, preserve_ast=True)
        tpl = env.from_string(
            "{% if site is defined %}YES{% else %}NO{% end %}",
            static_context={"site": SITE},
        )
        ast = tpl._optimized_ast
        assert ast is not None

        # Check if the If was eliminated
        has_if = any(type(n).__name__ == "If" for n in ast.body)
        has_data_only = all(type(n).__name__ == "Data" for n in ast.body)

        # Phase 1: If preserved (Test not evaluated)
        # Phase 2: should fold to Data("YES")
        print(f"\n  Test folding: has_if={has_if}, all_data={has_data_only}")

    def test_concat_subexpr_not_simplified(self) -> None:
        """Concat with mixed static/dynamic operands not partially simplified."""
        env = Environment(autoescape=False, preserve_ast=True)
        tpl = env.from_string(
            '{{ site.title ~ " | " ~ page_title }}',
            static_context={"site": SITE},
        )
        ast = tpl._optimized_ast
        assert ast is not None

        # Check if any sub-expressions were folded to Const
        # Phase 1: entire Concat stays as-is
        # Phase 2: site.title sub-expr should fold to Const("Kida Docs")
        counts = _count_ast_nodes(ast.body)
        print(f"\n  Concat sub-expr: node types = {counts}")
