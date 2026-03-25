"""Tests for kida.analysis.type_checker template type checking."""

from __future__ import annotations

from kida import Environment
from kida.analysis.type_checker import check_types


def _get_issues(source: str):
    """Parse a template and run type checks on its AST."""
    env = Environment()
    tpl = env.from_string(source)
    return check_types(tpl._optimized_ast)


# ---------------------------------------------------------------------------
# No declarations => no issues
# ---------------------------------------------------------------------------


class TestNoDeclarations:
    def test_template_without_declaration(self):
        """Templates without {% template %} return empty list."""
        issues = _get_issues("{{ name }} {{ title }}")
        assert issues == []

    def test_empty_template(self):
        issues = _get_issues("")
        assert issues == []


# ---------------------------------------------------------------------------
# Undeclared variable access
# ---------------------------------------------------------------------------


class TestUndeclaredVar:
    def test_undeclared_variable(self):
        issues = _get_issues("{% template name: str %}{{ name }} {{ age }}")
        undeclared = [i for i in issues if i.rule == "undeclared-var"]
        assert len(undeclared) == 1
        assert "age" in undeclared[0].message

    def test_all_declared_no_issues(self):
        issues = _get_issues("{% template name: str, age: int %}{{ name }} {{ age }}")
        undeclared = [i for i in issues if i.rule == "undeclared-var"]
        assert undeclared == []

    def test_builtin_names_not_flagged(self):
        """Built-in names (range, loop, True, etc.) should not be flagged."""
        issues = _get_issues(
            "{% template items: list %}{% for i in range(10) %}{{ loop.index }}{% end %}{{ items }}"
        )
        undeclared = [i for i in issues if i.rule == "undeclared-var"]
        assert undeclared == []


# ---------------------------------------------------------------------------
# Unused declared variables
# ---------------------------------------------------------------------------


class TestUnusedDeclared:
    def test_unused_declared_variable(self):
        issues = _get_issues("{% template name: str, title: str %}{{ name }}")
        unused = [i for i in issues if i.rule == "unused-declared"]
        assert len(unused) == 1
        assert "title" in unused[0].message

    def test_all_used_no_unused(self):
        issues = _get_issues("{% template name: str, title: str %}{{ name }} {{ title }}")
        unused = [i for i in issues if i.rule == "unused-declared"]
        assert unused == []


# ---------------------------------------------------------------------------
# Typo suggestions
# ---------------------------------------------------------------------------


class TestTypoSuggestion:
    def test_typo_suggests_similar_name(self):
        """A variable close to a declared name should produce a typo suggestion."""
        issues = _get_issues("{% template username: str %}{{ usernme }}")
        typos = [i for i in issues if i.rule == "typo-suggestion"]
        assert len(typos) == 1
        assert "username" in typos[0].message
        assert "did you mean" in typos[0].message

    def test_no_typo_for_totally_different_name(self):
        """A name that is very different should be undeclared-var, not typo."""
        issues = _get_issues("{% template name: str %}{{ completely_different_variable }}")
        typos = [i for i in issues if i.rule == "typo-suggestion"]
        assert typos == []
        undeclared = [i for i in issues if i.rule == "undeclared-var"]
        assert len(undeclared) == 1


# ---------------------------------------------------------------------------
# Local variables (set, let, for) recognized
# ---------------------------------------------------------------------------


class TestLocalVariables:
    def test_set_defines_local(self):
        """{% set %} should define a local, not trigger undeclared."""
        issues = _get_issues(
            '{% template name: str %}{% set greeting = "Hello" %}{{ greeting }} {{ name }}'
        )
        undeclared = [i for i in issues if i.rule in ("undeclared-var", "typo-suggestion")]
        assert undeclared == []

    def test_let_defines_local(self):
        """{% let %} should define a local."""
        issues = _get_issues(
            '{% template name: str %}{% let greeting = "Hi" %}{{ greeting }} {{ name }}'
        )
        undeclared = [i for i in issues if i.rule in ("undeclared-var", "typo-suggestion")]
        assert undeclared == []

    def test_for_loop_variable_is_local(self):
        """For-loop target variables should not be flagged."""
        issues = _get_issues("{% template items: list %}{% for item in items %}{{ item }}{% end %}")
        undeclared = [i for i in issues if i.rule in ("undeclared-var", "typo-suggestion")]
        assert undeclared == []

    def test_for_loop_tuple_unpacking(self):
        """Tuple unpacking in for loops defines locals."""
        issues = _get_issues(
            "{% template pairs: list %}{% for key, value in pairs %}{{ key }}={{ value }}{% end %}"
        )
        undeclared = [i for i in issues if i.rule in ("undeclared-var", "typo-suggestion")]
        assert undeclared == []

    def test_def_params_are_local(self):
        """Function parameters inside {% def %} are local."""
        issues = _get_issues(
            "{% template name: str %}{% def greet(person) %}Hello {{ person }}{% end %}{{ name }}"
        )
        undeclared = [i for i in issues if i.rule in ("undeclared-var", "typo-suggestion")]
        assert undeclared == []


# ---------------------------------------------------------------------------
# Mixed scenarios
# ---------------------------------------------------------------------------


class TestMixedScenarios:
    def test_multiple_issues(self):
        """Multiple undeclared and unused can appear together."""
        issues = _get_issues("{% template a: str, b: str, c: str %}{{ a }} {{ x }} {{ y }}")
        undeclared = [i for i in issues if i.rule in ("undeclared-var", "typo-suggestion")]
        unused = [i for i in issues if i.rule == "unused-declared"]
        assert len(undeclared) == 2  # x and y
        assert len(unused) == 2  # b and c

    def test_issues_sorted_by_line(self):
        """Issues should come back sorted by (lineno, col_offset)."""
        issues = _get_issues("{% template name: str %}{{ unknown1 }} {{ unknown2 }}")
        if len(issues) >= 2:
            for i in range(len(issues) - 1):
                assert (issues[i].lineno, issues[i].col_offset) <= (
                    issues[i + 1].lineno,
                    issues[i + 1].col_offset,
                )
