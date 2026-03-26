"""Snapshot tests for built-in CI report templates.

Each template is rendered against a fixture JSON file and compared to a
golden snapshot. Run with ``--update-snapshots`` to regenerate snapshots.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kida import FileSystemLoader
from kida.markdown import markdown_env

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"

TEMPLATE_NAMES = [
    "pytest",
    "coverage",
    "ruff",
    "ty",
    "jest",
    "gotest",
    "sarif",
]


@pytest.fixture(params=TEMPLATE_NAMES)
def template_name(request):
    return request.param


def test_template_snapshot(template_name, request):
    """Render a template and compare to golden snapshot."""
    fixture_path = FIXTURES_DIR / f"{template_name}.json"
    context = json.loads(fixture_path.read_text(encoding="utf-8"))

    env = markdown_env(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tpl = env.get_template(f"{template_name}-report.md")
    output = tpl.render(**context)

    snapshot_path = SNAPSHOTS_DIR / f"{template_name}-report.md"
    update = request.config.getoption("--update-snapshots")

    # Normalize: strip trailing whitespace, add single newline (end-of-file-fixer compat)
    normalized = output.rstrip() + "\n"

    if update or not snapshot_path.exists():
        snapshot_path.write_text(normalized, encoding="utf-8")
        if not update:
            pytest.fail(
                f"Snapshot created at {snapshot_path.relative_to(Path.cwd())} — review and re-run"
            )
        return

    expected = snapshot_path.read_text(encoding="utf-8")
    assert normalized == expected, (
        f"Snapshot mismatch for {template_name}-report.md.\n"
        f"Run with --update-snapshots to regenerate."
    )
