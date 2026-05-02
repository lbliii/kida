"""Snapshot tests for built-in CI report templates.

Each template is rendered against a fixture JSON file and compared to a
golden snapshot. Run with ``--update-snapshots`` to regenerate snapshots.
"""

from __future__ import annotations

import json

import pytest

from kida import FileSystemLoader
from kida.markdown import markdown_env
from kida.terminal import terminal_env

from .report_contracts import REPORT_CONTRACTS, TEMPLATES_DIR


@pytest.fixture(params=REPORT_CONTRACTS, ids=lambda contract: contract.name)
def report_contract(request):
    return request.param


def test_report_contract_inventory():
    """Every built-in report template has explicit fixture and snapshot coverage."""
    contracted_templates = {contract.template_path.name for contract in REPORT_CONTRACTS}
    actual_templates = {path.name for path in TEMPLATES_DIR.glob("*-report.md")}
    assert contracted_templates == actual_templates

    for contract in REPORT_CONTRACTS:
        assert contract.template_path.is_file(), f"missing template: {contract.template_path}"
        assert contract.fixture_path.is_file(), f"missing fixture: {contract.fixture_path}"
        assert contract.snapshot_path.is_file(), f"missing snapshot: {contract.snapshot_path}"


def test_template_snapshot(report_contract, request):
    """Render a template and compare to golden snapshot."""
    context = json.loads(report_contract.fixture_path.read_text(encoding="utf-8"))

    # Terminal templates need terminal_env for ANSI filters (bold, cyan, etc.)
    if report_contract.render_mode == "terminal":
        env = terminal_env(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    else:
        env = markdown_env(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tpl = env.get_template(report_contract.template_path.name)
    output = tpl.render(**context)

    update = request.config.getoption("--update-snapshots")

    # Normalize: strip trailing whitespace per line (matches pre-commit hook behavior)
    # and add single newline at end (end-of-file-fixer compat)
    normalized = "\n".join(line.rstrip() for line in output.splitlines()).rstrip() + "\n"

    if update or not report_contract.snapshot_path.exists():
        report_contract.snapshot_path.write_text(normalized, encoding="utf-8")
        if not update:
            pytest.fail(f"Snapshot created at {report_contract.snapshot_path} — review and re-run")
        return

    expected = report_contract.snapshot_path.read_text(encoding="utf-8")
    assert normalized == expected, (
        f"Snapshot mismatch for {report_contract.template_path.name}.\n"
        f"Run with --update-snapshots to regenerate."
    )
