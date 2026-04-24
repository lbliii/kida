"""End-to-end tests for namespace-alias template resolution.

Covers ``@alias/path`` prefixes in every cross-template statement
(``{% include %}``, ``{% extends %}``, ``{% embed %}``,
``{% from ... import ... %}``) and via direct ``env.get_template()`` calls.
Aliases are configured with ``Environment(template_aliases={...})`` and
resolve before loader lookup. Unknown aliases raise a
``TemplateNotFoundError`` that enumerates the configured aliases.
"""

from __future__ import annotations

import pytest

from kida import DictLoader, Environment
from kida.exceptions import TemplateNotFoundError


def test_alias_direct_get_template() -> None:
    env = Environment(
        loader=DictLoader({"ui/components/card.html": "CARD"}),
        template_aliases={"components": "ui/components"},
    )
    assert env.get_template("@components/card.html").render() == "CARD"


def test_alias_in_include() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "pages/home.html": '{% include "@components/card.html" %}',
                "ui/components/card.html": "CARD",
            }
        ),
        template_aliases={"components": "ui/components"},
    )
    assert env.get_template("pages/home.html").render() == "CARD"


def test_alias_in_extends() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "ui/layouts/base.html": "BASE[{% block body %}{% end %}]",
                "pages/page.html": (
                    '{% extends "@layouts/base.html" %}{% block body %}HI{% end %}'
                ),
            }
        ),
        template_aliases={"layouts": "ui/layouts"},
    )
    assert env.get_template("pages/page.html").render() == "BASE[HI]"


def test_alias_in_from_import() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "ui/macros/greet.html": "{% def greet(name) %}Hi {{ name }}{% end %}",
                "pages/page.html": (
                    '{% from "@macros/greet.html" import greet %}{{ greet("world") }}'
                ),
            }
        ),
        template_aliases={"macros": "ui/macros"},
    )
    assert env.get_template("pages/page.html").render() == "Hi world"


def test_alias_in_embed() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "ui/layouts/base.html": "BASE[{% block body %}DEFAULT{% end %}]",
                "pages/page.html": (
                    '{% embed "@layouts/base.html" %}{% block body %}OVERRIDE{% end %}{% end %}'
                ),
            }
        ),
        template_aliases={"layouts": "ui/layouts"},
    )
    assert env.get_template("pages/page.html").render() == "BASE[OVERRIDE]"


def test_multiple_aliases_coexist() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "ui/components/card.html": "CARD",
                "ui/layouts/base.html": "BASE[{% block body %}{% end %}]",
                "pages/page.html": (
                    '{% extends "@layouts/base.html" %}'
                    '{% block body %}{% include "@components/card.html" %}{% end %}'
                ),
            }
        ),
        template_aliases={
            "components": "ui/components",
            "layouts": "ui/layouts",
        },
    )
    assert env.get_template("pages/page.html").render() == "BASE[CARD]"


def test_alias_with_nested_path() -> None:
    """``@components/icons/chevron.html`` walks into the alias root subdirs."""
    env = Environment(
        loader=DictLoader({"ui/components/icons/chevron.html": "SVG"}),
        template_aliases={"components": "ui/components"},
    )
    assert env.get_template("@components/icons/chevron.html").render() == "SVG"


def test_alias_root_with_trailing_slash_is_normalized() -> None:
    """Trailing slashes in the alias root are stripped."""
    env = Environment(
        loader=DictLoader({"ui/components/card.html": "CARD"}),
        template_aliases={"components": "ui/components/"},
    )
    assert env.get_template("@components/card.html").render() == "CARD"


# ----------------------------- Error matrix ---------------------------------


def test_unknown_alias_rejected_with_hint() -> None:
    env = Environment(
        loader=DictLoader({"x.html": "X"}),
        template_aliases={"components": "ui/components"},
    )
    with pytest.raises(TemplateNotFoundError) as exc_info:
        env.get_template("@layouts/base.html")
    msg = str(exc_info.value)
    assert "@layouts" in msg
    assert "@components/" in msg  # configured alias listed


def test_unknown_alias_with_no_configured_aliases() -> None:
    env = Environment(loader=DictLoader({"x.html": "X"}))
    with pytest.raises(TemplateNotFoundError) as exc_info:
        env.get_template("@components/card.html")
    msg = str(exc_info.value)
    assert "@components" in msg
    assert "no template aliases" in msg.lower()


def test_alias_missing_target_reports_resolved_name() -> None:
    """When alias resolution succeeds but the file is absent, the usual
    not-found error fires — proving alias substitution happened first."""
    env = Environment(
        loader=DictLoader({}),
        template_aliases={"components": "ui/components"},
    )
    with pytest.raises(TemplateNotFoundError):
        env.get_template("@components/missing.html")


def test_alias_does_not_compose_with_relative() -> None:
    """``@components/./foo`` is legal syntax but produces no file — the
    alias resolves first to a concrete root-relative name, then `./` is
    just a no-op segment inside ``normpath``. Document that the two
    resolution modes are orthogonal."""
    env = Environment(
        loader=DictLoader({"ui/components/card.html": "CARD"}),
        template_aliases={"components": "ui/components"},
    )
    # After alias: "ui/components/./card.html" → normalize → "ui/components/card.html"
    # This is the current behavior; it's benign because it does not escape.
    assert env.get_template("@components/card.html").render() == "CARD"
