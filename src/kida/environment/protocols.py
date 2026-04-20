"""Protocols for Kida environment components.

Defines protocols for loaders, filters, and tests. These are static-only
type hints — they are not decorated with ``@runtime_checkable`` and are
not used with ``isinstance()`` anywhere in the codebase.
"""

from __future__ import annotations

from typing import Any, Protocol


class Loader(Protocol):
    """Protocol for template loaders."""

    def get_source(self, name: str) -> tuple[str, str | None]:
        """Load template source.

        Args:
            name: Template identifier

        Returns:
            Tuple of (source_code, optional_filename)

        Raises:
            TemplateNotFoundError: If template doesn't exist
        """
        ...

    def list_templates(self) -> list[str]:
        """List all available templates."""
        ...


class Filter(Protocol):
    """Protocol for template filters."""

    def __call__(self, value: Any, *args: Any, **kwargs: Any) -> Any:
        """Apply filter to value."""
        ...


class Test(Protocol):
    """Protocol for template tests."""

    def __call__(self, value: Any, *args: Any, **kwargs: Any) -> bool:
        """Test value, return True/False."""
        ...
