"""Tests for the dead-code-elimination partial-evaluation phase."""

from kida import Environment


def _env() -> Environment:
    return Environment(autoescape=False)


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
