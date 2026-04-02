"""Canonical template name normalization for cache keys and import_stack lookups."""

from __future__ import annotations


def normalize_template_name(name: str) -> str:
    """Normalize template name for cache keys and import_stack lookups.

    - Strip whitespace
    - Normalize path separators to /
    - Reject .. and path traversal (raises TemplateNotFoundError)

    Args:
        name: Raw template name from {% extends %}, {% include %}, etc.

    Returns:
        Normalized name suitable for cache keys and loader lookups.

    Raises:
        TemplateNotFoundError: If name contains path traversal (..).
    """
    normalized = name.strip().replace("\\", "/")
    # Reject path traversal (import deferred to raise path only)
    parts = normalized.split("/")
    for part in parts:
        if part == "..":
            from kida.exceptions import TemplateNotFoundError

            raise TemplateNotFoundError(name)
    return normalized
