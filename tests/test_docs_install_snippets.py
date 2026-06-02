"""Regression checks for published install snippets."""

from __future__ import annotations

import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT_DIR / "site" / "content" / "docs"

STALE_INSTALL_PATTERN = re.compile(r"pip install (?:[a-z0-9_-]+ )*kida(?:\[perf\])?(?:\s|$)")


def test_published_docs_use_distribution_package_name() -> None:
    """Current docs should install the published package, not the import package."""
    offenders: list[str] = []
    for doc_path in DOCS_DIR.rglob("*.md"):
        text = doc_path.read_text(encoding="utf-8")
        if STALE_INSTALL_PATTERN.search(text):
            offenders.append(str(doc_path.relative_to(ROOT_DIR)))

    assert offenders == []
