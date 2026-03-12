"""Type conversion filters for Kida templates."""

from __future__ import annotations

import json
from pathlib import PurePath
from typing import Any

from kida.environment.exceptions import TemplateRuntimeError
from kida.utils.html import Markup


def _filter_string(value: Any) -> str:
    """Convert to string."""
    return str(value)


def _filter_int(value: Any, default: int = 0, strict: bool = False) -> int:
    """Convert to integer.

    Use for values from YAML/config that may arrive as strings (e.g. excerpt_words,
    per_page). Apply before arithmetic (//, /, %) to avoid TypeError.

    Args:
        value: Value to convert to integer.
        default: Default value to return if conversion fails (default: 0).
        strict: If True, raise TemplateRuntimeError on conversion failure
            instead of returning default (default: False).

    Returns:
        Integer value, or default if conversion fails and strict=False.

    Raises:
        TemplateRuntimeError: If strict=True and conversion fails.

    Examples:
            >>> _filter_int("42")
        42
            >>> _filter_int("not a number")
        0
            >>> _filter_int("not a number", strict=True)
        TemplateRuntimeError: Cannot convert str to int: 'not a number'

    """
    try:
        return int(value)
    except (ValueError, TypeError) as e:
        if strict:
            raise TemplateRuntimeError(
                f"Cannot convert {type(value).__name__} to int: {value!r}",
                suggestion="Use | default(0) | int for optional conversion, or ensure value is numeric",
            ) from e
        return default


def _filter_float(value: Any, default: float = 0.0, strict: bool = False) -> float:
    """Convert value to float.

    Args:
        value: Value to convert to float.
        default: Default value to return if conversion fails (default: 0.0).
        strict: If True, raise TemplateRuntimeError on conversion failure
            instead of returning default (default: False).

    Returns:
        Float value, or default if conversion fails and strict=False.

    Raises:
        TemplateRuntimeError: If strict=True and conversion fails.

    Examples:
            >>> _filter_float("3.14")
        3.14
            >>> _filter_float("not a number")
        0.0
            >>> _filter_float("not a number", strict=True)
        TemplateRuntimeError: Cannot convert str to float: 'not a number'

    """
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        if strict:
            raise TemplateRuntimeError(
                f"Cannot convert {type(value).__name__} to float: {value!r}",
                suggestion="Use | default(0.0) | float for optional conversion, or ensure value is numeric",
            ) from e
        return default


def _filter_list(value: Any) -> list[Any]:
    """Convert to list."""
    return list(value)


def _filter_typeof(value: Any) -> str:
    """Return generic type name for a value (bool, int, float, path, list, dict, none, str)."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, PurePath):
        return "path"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if value is None:
        return "none"
    return "str"


def _filter_tojson(value: Any, indent: int | None = None) -> Markup:
    """Convert value to JSON string (marked safe to prevent escaping)."""
    return Markup(json.dumps(value, indent=indent, default=str))
