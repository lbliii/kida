"""Drift checks for the top-level public API classification audit."""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT_PATH = ROOT / "src" / "kida" / "__init__.py"
CLASSIFICATION_PATH = ROOT / "docs" / "audit" / "public-api-classification.md"
CLASSIFICATION_ROW = re.compile(
    r"^\| `(?P<name>[^`]+)` \| (?P<category>[^|]+?) \|",
    re.MULTILINE,
)
EXPECTED_CATEGORIES = {
    "stable core",
    "stable advanced",
    "tooling/observability",
    "deprecated",
    "internal-before-1.0",
}
EXPECTED_CATEGORY_COUNTS = {
    "stable core": 20,
    "stable advanced": 28,
    "tooling/observability": 23,
    "internal-before-1.0": 3,
}


def _literal_public_exports() -> list[str]:
    tree = ast.parse(INIT_PATH.read_text(encoding="utf-8"), filename=str(INIT_PATH))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            exports = ast.literal_eval(node.value)
            assert isinstance(exports, list)
            assert all(isinstance(name, str) for name in exports)
            return exports
    raise AssertionError("literal kida.__all__ was not found")


def test_every_top_level_export_has_exactly_one_classification() -> None:
    rows = CLASSIFICATION_ROW.findall(CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    classified_names = [name for name, _category in rows]
    exports = _literal_public_exports()

    assert len(classified_names) == len(set(classified_names)), "duplicate classification row"
    assert set(classified_names) == set(exports)
    assert len(classified_names) == 74
    assert {category for _name, category in rows} <= EXPECTED_CATEGORIES
    assert Counter(category for _name, category in rows) == EXPECTED_CATEGORY_COUNTS
