"""Tests for the refactor-safety example."""

from __future__ import annotations

from pathlib import Path

from kida.cli import main


def test_good_dashboard_renders_components(example_app) -> None:
    assert "<h1>Ops Dashboard</h1>" in example_app.output
    assert "card-warning" in example_app.output
    assert "Closed issues" in example_app.output
    assert "<td>Ari</td><td>SRE</td>" in example_app.output


def test_missing_context_is_detected_before_render(example_app) -> None:
    assert "owner" in example_app.missing_context
    assert "stats" in example_app.missing_context
    assert "users" in example_app.missing_context


def test_broken_templates_report_static_diagnostics(
    capsys,
) -> None:
    root = Path(__file__).parent / "templates" / "broken"

    exit_code = main(["check", str(root), "--validate-calls", "--lint-fragile-paths"])
    assert exit_code == 1

    err = capsys.readouterr().err
    assert "K-PAR-003" in err
    assert "Duplicate keyword argument: title" in err
    assert "K-CMP-001" in err
    assert "missing required: value" in err
    assert "unknown params: variant" in err
    assert "K-CMP-002" in err
    assert "expects int, got str ('five')" in err
    assert "lint/fragile-path" in err
    assert "./summary.html" in err
