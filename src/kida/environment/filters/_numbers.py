"""Number and math filters for Kida templates."""

from __future__ import annotations

import math
import warnings
from typing import Any

from kida.exceptions import CoercionWarning, TemplateRuntimeError


def _filter_abs(value: Any) -> Any:
    """Return absolute value."""
    return abs(value)


def _filter_round(
    value: Any, precision: int = 0, method: str = "common", *, strict: bool = False
) -> float:
    """Round a number to a given precision."""
    try:
        fval = float(value)
    except (ValueError, TypeError) as e:
        if strict:
            raise TemplateRuntimeError(
                f"Cannot convert {type(value).__name__} to float: {value!r}",
                suggestion="Use | float or ensure correct type at data source",
            ) from e
        warnings.warn(
            f"Filter 'round' could not convert {type(value).__name__} {value!r} to float, returning 0.0. "
            f"Use | round(strict=true) to raise, or validate input data.",
            CoercionWarning,
            stacklevel=2,
        )
        return 0.0
    if method == "ceil":
        return float(math.ceil(fval * (10**precision)) / (10**precision))
    elif method == "floor":
        return float(math.floor(fval * (10**precision)) / (10**precision))
    else:
        return round(fval, precision)


def _filter_decimal(value: Any, places: int = 2, *, strict: bool = False) -> str:
    """Format a number with a fixed number of decimal places.

    Example:
        {{ 3.1 | decimal }}     → "3.10"
        {{ 3.1 | decimal(1) }}  → "3.1"
        {{ 1234 | decimal(2) }} → "1234.00"

    Args:
        value: Value to format.
        places: Number of decimal places.
        strict: If True, raise TemplateRuntimeError on conversion failure.

    """
    try:
        num = float(value)
        return f"{num:.{places}f}"
    except (ValueError, TypeError) as e:
        if strict:
            raise TemplateRuntimeError(
                f"Cannot convert {type(value).__name__} to decimal: {value!r}",
                suggestion="Use | int or | float for numeric coercion, or ensure correct type at data source",
            ) from e
        warnings.warn(
            f"Filter 'decimal' could not convert {type(value).__name__} {value!r}, returning as-is. "
            f"Use | decimal(strict=true) to raise, or validate input data.",
            CoercionWarning,
            stacklevel=2,
        )
        return str(value)


def _filter_filesizeformat(value: int | float, binary: bool = False) -> str:
    """Format a file size as human-readable."""
    try:
        bytes_val = float(value)
    except ValueError, TypeError:
        warnings.warn(
            f"Filter 'filesizeformat' could not convert {type(value).__name__} {value!r} to float, "
            f"returning '0 Bytes'. Validate input data.",
            CoercionWarning,
            stacklevel=2,
        )
        return "0 Bytes"
    base = 1024 if binary else 1000
    prefixes = [
        ("KiB" if binary else "kB", base),
        ("MiB" if binary else "MB", base**2),
        ("GiB" if binary else "GB", base**3),
        ("TiB" if binary else "TB", base**4),
    ]

    if bytes_val < base:
        return f"{int(bytes_val)} Bytes"

    for prefix, divisor in prefixes:
        if bytes_val < divisor * base:
            return f"{bytes_val / divisor:.1f} {prefix}"

    # Fallback to TB
    return f"{bytes_val / (base**4):.1f} {'TiB' if binary else 'TB'}"


def _filter_format_number(value: Any, decimal_places: int = 0, *, strict: bool = False) -> str:
    """Format a number with thousands separators.

    Example:
        {{ 1234567 | format_number }} → "1,234,567"
        {{ 1234.567 | format_number(2) }} → "1,234.57"

    Args:
        value: Value to format.
        decimal_places: Number of decimal places.
        strict: If True, raise TemplateRuntimeError on conversion failure.

    """
    try:
        num = float(value)
        if decimal_places > 0:
            return f"{num:,.{decimal_places}f}"
        else:
            return f"{int(num):,}"
    except (ValueError, TypeError) as e:
        if strict:
            raise TemplateRuntimeError(
                f"Cannot convert {type(value).__name__} to number: {value!r}",
                suggestion="Use | int or | float for numeric coercion, or ensure correct type at data source",
            ) from e
        warnings.warn(
            f"Filter 'format_number' could not convert {type(value).__name__} {value!r}, returning as-is. "
            f"Use | format_number(strict=true) to raise, or validate input data.",
            CoercionWarning,
            stacklevel=2,
        )
        return str(value)


def _filter_commas(value: Any) -> str:
    """Format a number with commas as thousands separators.

    Alias for format_number without decimal places.

    Example:
        {{ 1234567 | commas }} → "1,234,567"

    """
    return _filter_format_number(value, 0)


def _filter_min(value: Any, attribute: str | None = None) -> Any:
    """Return minimum value."""
    if attribute:
        items = list(value)
        none_count = sum(1 for x in items if getattr(x, attribute, None) is None)
        if none_count:
            warnings.warn(
                f"Filter 'min' found {none_count} item(s) with None for attribute '{attribute}', "
                f"treating as 0. Use | default(0) on the attribute or filter out None values first.",
                CoercionWarning,
                stacklevel=2,
            )
        return min(items, key=lambda x: getattr(x, attribute, None) or 0)
    return min(value)


def _filter_max(value: Any, attribute: str | None = None) -> Any:
    """Return maximum value."""
    if attribute:
        items = list(value)
        none_count = sum(1 for x in items if getattr(x, attribute, None) is None)
        if none_count:
            warnings.warn(
                f"Filter 'max' found {none_count} item(s) with None for attribute '{attribute}', "
                f"treating as 0. Use | default(0) on the attribute or filter out None values first.",
                CoercionWarning,
                stacklevel=2,
            )
        return max(items, key=lambda x: getattr(x, attribute, None) or 0)
    return max(value)


def _filter_sum(value: Any, attribute: str | None = None, start: int = 0) -> Any:
    """Return sum of values."""
    if attribute:
        return sum((getattr(x, attribute, 0) for x in value), start)
    return sum(value, start)
