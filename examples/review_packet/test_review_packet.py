"""Tests for the review packet example."""

import importlib.util
from pathlib import Path


def _load_analysis_packet():
    path = Path(__file__).parent / "analysis_packet.py"
    spec = importlib.util.spec_from_file_location("review_packet_analysis_packet", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_markdown_review_packet_leads_with_pr_context(example_app) -> None:
    assert "# Kida Review Packet: #127" in example_app.output
    assert "codex/adoption-roadmap-cleanup" in example_app.output
    assert "| `pytest` | pass | 98 passed, 5 warnings |" in example_app.output


def test_markdown_review_packet_includes_static_diagnostics(example_app) -> None:
    assert "`K-CMP-001`" in example_app.output
    assert "`K-CMP-002`" in example_app.output
    assert "`K-PAR-003`" in example_app.output
    assert "Next action: Pass value=..." in example_app.output


def test_terminal_review_packet_uses_same_data(example_app) -> None:
    terminal = example_app.render("terminal")
    assert "KIDA REVIEW PACKET #127" in terminal
    assert "[warn] pre-commit - Local hook blocked by parent uv nested workspace" in terminal
    assert "K-CMP-001 pages/dashboard.html:8" in terminal
    assert "# Kida Review Packet" not in terminal


def test_large_app_analysis_packet_combines_static_facts() -> None:
    packet = _load_analysis_packet().build_large_app_packet()

    assert packet["template"] == "page.html"
    assert packet["required_context"] == ["body_html", "card", "page", "user"]
    assert [item["name"] for item in packet["components"]] == ["card"]
    assert [(item["name"], item["value"]) for item in packet["literal_attributes"]] == [
        ("id", "thread"),
        ("data-page", "thread"),
        ("hx-post", "/reply"),
    ]
    assert [(item["code"], item["kind"]) for item in packet["escape_findings"]] == [
        ("K-ESC-002", "safe-filter")
    ]
    assert ("K-PRI-001", "user.email") in [
        (item["code"], item["path"]) for item in packet["privacy_findings"]
    ]
