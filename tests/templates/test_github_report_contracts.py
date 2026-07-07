"""GitHub Action report contract tests."""

from __future__ import annotations

from .report_contracts import ROOT_DIR, TEMPLATES_DIR

GITHUB_TEMPLATES_DIR = ROOT_DIR / ".github" / "kida-templates"
WORKFLOWS_DIR = ROOT_DIR / ".github" / "workflows"


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
    workflow = (WORKFLOWS_DIR / "tests.yml").read_text(encoding="utf-8")

    assert "uv run pytest -n auto -q --tb=short --dist worksteal" in workflow
    assert "uv run pytest -n 0 -q --tb=short --cov=kida" in workflow
    assert "uv run ty check src/kida\n" in workflow
    assert "uv run ty check src/kida --output-format junit > reports/ty.xml || true" in workflow
    assert "uv run ruff check .\n" in workflow
    assert "--output-format json > reports/ruff.json || true" in workflow
    assert "uv run ruff format --check .\n" in workflow


def test_ci_has_one_authoritative_ty_lane():
    """Type checking runs once and keeps the report-producing CI job."""
    workflows = {
        path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS_DIR.glob("*.yml")
    }

    assert "ty.yml" not in workflows
    assert sum("uv run ty check src/kida\n" in workflow for workflow in workflows.values()) == 1
    assert "name: Type Check (ty)" in workflows["tests.yml"]
    assert "--output-format junit > reports/ty.xml || true" in workflows["tests.yml"]


def test_local_ruff_targets_use_the_same_repository_scope_as_ci():
    """Local lint, fix, format, and format-check targets cover the whole repo."""
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")

    for command in (
        "uv run ruff check .",
        "uv run ruff check . --fix",
        "uv run ruff format .",
        "uv run ruff format --check .",
    ):
        assert f"\t{command}\n" in makefile
