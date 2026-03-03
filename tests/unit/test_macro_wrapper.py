"""Unit tests for MacroWrapper and _make_macro_wrapper."""

from __future__ import annotations

from kida.render_context import render_context
from kida.template.render_helpers import _make_macro_wrapper


def test_macro_wrapper_has_attributes() -> None:
    """MacroWrapper has _kida_source_template and _kida_source_file attributes."""

    def dummy() -> str:
        return "ok"

    wrapper = _make_macro_wrapper(dummy, "lib.html", "/path/to/lib.html", "source")
    assert wrapper._kida_source_template == "lib.html"
    assert wrapper._kida_source_file == "/path/to/lib.html"
    assert wrapper._source == "source"


def test_macro_wrapper_is_callable() -> None:
    """MacroWrapper is callable and returns the wrapped function's result."""

    def greet(name: str) -> str:
        return f"Hello {name}"

    wrapper = _make_macro_wrapper(greet, "macros.html", None, None)
    assert callable(wrapper)

    with render_context(template_name="caller.html"):
        result = wrapper("World")
    assert result == "Hello World"


def test_macro_wrapper_satisfies_import_macros_filter() -> None:
    """MacroWrapper passes callable(val) and not isinstance(val, type) checks."""

    def macro() -> str:
        return "x"

    wrapper = _make_macro_wrapper(macro, "t.html", None)
    assert callable(wrapper)
    assert not isinstance(wrapper, type)


def test_macro_wrapper_with_none_source_file() -> None:
    """MacroWrapper accepts None for source_file and source."""

    def fn() -> int:
        return 42

    wrapper = _make_macro_wrapper(fn, "t.html", None, None)
    assert wrapper._kida_source_file is None
    assert wrapper._source is None

    with render_context(template_name="caller.html"):
        assert wrapper() == 42
