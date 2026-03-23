"""Tests for ``kida`` CLI."""

import subprocess
import sys
from pathlib import Path


def test_check_passes_on_examples_templates() -> None:
    from kida.cli import main

    root = Path(__file__).resolve().parents[1] / "examples" / "htmx_partials" / "templates"
    assert root.is_dir()
    assert main(["check", str(root)]) == 0


def test_check_reports_bad_template(tmp_path: Path) -> None:
    from kida.cli import main

    (tmp_path / "bad.html").write_text("{% if x %}", encoding="utf-8")
    assert main(["check", str(tmp_path)]) != 0


def test_module_invocation() -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "htmx_partials" / "templates"
    proc = subprocess.run(
        [sys.executable, "-m", "kida", "check", str(root)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
