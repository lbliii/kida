"""End-to-end tests for relative template resolution.

Covers ``./`` and ``../`` path resolution across every cross-template
statement: ``{% include %}``, ``{% extends %}``, ``{% embed %}``, and
``{% from ... import ... %}``. Resolution is performed against the
calling template's directory; absolute (root-relative) names remain
unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kida import DictLoader, Environment, FileSystemLoader
from kida.exceptions import TemplateNotFoundError

# ----------------------------- DictLoader matrix -----------------------------


def test_include_relative_sibling() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "pages/about.html": '{% include "./card.html" %}',
                "pages/card.html": "CARD",
            }
        )
    )
    assert env.get_template("pages/about.html").render() == "CARD"


def test_include_relative_parent() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "pages/blog/post.html": '{% include "../nav.html" %} BODY',
                "pages/nav.html": "NAV",
            }
        )
    )
    assert env.get_template("pages/blog/post.html").render() == "NAV BODY"


def test_include_relative_deep_parent() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "a/b/c/d.html": '{% include "../../../shared.html" %}',
                "shared.html": "SHARED",
            }
        )
    )
    assert env.get_template("a/b/c/d.html").render() == "SHARED"


def test_extends_relative() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "pages/base.html": "BASE[{% block body %}{% end %}]",
                "pages/child.html": ('{% extends "./base.html" %}{% block body %}HI{% end %}'),
            }
        )
    )
    assert env.get_template("pages/child.html").render() == "BASE[HI]"


def test_from_import_relative() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "pages/macros.html": ("{% def greet(name) %}Hi {{ name }}{% end %}"),
                "pages/page.html": ('{% from "./macros.html" import greet %}{{ greet("world") }}'),
            }
        )
    )
    assert env.get_template("pages/page.html").render() == "Hi world"


def test_from_import_relative_with_alias() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "pages/macros.html": "{% def original() %}X{% end %}",
                "pages/page.html": (
                    '{% from "./macros.html" import original as renamed %}{{ renamed() }}'
                ),
            }
        )
    )
    assert env.get_template("pages/page.html").render() == "X"


def test_embed_relative() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "pages/base.html": "BASE[{% block body %}DEFAULT{% end %}]",
                "pages/page.html": (
                    '{% embed "./base.html" %}{% block body %}OVERRIDE{% end %}{% end %}'
                ),
            }
        )
    )
    assert env.get_template("pages/page.html").render() == "BASE[OVERRIDE]"


def test_absolute_paths_unchanged() -> None:
    """Existing absolute (root-relative) references keep working byte-identical."""
    env = Environment(
        loader=DictLoader(
            {
                "pages/about.html": '{% include "components/card.html" %}',
                "components/card.html": "CARD",
            }
        )
    )
    assert env.get_template("pages/about.html").render() == "CARD"


def test_nested_relative_resolves_against_current_template() -> None:
    """A relative include inside an already-included template resolves
    against THAT template's directory, not the original caller."""
    env = Environment(
        loader=DictLoader(
            {
                "pages/a.html": '{% include "./nested/b.html" %}',
                "pages/nested/b.html": '{% include "./c.html" %} END',
                "pages/nested/c.html": "INNER",
            }
        )
    )
    assert env.get_template("pages/a.html").render() == "INNER END"


# ----------------------------- Error matrix ---------------------------------


def test_relative_escape_rejected() -> None:
    """`../../../etc/passwd` from a shallow caller raises."""
    env = Environment(
        loader=DictLoader(
            {
                "a/b.html": '{% include "../../../etc/passwd" %}',
            }
        )
    )
    with pytest.raises(TemplateNotFoundError) as exc_info:
        env.get_template("a/b.html").render()
    msg = str(exc_info.value).lower()
    assert "escape" in msg
    assert "include" in msg


def test_relative_without_caller_rejected() -> None:
    """Calling ``env.get_template('./x')`` directly from Python raises."""
    env = Environment(loader=DictLoader({"x.html": "X"}))
    with pytest.raises(TemplateNotFoundError) as exc_info:
        env.get_template("./x.html")
    assert "caller" in str(exc_info.value).lower()


def test_relative_missing_target_enriched_with_caller() -> None:
    """A relative include that points at a missing file reports the caller."""
    env = Environment(
        loader=DictLoader(
            {
                "pages/about.html": '{% include "./missing.html" %}',
            }
        )
    )
    with pytest.raises(TemplateNotFoundError) as exc_info:
        env.get_template("pages/about.html").render()
    msg = str(exc_info.value)
    assert "pages/about.html" in msg
    assert "include" in msg


# ----------------------------- FileSystemLoader parity ----------------------


def test_filesystem_loader_relative_include(tmp_path: Path) -> None:
    """Relative resolution works identically with FileSystemLoader."""
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "about.html").write_text(
        '{% include "./card.html" %}',
    )
    (tmp_path / "pages" / "card.html").write_text("CARD")
    env = Environment(loader=FileSystemLoader(tmp_path))
    assert env.get_template("pages/about.html").render() == "CARD"


def test_filesystem_loader_relative_parent(tmp_path: Path) -> None:
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "blog").mkdir()
    (tmp_path / "shared.html").write_text("SHARED")
    (tmp_path / "pages" / "blog" / "post.html").write_text(
        '{% include "../../shared.html" %}',
    )
    env = Environment(loader=FileSystemLoader(tmp_path))
    assert env.get_template("pages/blog/post.html").render() == "SHARED"


def test_filesystem_loader_escape_rejected(tmp_path: Path) -> None:
    """FileSystemLoader's traversal guard still fires when resolution
    would land outside every search root."""
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "b.html").write_text(
        '{% include "../../../etc/passwd" %}',
    )
    env = Environment(loader=FileSystemLoader(tmp_path / "pages"))
    with pytest.raises(TemplateNotFoundError):
        env.get_template("b.html").render()


# ----------------------------- Refactor-safety demo -------------------------


def test_folder_move_with_relative_imports_is_zero_edit() -> None:
    """Moving an entire folder leaves relative references intact —
    this is the core user-feedback scenario.
    """
    # Initial layout
    env_before = Environment(
        loader=DictLoader(
            {
                "skills/page.html": ('{% include "./_status.html" %}{% include "./_trust.html" %}'),
                "skills/_status.html": "STATUS",
                "skills/_trust.html": "TRUST",
            }
        )
    )
    assert env_before.get_template("skills/page.html").render() == "STATUSTRUST"

    # After moving skills/ → library/skills/ — ZERO template edits
    env_after = Environment(
        loader=DictLoader(
            {
                "library/skills/page.html": (
                    '{% include "./_status.html" %}{% include "./_trust.html" %}'
                ),
                "library/skills/_status.html": "STATUS",
                "library/skills/_trust.html": "TRUST",
            }
        )
    )
    assert env_after.get_template("library/skills/page.html").render() == "STATUSTRUST"
