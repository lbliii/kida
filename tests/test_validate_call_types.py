"""Tests for type-aware call-site validation (Sprint 3)."""

from __future__ import annotations

import pytest

from kida import Environment
from kida.analysis.analyzer import BlockAnalyzer


@pytest.fixture
def env() -> Environment:
    return Environment()


def _get_mismatches(env: Environment, source: str):
    tpl = env.from_string(source)
    assert tpl._optimized_ast is not None
    return BlockAnalyzer().validate_call_types(tpl._optimized_ast)


class TestValidateCallTypes:
    """BlockAnalyzer.validate_call_types()"""

    def test_no_annotations_no_mismatches(self, env):
        """Defs without annotations produce no mismatches."""
        src = '{% def greet(name) %}Hi {{ name }}{% end %}{{ greet("Alice") }}'
        assert _get_mismatches(env, src) == []

    def test_correct_types_no_mismatches(self, env):
        """Literal args matching annotations produce no mismatches."""
        src = '{% def card(title: str, count: int) %}{{ title }}{% end %}{{ card("Hi", 5) }}'
        assert _get_mismatches(env, src) == []

    def test_str_param_gets_int(self, env):
        """Passing int literal to str param is a mismatch."""
        src = "{% def card(title: str) %}{{ title }}{% end %}{{ card(42) }}"
        mm = _get_mismatches(env, src)
        assert len(mm) == 1
        assert mm[0].def_name == "card"
        assert mm[0].param_name == "title"
        assert mm[0].expected == "str"
        assert mm[0].actual_type == "int"
        assert mm[0].actual_value == 42

    def test_int_param_gets_str(self, env):
        """Passing str literal to int param is a mismatch."""
        src = '{% def show(count: int) %}{{ count }}{% end %}{{ show("five") }}'
        mm = _get_mismatches(env, src)
        assert len(mm) == 1
        assert mm[0].param_name == "count"
        assert mm[0].expected == "int"
        assert mm[0].actual_type == "str"

    def test_float_accepts_int(self, env):
        """int literal is acceptable for float param (standard Python coercion)."""
        src = "{% def plot(x: float) %}{{ x }}{% end %}{{ plot(3) }}"
        assert _get_mismatches(env, src) == []

    def test_float_rejects_str(self, env):
        """str literal is not acceptable for float param."""
        src = '{% def plot(x: float) %}{{ x }}{% end %}{{ plot("3.14") }}'
        mm = _get_mismatches(env, src)
        assert len(mm) == 1
        assert mm[0].expected == "float"
        assert mm[0].actual_type == "str"

    def test_bool_param(self, env):
        """Bool annotation validates correctly."""
        src = "{% def toggle(on: bool) %}{{ on }}{% end %}{{ toggle(true) }}"
        assert _get_mismatches(env, src) == []

    def test_bool_param_gets_str(self, env):
        """str literal to bool param is a mismatch."""
        src = '{% def toggle(on: bool) %}{{ on }}{% end %}{{ toggle("yes") }}'
        mm = _get_mismatches(env, src)
        assert len(mm) == 1
        assert mm[0].expected == "bool"

    def test_union_type_str_or_none(self, env):
        """str | None annotation accepts both str and None."""
        src = '{% def card(title: str | None) %}{{ title }}{% end %}{{ card("Hi") }}'
        assert _get_mismatches(env, src) == []

        src2 = "{% def card(title: str | None) %}{{ title }}{% end %}{{ card(none) }}"
        assert _get_mismatches(env, src2) == []

    def test_union_type_rejects_wrong(self, env):
        """str | None annotation rejects int."""
        src = "{% def card(title: str | None) %}{{ title }}{% end %}{{ card(42) }}"
        mm = _get_mismatches(env, src)
        assert len(mm) == 1
        assert mm[0].expected == "str | None"

    def test_keyword_args(self, env):
        """Type checking works for keyword arguments."""
        src = "{% def card(title: str) %}{{ title }}{% end %}{{ card(title=123) }}"
        mm = _get_mismatches(env, src)
        assert len(mm) == 1
        assert mm[0].param_name == "title"
        assert mm[0].actual_value == 123

    def test_mixed_positional_and_keyword(self, env):
        """Both positional and keyword args are checked."""
        src = '{% def card(title: str, count: int) %}{{ title }}{% end %}{{ card(42, count="x") }}'
        mm = _get_mismatches(env, src)
        assert len(mm) == 2
        names = {m.param_name for m in mm}
        assert names == {"title", "count"}

    def test_variable_args_skipped(self, env):
        """Non-Const (variable) args are not checked."""
        src = "{% def card(title: str) %}{{ title }}{% end %}{{ card(some_var) }}"
        assert _get_mismatches(env, src) == []

    def test_unknown_annotation_skipped(self, env):
        """Unknown annotation types are gracefully skipped."""
        src = '{% def card(items: MyList) %}{{ items }}{% end %}{{ card("hi") }}'
        assert _get_mismatches(env, src) == []

    def test_multiple_defs(self, env):
        """Type mismatches detected across multiple defs."""
        src = (
            "{% def a(x: int) %}{{ x }}{% end %}"
            "{% def b(y: str) %}{{ y }}{% end %}"
            '{{ a("bad") }}{{ b(42) }}'
        )
        mm = _get_mismatches(env, src)
        assert len(mm) == 2
        def_names = {m.def_name for m in mm}
        assert def_names == {"a", "b"}

    def test_call_block_type_check(self, env):
        """Type checking works inside {% call %} blocks."""
        src = (
            "{% def card(title: str) %}<div>{% slot %}</div>{% end %}"
            "{% call card(123) %}body{% end %}"
        )
        mm = _get_mismatches(env, src)
        assert len(mm) == 1
        assert mm[0].def_name == "card"
        assert mm[0].actual_value == 123

    def test_no_defs_no_mismatches(self, env):
        """Template with no defs produces no mismatches."""
        src = "<p>Hello</p>"
        assert _get_mismatches(env, src) == []

    def test_none_literal(self, env):
        """None annotation accepts none literal."""
        src = "{% def f(x: None) %}{{ x }}{% end %}{{ f(none) }}"
        assert _get_mismatches(env, src) == []


class TestValidateCallTypesCLI:
    """Type mismatches surfaced via kida check --validate-calls."""

    def test_type_mismatch_reported(self, tmp_path, capsys):
        """kida check --validate-calls reports type mismatches."""
        from kida.cli import main

        (tmp_path / "bad.html").write_text(
            "{% def card(title: str) %}{{ title }}{% end %}{{ card(42) }}"
        )
        rc = main(["check", str(tmp_path), "--validate-calls"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "type:" in err
        assert "card()" in err
        assert "title" in err
        assert "expects str" in err
        assert "got int" in err

    def test_no_mismatch_clean(self, tmp_path, capsys):
        """kida check --validate-calls passes when types match."""
        from kida.cli import main

        (tmp_path / "good.html").write_text(
            '{% def card(title: str) %}{{ title }}{% end %}{{ card("hi") }}'
        )
        rc = main(["check", str(tmp_path), "--validate-calls"])
        assert rc == 0

    def test_imported_type_mismatch_reported(self, tmp_path, capsys):
        """kida check validates literal args against imported def metadata."""
        from kida.cli import main

        (tmp_path / "components.html").write_text("{% def card(title: str) %}{{ title }}{% end %}")
        (tmp_path / "page.html").write_text(
            '{% from "components.html" import card %}{{ card(42) }}'
        )

        rc = main(["check", str(tmp_path), "--validate-calls"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "K-CMP-002" in err
        assert "card()" in err
        assert "got int" in err
