"""Tests for literal HTML attribute extraction."""

from __future__ import annotations

from kida import Environment
from kida.analysis.attributes import extract_literal_attributes


def test_extracts_literal_attributes_with_locations() -> None:
    env = Environment()
    template = env.from_string(
        '<main id="thread" data-page="1">\n'
        "  <button hx-post='/reply' disabled>Reply</button>\n"
        "</main>",
        name="thread.html",
    )

    attrs = extract_literal_attributes(template, names={"id", "data-page", "hx-post", "disabled"})

    assert [(attr.tag, attr.name, attr.value) for attr in attrs] == [
        ("main", "id", "thread"),
        ("main", "data-page", "1"),
        ("button", "hx-post", "/reply"),
        ("button", "disabled", None),
    ]
    assert {attr.template_name for attr in attrs} == {"thread.html"}
    assert attrs[0].lineno == 1
    assert attrs[2].lineno == 2


def test_extracts_by_prefix_without_framework_semantics() -> None:
    env = Environment()
    template = env.from_string(
        '<div data-target="posts" hx-swap="outerHTML" aria-live="polite"></div>',
        name="partial.html",
    )

    attrs = extract_literal_attributes(template, prefixes=("data-", "hx-"))

    assert [(attr.name, attr.value) for attr in attrs] == [
        ("data-target", "posts"),
        ("hx-swap", "outerHTML"),
    ]


def test_dynamic_attributes_are_not_inferred() -> None:
    env = Environment()
    template = env.from_string('<div {{ attrs }} id="{{ dynamic_id }}"></div>', name="dynamic.html")

    attrs = extract_literal_attributes(template)

    assert attrs == []


def test_no_ast_returns_empty_attributes() -> None:
    env = Environment()
    template = env.from_string('<div id="x"></div>')
    template._optimized_ast = None

    assert extract_literal_attributes(template) == []
