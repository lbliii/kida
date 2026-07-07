"""Release collateral must agree with the package version."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_release_collateral_is_aligned() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    version = pyproject["project"]["version"]

    release_page = ROOT / "site" / "content" / "releases" / f"{version}.md"
    assert release_page.is_file(), f"missing release page for {version}"

    release_text = release_page.read_text()
    assert f"title: Kida {version}" in release_text
    assert f"# v{version}" in release_text
    assert "draft: false" in release_text

    changelog = (ROOT / "CHANGELOG.md").read_text()
    unreleased_index = changelog.index("## [Unreleased]")
    release_index = changelog.index(f"## [{version}]")
    assert changelog.startswith("# Changelog\n")
    assert unreleased_index < release_index

    readme = (ROOT / "README.md").read_text()
    assert f"/releases/{version}/" in readme


def test_towncrier_inserts_after_unreleased_heading() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["tool"]["towncrier"]["start_string"] == "## [Unreleased]\n"
