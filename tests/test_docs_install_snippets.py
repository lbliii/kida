"""Regression checks for published install snippets."""

from __future__ import annotations

import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT_DIR / "site" / "content" / "docs"

STALE_INSTALL_PATTERN = re.compile(r"pip install (?:[a-z0-9_-]+ )*kida(?:\[perf\])?(?:\s|$)")
FRAMEWORK_GUIDES = {
    "tutorials/flask-integration.md": "flask",
    "tutorials/django-integration.md": "django",
    "tutorials/starlette-integration.md": "fastapi",
}


def test_published_docs_use_distribution_package_name() -> None:
    """Current docs should install the published package, not the import package."""
    offenders: list[str] = []
    for doc_path in DOCS_DIR.rglob("*.md"):
        text = doc_path.read_text(encoding="utf-8")
        if STALE_INSTALL_PATTERN.search(text):
            offenders.append(str(doc_path.relative_to(ROOT_DIR)))

    assert offenders == []


def test_framework_guides_keep_horizontal_quickstart_contract() -> None:
    """Framework entry points retain the 3.14, migration, and fragment path."""
    for relative_path, package in FRAMEWORK_GUIDES.items():
        text = (DOCS_DIR / relative_path).read_text(encoding="utf-8")

        assert "Python 3.14" in text[:800]
        assert f"uv add {package}" in text
        assert "coming-from-jinja2" in text[:1_200]
        assert "block-scoped" in text[:1_200]
        assert "{% def " in text
        assert '<form method="post"' in text
        assert "render_block(" in text
