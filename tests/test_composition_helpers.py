"""Behavioral contract tests for the public ``kida.composition`` helpers."""

from __future__ import annotations

from types import SimpleNamespace

from kida import BlockMetadata, DictLoader, Environment
from kida.composition import (
    block_role_for_framework,
    get_structure,
    validate_block_exists,
    validate_template_block,
)


def _composition_environment(*, preserve_ast: bool = True) -> Environment:
    return Environment(
        loader=DictLoader(
            {
                "base.html": (
                    "{% block shell %}base{% end %}"
                    '{% region nav(current="/") %}<nav>{{ current }}</nav>{% end %}'
                ),
                "child.html": (
                    '{% extends "base.html" %}{% block content %}{{ page.title }}{% end %}'
                ),
                "broken.html": "{% if %}",
            }
        ),
        preserve_ast=preserve_ast,
    )


class TestValidateBlockExists:
    def test_accepts_local_inherited_and_region_blocks(self) -> None:
        env = _composition_environment()

        assert validate_block_exists(env, "child.html", "content") is True
        assert validate_block_exists(env, "child.html", "shell") is True
        assert validate_block_exists(env, "child.html", "nav") is True

    def test_rejects_empty_missing_and_unknown_blocks(self) -> None:
        env = _composition_environment()

        assert validate_block_exists(env, "child.html", "") is False
        assert validate_block_exists(env, "child.html", "missing") is False
        assert validate_block_exists(env, "missing.html", "content") is False

    def test_syntax_failure_is_converted_to_false(self) -> None:
        env = _composition_environment()

        # This helper is a boolean preflight API; it does not expose the
        # underlying TemplateSyntaxError diagnostic.
        assert validate_block_exists(env, "broken.html", "content") is False


class TestValidateTemplateBlock:
    def test_accepts_local_inherited_and_region_blocks(self) -> None:
        template = _composition_environment().get_template("child.html")

        assert validate_template_block(template, "content") is True
        assert validate_template_block(template, "shell") is True
        assert validate_template_block(template, "nav") is True

    def test_rejects_empty_and_unknown_blocks(self) -> None:
        template = _composition_environment().get_template("child.html")

        assert validate_template_block(template, "") is False
        assert validate_template_block(template, "missing") is False


class TestGetStructure:
    def test_returns_cached_inherited_structure_with_dependencies(self) -> None:
        env = _composition_environment()

        structure = get_structure(env, "child.html")

        assert structure is not None
        assert structure.name == "child.html"
        assert structure.extends == "base.html"
        assert structure.block_names == ("shell", "nav", "content")
        assert set(structure.block_hashes) == {"shell", "nav", "content"}
        assert all(structure.block_hashes.values())
        assert structure.dependencies == frozenset({"current", "page.title"})
        assert get_structure(env, "child.html") is structure

    def test_returns_none_for_missing_and_syntax_failure(self) -> None:
        env = _composition_environment()

        assert get_structure(env, "missing.html") is None
        assert get_structure(env, "broken.html") is None

    def test_returns_none_when_ast_is_not_preserved(self) -> None:
        env = _composition_environment(preserve_ast=False)

        assert get_structure(env, "child.html") is None


class TestBlockRoleForFramework:
    def test_classifies_content_name_or_role_as_fragment(self) -> None:
        assert block_role_for_framework(BlockMetadata(name="content")) == "fragment"
        assert (
            block_role_for_framework(BlockMetadata(name="article_body", inferred_role="content"))
            == "fragment"
        )

    def test_classifies_root_name_but_not_landmark_role_as_page_root(self) -> None:
        assert block_role_for_framework(BlockMetadata(name="page_root")) == "page_root"
        assert (
            block_role_for_framework(BlockMetadata(name="nav", inferred_role="navigation")) is None
        )
        assert (
            block_role_for_framework(BlockMetadata(name="header", inferred_role="header")) is None
        )

    def test_supports_custom_content_and_root_names(self) -> None:
        metadata = BlockMetadata(name="application_shell")

        assert (
            block_role_for_framework(
                metadata,
                content_roles=frozenset({"application_shell"}),
                root_roles=frozenset(),
            )
            == "fragment"
        )
        assert (
            block_role_for_framework(
                metadata,
                content_roles=frozenset(),
                root_roles=frozenset({"application_shell"}),
            )
            == "page_root"
        )

    def test_returns_none_for_none_unknown_and_missing_metadata_fields(self) -> None:
        assert block_role_for_framework(None) is None
        assert block_role_for_framework(BlockMetadata(name="custom")) is None
        assert block_role_for_framework(SimpleNamespace()) is None
