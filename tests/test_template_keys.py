"""Tests for template key normalization."""

import pytest

from kida.environment.exceptions import TemplateNotFoundError
from kida.utils.template_keys import normalize_template_name, resolve_template_name


def test_normalize_template_name_strips_whitespace() -> None:
    assert normalize_template_name("  page.html  ") == "page.html"
    assert normalize_template_name("\tlayouts/base.html\n") == "layouts/base.html"


def test_normalize_template_name_normalizes_path_separators() -> None:
    assert normalize_template_name("layouts\\base.html") == "layouts/base.html"
    assert normalize_template_name("a\\b\\c.html") == "a/b/c.html"


def test_normalize_template_name_idempotent() -> None:
    name = "layouts/base.html"
    assert normalize_template_name(normalize_template_name(name)) == name


def test_normalize_template_name_rejects_path_traversal() -> None:
    with pytest.raises(TemplateNotFoundError):
        normalize_template_name("../secret.html")
    with pytest.raises(TemplateNotFoundError):
        normalize_template_name("layouts/../../etc/passwd")
    with pytest.raises(TemplateNotFoundError):
        normalize_template_name("..")


def test_normalize_template_name_allows_valid_paths() -> None:
    assert normalize_template_name("page.html") == "page.html"
    assert normalize_template_name("layouts/base.html") == "layouts/base.html"
    assert normalize_template_name("partials/_header.html") == "partials/_header.html"


def test_resolve_template_name_absolute_matches_normalize() -> None:
    """Non-relative names resolve identically to normalize_template_name."""
    assert resolve_template_name("page.html") == "page.html"
    assert resolve_template_name("layouts/base.html", caller="anything") == "layouts/base.html"
    assert resolve_template_name("  page.html  ") == "page.html"


def test_resolve_template_name_dot_relative() -> None:
    """`./x` resolves against caller's directory."""
    assert resolve_template_name("./card.html", caller="pages/about.html") == "pages/card.html"
    assert resolve_template_name("./x.html", caller="a/b/c.html") == "a/b/x.html"
    # Caller at root
    assert resolve_template_name("./x.html", caller="index.html") == "x.html"


def test_resolve_template_name_dotdot_relative() -> None:
    """`../x` walks up one directory from caller."""
    assert (
        resolve_template_name("../shared/nav.html", caller="pages/blog/post.html")
        == "pages/shared/nav.html"
    )
    assert resolve_template_name("../x.html", caller="a/b.html") == "x.html"


def test_resolve_template_name_nested_relative() -> None:
    """Deep `../../x` resolves correctly."""
    assert resolve_template_name("../../shared.html", caller="a/b/c/d.html") == "a/shared.html"


def test_resolve_template_name_rejects_escape() -> None:
    """Resolution that walks above the template root is rejected."""
    with pytest.raises(TemplateNotFoundError) as exc_info:
        resolve_template_name("../../../etc/passwd", caller="pages/about.html")
    assert "escapes" in str(exc_info.value).lower()


def test_resolve_template_name_requires_caller() -> None:
    """Relative paths without a caller raise a clear error."""
    with pytest.raises(TemplateNotFoundError) as exc_info:
        resolve_template_name("./card.html")
    assert "caller" in str(exc_info.value).lower()

    with pytest.raises(TemplateNotFoundError):
        resolve_template_name("../x.html", caller=None)

    with pytest.raises(TemplateNotFoundError):
        resolve_template_name("./x.html", caller="")


def test_resolve_template_name_normalizes_interior_dotdot_resolved_inside_root() -> None:
    """Interior `..` inside a relative path resolves to a valid within-root name."""
    # pages/./foo/../card.html → pages/card.html
    assert (
        resolve_template_name("./foo/../card.html", caller="pages/about.html") == "pages/card.html"
    )


def test_resolve_template_name_rejects_bare_dot_at_root() -> None:
    """`./` from a root-level caller resolves to '.' and is rejected."""
    with pytest.raises(TemplateNotFoundError):
        resolve_template_name("./", caller="index.html")


def test_filesystem_loader_rejects_path_traversal() -> None:
    """FileSystemLoader rejects path traversal when used directly."""
    import tempfile
    from pathlib import Path

    from kida.environment.exceptions import TemplateNotFoundError
    from kida.environment.loaders import FileSystemLoader

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "page.html").write_text("ok")
        loader = FileSystemLoader(base)
        assert loader.get_source("page.html")[0] == "ok"

        with pytest.raises(TemplateNotFoundError) as exc_info:
            loader.get_source("../page.html")
        assert "path traversal" in str(exc_info.value).lower()


def test_package_loader_rejects_path_traversal() -> None:
    """PackageLoader rejects path traversal via normalize_template_name."""
    from kida.environment.loaders import PackageLoader

    loader = PackageLoader("kida")
    with pytest.raises(TemplateNotFoundError):
        loader.get_source("../../etc/passwd")
    with pytest.raises(TemplateNotFoundError):
        loader.get_source("layouts/../secret.html")
