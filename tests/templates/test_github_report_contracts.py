"""GitHub Action report contract tests."""

from __future__ import annotations

from .report_contracts import ROOT_DIR, TEMPLATES_DIR

GITHUB_TEMPLATES_DIR = ROOT_DIR / ".github" / "kida-templates"
WORKFLOWS_DIR = ROOT_DIR / ".github" / "workflows"


def _action_steps(source: str) -> list[str]:
    """Return top-level step blocks from an Action or workflow source."""
    lines = source.splitlines()
    steps: list[str] = []

    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("- "):
            continue

        indent = len(line) - len(stripped)
        block = [line]
        for candidate in lines[index + 1 :]:
            candidate_stripped = candidate.lstrip()
            candidate_indent = len(candidate) - len(candidate_stripped)
            if candidate_indent == indent and candidate_stripped.startswith("- "):
                break
            if candidate and candidate_indent < indent:
                break
            block.append(candidate)
        steps.append("\n".join(block))

    return steps


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


def test_ci_repeats_seeded_thread_stress_on_scheduled_runs():
    """Required CI uses one seed while weekly/manual runs expand the same proof."""
    workflow = (WORKFLOWS_DIR / "tests.yml").read_text(encoding="utf-8")

    assert "name: Run seeded randomized thread stress" in workflow
    assert 'KIDA_STRESS_SEED: "0"' in workflow
    assert (
        "KIDA_STRESS_RUNS: ${{ (github.event_name == 'schedule' || "
        "github.event_name == 'workflow_dispatch') && '25' || '1' }}" in workflow
    )
    assert (
        "uv run pytest tests/test_randomized_thread_stress.py -vv -s "
        "--tb=short --timeout=120" in workflow
    )


def test_setup_uv_steps_only_use_supported_inputs():
    """setup-uv steps do not pass setup-python-only inputs."""
    sources = [
        (ROOT_DIR / "action.yml").read_text(encoding="utf-8"),
        *(path.read_text(encoding="utf-8") for path in WORKFLOWS_DIR.glob("*.yml")),
    ]
    setup_uv_steps = [
        step
        for source in sources
        for step in _action_steps(source)
        if "uses: astral-sh/setup-uv@" in step
    ]

    assert setup_uv_steps, "expected at least one setup-uv workflow step"
    assert all("allow-prereleases:" not in step for step in setup_uv_steps)


def test_release_workflow_keeps_exact_free_threaded_python_setup():
    """Release jobs keep selecting the exact Python 3.14t interpreter."""
    workflow = (WORKFLOWS_DIR / "python-publish.yml").read_text(encoding="utf-8")
    steps = _action_steps(workflow)
    release_python_steps = [
        step
        for step in steps
        if 'python-version: "3.14t"' in step
        and ("uses: astral-sh/setup-uv@" in step or "uses: actions/setup-python@" in step)
    ]

    assert len(release_python_steps) == 2
    setup_python_step = next(
        step for step in release_python_steps if "uses: actions/setup-python@" in step
    )
    assert "allow-prereleases: true" in setup_python_step


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
