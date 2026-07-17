"""Contracts for the report-only downstream canary workflow."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "downstream-canaries.yml"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_downstream_override.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_downstream_override", VERIFY_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_override_accepts_checkout_and_rejects_released_package(tmp_path: Path) -> None:
    verifier = _load_verifier()
    checkout = tmp_path / "kida"
    local_import = checkout / "src" / "kida" / "__init__.py"
    released_import = tmp_path / "site-packages" / "kida" / "__init__.py"

    assert verifier.verify_source(local_import, checkout) == local_import
    with pytest.raises(RuntimeError, match="imported the wrong Kida"):
        verifier.verify_source(released_import, checkout)


def test_workflow_is_report_only_least_privilege_and_fork_safe() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert "continue-on-error: true" in workflow
    assert "fail-fast: false" in workflow
    assert "secrets." not in workflow
    assert "persist-credentials: false" in workflow
    assert "pull_request:" in workflow
    assert "push:\n    branches: [main]" in workflow
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow


def test_workflow_proves_source_override_and_runs_pinned_surface_canaries() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "repository: lbliii/chirp-ui" in workflow
    assert "repository: lbliii/milo-cli" in workflow
    assert "repository: lbliii/chirp" in workflow
    assert "ref: d06ea60536ee8b909ae8a23815799d018809742d" in workflow
    assert "ref: 085526215cdec5a9a9dfc2c59ed589b97ec645ff" in workflow
    assert "ref: 3e56ce273cf6ec3cb73c6ce8decef2f78e6dc1f5" in workflow
    assert "ref: ${{ matrix.ref }}" in workflow
    assert "--no-deps --editable ./kida" in workflow
    assert "verify_downstream_override.py" in workflow
    assert 'python-version: "3.14t"' in workflow
    assert "run: uv run --no-sync pytest tests/ -x -q\n" in workflow
    assert "run: uv run --no-sync pytest -q\n" in workflow
    assert "--no-deps --editable ." in workflow
    assert "CHIRP_KIDA_MULTI_ROOT_PILOT" in workflow
    assert (
        "run: uv run --no-sync pytest tests/templating/test_kida_multi_root_pilot.py -q\n"
        in workflow
    )
    assert "--timeout=" not in workflow
    assert 'PYTHON_GIL: "0"' in workflow
    assert "Record canary provenance" in workflow
