"""Tests for Kida lightweight structure manifest API."""

from kida import Environment
from kida.environment.loaders import DictLoader


def test_get_template_structure_includes_block_hashes() -> None:
    env = Environment(
        loader=DictLoader(
            {
                "page.html": """
{% extends "base.html" %}
{% block nav %}<nav>{{ site.title }}</nav>{% end %}
{% block content %}{{ page.title }}{% end %}
""".strip(),
                "base.html": "{% block nav %}{% end %}{% block content %}{% end %}",
            }
        )
    )

    manifest = env.get_template_structure("page.html")
    assert manifest is not None
    assert manifest.name == "page.html"
    assert manifest.extends == "base.html"
    assert set(manifest.block_names) == {"nav", "content"}
    assert set(manifest.block_hashes) == {"nav", "content"}
    assert all(len(value) == 16 for value in manifest.block_hashes.values())
    assert "site.title" in manifest.dependencies
    assert "page.title" in manifest.dependencies


def test_get_template_structure_uses_cache() -> None:
    env = Environment(loader=DictLoader({"cached.html": "{% block nav %}A{% end %}"}))

    first = env.get_template_structure("cached.html")
    second = env.get_template_structure("cached.html")
    assert first is not None
    assert second is not None
    assert first is second
