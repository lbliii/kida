"""Regression checks for the published explicit-closer migration contract."""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT_DIR / "site" / "content" / "docs"


def _read(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def test_primary_migration_surfaces_keep_explicit_closers_as_a_noop() -> None:
    """Migration guidance must not require compatible closer-only rewrites."""
    readme = _read("README.md")
    claude = _read("CLAUDE.md")
    coming_from_jinja = _read("site/content/docs/get-started/coming-from-jinja2.md")
    migration_tutorial = _read("site/content/docs/tutorials/migrate-from-jinja2.md")

    assert "does not need closer-only edits" in readme
    for closer in ("endif", "endfor", "endblock"):
        assert f"`{{% {closer} %}}` | No change required" in claude
        assert f"{{% {closer} %}}" in coming_from_jinja
        assert f"{{% {closer} %}}" in migration_tutorial

    assert "is a migration no-op" in coming_from_jinja
    assert "## Step 4: Keep Matching Block Endings" in migration_tutorial
    assert "## Step 4: Rewrite Block Endings" not in migration_tutorial
    assert "Unexpected tag 'endif'" not in migration_tutorial


def test_reference_pages_describe_end_as_canonical_not_exclusive() -> None:
    """Reference summaries retain both canonical style and accepted syntax."""
    references = (
        DOCS_DIR / "get-started" / "quickstart.md",
        DOCS_DIR / "syntax" / "_index.md",
        DOCS_DIR / "syntax" / "control-flow.md",
        DOCS_DIR / "about" / "comparison.md",
        DOCS_DIR / "about" / "faq.md",
        DOCS_DIR / "errors.md",
    )

    for path in references:
        text = path.read_text(encoding="utf-8")
        assert "canonical" in text.lower(), path
        assert "explicit closers" in text.lower(), path
