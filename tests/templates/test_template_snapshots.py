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
from kida.terminal import terminal_env

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
    "code-review",
    "pr-summary",
    "deploy-preview",
    "dependency-review",
    "security-scan",
    "copilot-instructions",
]

# Templates that share a fixture with a different name
FIXTURE_ALIASES = {
    "release-notes": "release-notes",
    "release-notes-compact": "release-notes",
    "release-notes-detailed": "release-notes",
    "release-notes-terminal": "release-notes",
}

TEMPLATE_NAMES += list(FIXTURE_ALIASES.keys())


@pytest.fixture(params=TEMPLATE_NAMES)
def template_name(request):
    return request.param


def test_template_snapshot(template_name, request):
    """Render a template and compare to golden snapshot."""
    fixture_key = FIXTURE_ALIASES.get(template_name, template_name)
    fixture_path = FIXTURES_DIR / f"{fixture_key}.json"
    context = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Terminal templates need terminal_env for ANSI filters (bold, cyan, etc.)
    terminal_templates = {"release-notes-terminal"}
    if template_name in terminal_templates:
        env = terminal_env(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    else:
        env = markdown_env(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tpl = env.get_template(f"{template_name}-report.md")
    output = tpl.render(**context)

    snapshot_path = SNAPSHOTS_DIR / f"{template_name}-report.md"
    update = request.config.getoption("--update-snapshots")

    # Normalize: strip trailing whitespace per line (matches pre-commit hook behavior)
    # and add single newline at end (end-of-file-fixer compat)
    normalized = "\n".join(line.rstrip() for line in output.splitlines()).rstrip() + "\n"

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
