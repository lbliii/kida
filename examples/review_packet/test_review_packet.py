"""Tests for the review packet example."""


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
