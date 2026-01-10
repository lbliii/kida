"""Kida Template String support (PEP 750).

Provides the `k` tag for Python 3.14+ t-strings, allowing Kida-style
interpolation and filters within Python code.
"""

from __future__ import annotations

from typing import Any

try:  # Python <3.14 fallback: allow tests and callers to pass compatible objects
    import string.templatelib as templatelib
except ImportError:  # pragma: no cover - exercised via fallback path
    templatelib = None

from kida.utils.html import html_escape


def k(template: Any) -> str:
    """The `k` tag for Kida template strings.

    Example:
        >>> name = "World"
        >>> k(t"Hello {name}!")
        'Hello World!'

    Note: Currently supports simple interpolation. Future versions will
    integrate with the Kida compiler for filter support.
    """
    if templatelib is not None and not isinstance(template, templatelib.Template):
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
