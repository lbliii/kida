"""Tests for kida components CLI command (Sprint 2)."""

from __future__ import annotations

import json

import pytest

from kida.cli import main


@pytest.fixture
def component_dir(tmp_path):
    """Create a temp directory with component templates."""
    (tmp_path / "card.html").write_text(
        "{% def card(title: str, subtitle: str = None) %}"
        "<div>{% slot header %}{% slot %}</div>"
        "{% end %}"
        "{% def badge(label: str) %}"
        "<span>{{ label }}</span>"
        "{% end %}"
    )
    (tmp_path / "page.html").write_text("{% def nav(items: list) %}<nav>{{ items }}</nav>{% end %}")
    return tmp_path


@pytest.fixture
def empty_dir(tmp_path):
    """Create a temp directory with no templates."""
    return tmp_path


class TestComponentsCommand:
    """kida components subcommand."""

    def test_lists_all_defs(self, component_dir, capsys):
        """Lists all defs across templates."""
        rc = main(["components", str(component_dir)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "card" in out
        assert "badge" in out
        assert "nav" in out
        assert "3 component(s) found." in out

    def test_json_output(self, component_dir, capsys):
        """--json produces valid JSON with correct structure."""
        rc = main(["components", str(component_dir), "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 3
        names = {d["name"] for d in data}
        assert names == {"card", "badge", "nav"}

        # Check card structure
        card = next(d for d in data if d["name"] == "card")
        assert card["template"].endswith("card.html")
        assert len(card["params"]) == 2
        assert card["params"][0]["name"] == "title"
        assert card["params"][0]["annotation"] == "str"
        assert card["params"][0]["required"] is True
        assert card["params"][1]["required"] is False
        assert card["has_default_slot"] is True
        assert "header" in card["slots"]

    def test_json_output_contract_snapshot(self, component_dir, capsys):
        """--json output preserves the component inventory schema."""
        rc = main(["components", str(component_dir), "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data == [
            {
                "name": "badge",
                "template": "card.html",
                "lineno": 1,
                "params": [{"name": "label", "annotation": "str", "required": True}],
                "slots": [],
                "has_default_slot": False,
            },
            {
                "name": "card",
                "template": "card.html",
                "lineno": 1,
                "params": [
                    {"name": "title", "annotation": "str", "required": True},
                    {"name": "subtitle", "annotation": "str", "required": False},
                ],
                "slots": ["header"],
                "has_default_slot": True,
            },
            {
                "name": "nav",
                "template": "page.html",
                "lineno": 1,
                "params": [{"name": "items", "annotation": "list", "required": True}],
                "slots": [],
                "has_default_slot": False,
            },
        ]

    def test_filter_by_name(self, component_dir, capsys):
        """--filter narrows results by name substring."""
        rc = main(["components", str(component_dir), "--filter", "card"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "card" in out
        assert "badge" not in out
        assert "nav" not in out

    def test_filter_case_insensitive(self, component_dir, capsys):
        """--filter is case-insensitive."""
        rc = main(["components", str(component_dir), "--filter", "BADGE"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "badge" in out

    def test_no_components_found(self, empty_dir, capsys):
        """Returns 0 with message when no components found."""
        rc = main(["components", str(empty_dir)])
        assert rc == 0
        err = capsys.readouterr().err
        assert "No components found." in err

    def test_filter_no_match(self, component_dir, capsys):
        """Returns 0 with message when filter matches nothing."""
        rc = main(["components", str(component_dir), "--filter", "nonexistent"])
        assert rc == 0
        err = capsys.readouterr().err
        assert "No components matching" in err

    def test_invalid_directory(self, tmp_path, capsys):
        """Returns 2 for non-existent directory."""
        rc = main(["components", str(tmp_path / "nope")])
        assert rc == 2

    def test_shows_slots(self, component_dir, capsys):
        """Human-readable output shows slot information."""
        rc = main(["components", str(component_dir)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "slots:" in out
        assert "header" in out

    def test_shows_param_annotations(self, component_dir, capsys):
        """Human-readable output shows type annotations."""
        rc = main(["components", str(component_dir)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "title: str" in out

    def test_json_filter_combined(self, component_dir, capsys):
        """--json and --filter work together."""
        rc = main(["components", str(component_dir), "--json", "--filter", "badge"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["name"] == "badge"
