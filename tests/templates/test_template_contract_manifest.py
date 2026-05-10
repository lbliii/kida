"""Contract manifest tests for built-in report templates."""

from __future__ import annotations

import json

from .report_contracts import REPORT_CONTRACTS, ROOT_DIR


def _expected_manifest_templates() -> list[dict[str, object]]:
    return [
        {
            "name": contract.name,
            "template": f"templates/{contract.name}-report.md",
            "fixture": f"tests/templates/fixtures/{contract.fixture_name}.json",
            "snapshot": f"tests/templates/snapshots/{contract.name}-report.md",
            "data_format": contract.data_format,
            "render_mode": contract.render_mode,
            "surfaces": list(contract.surfaces),
            "amp_schema": contract.amp_schema,
        }
        for contract in REPORT_CONTRACTS
    ]


def test_report_template_contract_manifest_matches_inventory() -> None:
    """The checked contract artifact mirrors the executable test inventory."""
    manifest = json.loads(
        (ROOT_DIR / "docs" / "report-template-contracts.json").read_text(encoding="utf-8")
    )

    assert manifest["version"] == 1
    assert manifest["templates"] == _expected_manifest_templates()


def test_report_template_contract_names_match_action_docs_and_amp_protocol() -> None:
    """Action/docs/protocol surfaces do not silently drift from the inventory."""
    action = (ROOT_DIR / "action.yml").read_text(encoding="utf-8")
    github_action_doc = (ROOT_DIR / "site/content/docs/usage/github-action.md").read_text(
        encoding="utf-8"
    )
    amp_doc = (ROOT_DIR / "site/content/docs/usage/amp.md").read_text(encoding="utf-8")
    protocol = json.loads(
        (ROOT_DIR / "schemas/amp/v1/protocol.json").read_text(encoding="utf-8")
    )
    message_types = protocol["default"]["message_types"]

    for contract in REPORT_CONTRACTS:
        assert contract.name in action
        assert f"`{contract.name}`" in github_action_doc

        if contract.amp_schema is None:
            continue

        assert contract.amp_schema in amp_doc
        registered_templates = set(message_types[contract.amp_schema]["templates"].values())
        if contract.name in registered_templates:
            continue

        # Detailed/alternate release-note templates share the release-notes schema
        # without being default AMP protocol renderers for a specific surface.
        assert contract.amp_schema == "release-notes"
        assert contract.name.startswith("release-notes-")
