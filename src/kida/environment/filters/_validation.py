"""Validation filters for Kida templates."""

from __future__ import annotations

from typing import Any


def _filter_default(value: Any, default: Any = "", boolean: bool = False) -> Any:
    """Return default if value is undefined or falsy.

    With None-resilient handling, empty string is treated as missing (like None).
    This matches Hugo behavior where nil access returns empty string.

    """
    if boolean:
        return value or default
    # Treat both None and "" as missing (None-resilient compatibility)
    return default if value is None or value == "" else value


def _filter_require(value: Any, message: str | None = None, field_name: str | None = None) -> Any:
    """Require a value to be non-None, raising a clear error if it is.

    Usage:
        {{ user.name | require('User name is required') }}
        {{ config.api_key | require(field_name='api_key') }}

    Args:
        value: The value to check
        message: Custom error message if value is None
        field_name: Field name for the default error message

    Returns:
        The value if not None

    Raises:
        RequiredValueError: If value is None

    """
    from kida.environment.exceptions import RequiredValueError

    if value is None:
        raise RequiredValueError(
            field_name=field_name or "value",
            message=message,
        )
    return value
