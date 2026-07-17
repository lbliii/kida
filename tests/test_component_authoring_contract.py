"""Contract checks for canonical app-owned component guidance."""

from __future__ import annotations

import re
from pathlib import Path

from kida import DictLoader, Environment

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "site" / "content" / "docs" / "usage" / "components.md"
SOURCE_LINK = "site/content/docs/usage/components.md#app-owned-authoring-contract"
SITE_LINK = "/docs/usage/components/#app-owned-authoring-contract"
PUBLISHED_LINK = "https://lbliii.github.io/kida/docs/usage/components/#app-owned-authoring-contract"


def _contract_example(name: str) -> str:
    contract = CONTRACT.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"```kida\n(?P<source>[^`]*contract-example: {re.escape(name)}[^`]*?)\n```"
    )
    match = pattern.search(contract)
    assert match is not None, f"missing contract example: {name}"
    return match.group("source")


def test_component_authoring_contract_covers_required_boundaries() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    for heading in (
        "## App-Owned Authoring Contract",
        "### Extract a component when the interface matters",
        "### Keep one-off composition inline",
        "### Choose the narrowest composition seam",
        "### Component source and imports",
        "### CSS ownership",
        "### Responsibility boundaries",
    ):
        assert heading in contract

    for shipped_pattern in (
        "title: str",
        'variant: str = "default"',
        "{% slot header_actions %}",
        "{% slot row let:item=result %}",
        '{% from "components/result-list.html" import result_list %}',
        "{% provide theme",
        "consume(",
        "kida check templates/ --validate-calls",
        "kida components templates/ --json",
    ):
        assert shipped_pattern in contract


def test_public_docs_link_to_canonical_component_contract() -> None:
    for relative_path in (
        "site/content/docs/advanced/scoped-slots.md",
        "site/content/docs/usage/provide-consume.md",
    ):
        assert SITE_LINK in (ROOT / relative_path).read_text(encoding="utf-8")

    scoped_slots = (ROOT / "site" / "content" / "docs" / "advanced" / "scoped-slots.md").read_text(
        encoding="utf-8"
    )
    assert "{% call(let:" not in scoped_slots


def test_examples_link_to_canonical_component_contract() -> None:
    for relative_path in (
        "examples/README.md",
        "examples/components/README.md",
        "examples/design_system/README.md",
    ):
        assert PUBLISHED_LINK in (ROOT / relative_path).read_text(encoding="utf-8")


def test_repository_and_agent_guidance_link_to_canonical_component_contract() -> None:
    for relative_path in ("README.md", "CLAUDE.md"):
        assert SOURCE_LINK in (ROOT / relative_path).read_text(encoding="utf-8")


def test_documented_product_boundary_compiles_and_renders() -> None:
    source = _contract_example("destructive-action")
    template = Environment().from_string(
        source + '{{ delete_account_form("/accounts/ada", "Ada") }}',
        name="contract.html",
    )

    rendered = template.render()

    assert 'action="/accounts/ada"' in rendered
    assert 'aria-describedby="delete-account-help"' in rendered
    assert "Delete Ada permanently." in rendered


def test_documented_scoped_slot_and_explicit_import_render() -> None:
    loader = DictLoader(
        {
            "components/result-list.html": _contract_example("result-list-definition"),
            "page.html": _contract_example("result-list-call"),
        }
    )
    template = Environment(loader=loader, validate_calls=True).get_template("page.html")

    rendered = template.render(search_results=[{"title": "Kida", "url": "/projects/kida"}])

    assert '<a href="/projects/kida">Kida</a>' in rendered
