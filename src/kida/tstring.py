"""Kida Template String support (PEP 750).

Provides the `k` tag for Python 3.14+ t-strings, allowing Kida-style
interpolation and filters within Python code.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any, Protocol, cast, runtime_checkable

from kida.utils.html import html_escape


@runtime_checkable
class TemplateProtocol(Protocol):
    strings: tuple[str, ...]
    interpolations: tuple[Any, ...]


class TemplateLibProtocol(Protocol):
    Template: type[TemplateProtocol]


templatelib_module: ModuleType | None
try:  # Python <3.14 fallback: allow tests and callers to pass compatible objects
    templatelib_module = import_module("string.templatelib")
except ImportError:  # pragma: no cover - exercised via fallback path
    templatelib_module = None

templatelib: TemplateLibProtocol | None = cast(TemplateLibProtocol | None, templatelib_module)


def k(template: TemplateProtocol) -> str:
    """The `k` tag for Kida template strings.

    Example:
        >>> name = "World"
        >>> k(t"Hello {name}!")
        'Hello World!'

    Note: Currently supports simple interpolation. Future versions will
    integrate with the Kida compiler for filter support.
    """
    # Accept any object that structurally matches the template protocol, even
    # when the stdlib templatelib module is available (tests pass SimpleNamespace).
    if not isinstance(template, TemplateProtocol):
        raise TypeError("k() expects a string.templatelib.Template or compatible object")

    strings = template.strings
    interpolations = template.interpolations
    parts: list[str] = []

    for i in range(len(strings)):
        parts.append(strings[i])
        if i < len(interpolations):
            val = interpolations[i].value
            # Auto-escape if it's not already Markup (Kida principle)
            if hasattr(val, "__html__"):
                parts.append(val.__html__())
            else:
                parts.append(html_escape(str(val)))

    return "".join(parts)
