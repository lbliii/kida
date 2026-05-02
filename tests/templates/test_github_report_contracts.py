"""GitHub Action report contract tests."""

from __future__ import annotations

from .report_contracts import ROOT_DIR, TEMPLATES_DIR

GITHUB_TEMPLATES_DIR = ROOT_DIR / ".github" / "kida-templates"


def test_github_report_template_copies_match_source_templates():
    """Checked-in GitHub report copies do not silently drift from source templates."""
    for github_template in GITHUB_TEMPLATES_DIR.glob("*-report.md"):
        source_template = TEMPLATES_DIR / github_template.name
        assert source_template.is_file(), f"missing source template for {github_template.name}"
        assert github_template.read_text(encoding="utf-8") == source_template.read_text(
            encoding="utf-8"
        ), f"{github_template.name} diverges from templates/{github_template.name}"


def test_ci_workflow_keeps_raw_output_alongside_rendered_reports():
    """Dogfooded reports are additive and do not replace raw lint/type/test output."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert "uv run pytest -n auto -q --tb=short --dist worksteal" in workflow
    assert "uv run pytest -n 0 -q --tb=short --cov=kida" in workflow
    assert "uv run ty check src/kida\n" in workflow
    assert "uv run ty check src/kida --output-format junit > reports/ty.xml || true" in workflow
    assert "uv run ruff check src/kida tests/ benchmarks/ scripts/\n" in workflow
    assert "--output-format json > reports/ruff.json || true" in workflow
