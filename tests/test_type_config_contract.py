"""Contracts for the repository's static type-check configuration."""

import tomllib
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent


def test_core_modules_do_not_restore_unresolved_attribute_overrides() -> None:
    """Parser, compiler, and analysis mixins pass ty at default severity."""
    config = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    overrides = config["tool"]["ty"].get("overrides", [])

    unresolved_attribute_overrides = [
        override for override in overrides if "unresolved-attribute" in override.get("rules", {})
    ]

    assert unresolved_attribute_overrides == []
