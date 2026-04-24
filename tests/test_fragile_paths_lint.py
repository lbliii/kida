"""Tests for the `kida check --lint-fragile-paths` rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida import DictLoader, Environment
from kida.analysis.fragile_paths import check_fragile_paths
from kida.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _ast(source: str, caller: str) -> object:
    env = Environment(loader=DictLoader({caller: source}))
    tpl = env.get_template(caller)
    return tpl._optimized_ast


def test_same_folder_include_is_flagged() -> None:
    ast = _ast('{% include "pages/card.html" %}', "pages/about.html")
    issues = check_fragile_paths(ast, "pages/about.html")
    assert len(issues) == 1
    assert issues[0].statement == "include"
    assert issues[0].target == "pages/card.html"
    assert issues[0].suggestion == "./card.html"


def test_cross_folder_include_is_not_flagged() -> None:
    """A target in a different folder is left alone — likely a shared library."""
    ast = _ast('{% include "components/card.html" %}', "pages/about.html")
    assert check_fragile_paths(ast, "pages/about.html") == []


def test_already_relative_is_not_flagged() -> None:
    ast = _ast('{% include "./card.html" %}', "pages/about.html")
    assert check_fragile_paths(ast, "pages/about.html") == []


def test_already_alias_is_not_flagged() -> None:
    ast = _ast('{% include "@components/card.html" %}', "pages/about.html")
    assert check_fragile_paths(ast, "pages/about.html") == []


def test_root_caller_is_not_flagged() -> None:
    """Caller at root has no folder anchor — no suggestion to make."""
    ast = _ast('{% include "other.html" %}', "index.html")
    assert check_fragile_paths(ast, "index.html") == []


def test_nested_same_folder_is_not_flagged() -> None:
    """Only exact-folder matches flag; nested cases are left alone to avoid
    false positives."""
    ast = _ast('{% include "pages/nested/card.html" %}', "pages/about.html")
    assert check_fragile_paths(ast, "pages/about.html") == []


def test_dynamic_include_is_not_flagged() -> None:
    """Non-constant target expressions skip the rule."""
    ast = _ast(
        '{% include "components/" + widget_type + ".html" %}',
        "pages/about.html",
    )
    assert check_fragile_paths(ast, "pages/about.html") == []


def test_extends_is_flagged() -> None:
    ast = _ast(
        '{% extends "pages/base.html" %}{% block body %}{% end %}',
        "pages/child.html",
    )
    issues = check_fragile_paths(ast, "pages/child.html")
    assert len(issues) == 1
    assert issues[0].statement == "extends"
    assert issues[0].suggestion == "./base.html"


def test_embed_is_flagged() -> None:
    ast = _ast(
        '{% embed "pages/base.html" %}{% block body %}X{% end %}{% end %}',
        "pages/child.html",
    )
    issues = check_fragile_paths(ast, "pages/child.html")
    assert [i.statement for i in issues] == ["embed"]


def test_from_import_is_flagged() -> None:
    ast = _ast(
        '{% from "pages/macros.html" import greet %}',
        "pages/child.html",
    )
    issues = check_fragile_paths(ast, "pages/child.html")
    assert [i.statement for i in issues] == ["from"]
    assert issues[0].suggestion == "./macros.html"


def test_import_is_flagged() -> None:
    ast = _ast(
        '{% import "pages/macros.html" as m %}',
        "pages/child.html",
    )
    issues = check_fragile_paths(ast, "pages/child.html")
    assert [i.statement for i in issues] == ["import"]


# ----------------------------- CLI integration ------------------------------


def test_cli_lint_fragile_paths_exit_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`kida check --lint-fragile-paths` reports suggestions and exits 1."""
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "about.html").write_text('{% include "pages/card.html" %}')
    (tmp_path / "pages" / "card.html").write_text("CARD")

    exit_code = main(["check", str(tmp_path), "--lint-fragile-paths"])
    assert exit_code == 1

    err = capsys.readouterr().err
    assert "lint/fragile-path" in err
    assert "pages/card.html" in err
    assert "./card.html" in err


def test_cli_lint_flag_default_off(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Without the flag the lint is silent — default `kida check` is unchanged."""
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "about.html").write_text('{% include "pages/card.html" %}')
    (tmp_path / "pages" / "card.html").write_text("CARD")

    exit_code = main(["check", str(tmp_path)])
    assert exit_code == 0

    err = capsys.readouterr().err
    assert "lint/fragile-path" not in err
