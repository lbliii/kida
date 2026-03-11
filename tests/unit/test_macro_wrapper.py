"""Unit tests for MacroWrapper and _make_macro_wrapper."""

from __future__ import annotations

import pytest

from kida.render_context import render_context
from kida.template.render_helpers import MacroWrapper, _make_macro_wrapper


def test_macro_wrapper_has_attributes() -> None:
    """MacroWrapper has _kida_source_template and _kida_source_file attributes."""

    def dummy() -> str:
        return "ok"

    wrapper = _make_macro_wrapper(
        dummy, "lib.html", "/path/to/lib.html", "source", macro_name="dummy"
    )
    assert wrapper._kida_source_template == "lib.html"
    assert wrapper._kida_source_file == "/path/to/lib.html"
    assert wrapper._source == "source"
    assert wrapper._kida_macro_name == "dummy"


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
    assert wrapper._kida_macro_name is None

    with render_context(template_name="caller.html"):
        assert wrapper() == 42


def test_macro_wrapper_iteration_raises_helpful_error() -> None:
    """Iterating over a MacroWrapper raises TypeError with name-collision hint."""

    def route_tabs(tabs: list, current_path: str) -> str:
        return "".join(str(t) for t in tabs)

    wrapper = _make_macro_wrapper(
        route_tabs, "_route_tabs.html", None, None, macro_name="route_tabs"
    )

    with pytest.raises(TypeError) as exc_info:
        for _ in wrapper:
            pass

    msg = str(exc_info.value)
    assert "Cannot iterate over macro 'route_tabs'" in msg
    assert "shadowing" in msg
    assert "render_route_tabs" in msg


def test_macro_wrapper_iteration_without_macro_name() -> None:
    """Iteration error falls back to 'macro' when macro_name is None."""

    wrapper = MacroWrapper(
        _fn=lambda: None,
        _kida_source_template="t.html",
        _kida_source_file=None,
        _source=None,
        _kida_macro_name=None,
    )

    with pytest.raises(TypeError) as exc_info:
        for _ in wrapper:
            pass

    assert "Cannot iterate over macro 'macro'" in str(exc_info.value)
