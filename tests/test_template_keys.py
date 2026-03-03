"""Tests for template key normalization."""

import pytest

from kida.environment.exceptions import TemplateNotFoundError
from kida.utils.template_keys import normalize_template_name


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


def test_invalid_block_name_raises() -> None:
    """Invalid block names raise TemplateSyntaxError at compile time."""
    from kida import DictLoader, Environment
    from kida.compiler import Compiler
    from kida.environment.exceptions import TemplateSyntaxError
    from kida.nodes import Block, Data
    from kida.nodes.structure import Template

    # Parser only accepts identifier-like names, so we test the compiler directly
    # with a Block node that has an invalid name (e.g. from programmatic construction)
    bad_block = Block(
        lineno=1,
        col_offset=0,
        name="invalid-name",
        body=(Data(lineno=2, col_offset=0, value="x"),),
    )
    root = Template(
        lineno=1,
        col_offset=0,
        body=(bad_block,),
        extends=None,
        context_type=None,
    )
    env = Environment(loader=DictLoader({}))
    compiler = Compiler(env)
    with pytest.raises(TemplateSyntaxError) as exc_info:
        compiler.compile(root, name="test.html")
    assert "Invalid block name" in str(exc_info.value)
    assert "invalid-name" in str(exc_info.value)


def test_invalid_def_name_raises() -> None:
    """Invalid def names raise TemplateSyntaxError at compile time."""
    from kida import DictLoader, Environment
    from kida.compiler import Compiler
    from kida.environment.exceptions import TemplateSyntaxError
    from kida.nodes import Data, Def, DefParam
    from kida.nodes.structure import Template

    bad_def = Def(
        lineno=1,
        col_offset=0,
        name="invalid-def",
        params=(),
        body=(Data(lineno=2, col_offset=0, value="x"),),
    )
    root = Template(
        lineno=1,
        col_offset=0,
        body=(bad_def,),
        extends=None,
        context_type=None,
    )
    env = Environment(loader=DictLoader({}))
    compiler = Compiler(env)
    with pytest.raises(TemplateSyntaxError) as exc_info:
        compiler.compile(root, name="test.html")
    assert "Invalid def name" in str(exc_info.value)
    assert "invalid-def" in str(exc_info.value)


def test_invalid_slot_name_raises() -> None:
    """Invalid slot names raise TemplateSyntaxError at compile time."""
    from kida import DictLoader, Environment
    from kida.compiler import Compiler
    from kida.environment.exceptions import TemplateSyntaxError
    from kida.nodes import Data, SlotBlock
    from kida.nodes.structure import Template

    bad_slot = SlotBlock(
        lineno=1,
        col_offset=0,
        name="bad-slot",
        body=(Data(lineno=2, col_offset=0, value="x"),),
    )
    root = Template(
        lineno=1,
        col_offset=0,
        body=(bad_slot,),
        extends=None,
        context_type=None,
    )
    env = Environment(loader=DictLoader({}))
    compiler = Compiler(env)
    with pytest.raises(TemplateSyntaxError) as exc_info:
        compiler.compile(root, name="test.html")
    assert "Invalid slot name" in str(exc_info.value)
    assert "bad-slot" in str(exc_info.value)
