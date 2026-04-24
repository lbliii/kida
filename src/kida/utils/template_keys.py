"""Canonical template name normalization for cache keys and import_stack lookups."""

from __future__ import annotations

import posixpath


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


def resolve_template_name(name: str, caller: str | None = None) -> str:
    """Resolve a template name to a canonical root-relative form.

    Handles ``./`` and ``../`` prefixes by resolving against the caller
    template's directory. Falls through to :func:`normalize_template_name`
    for absolute (root-relative) names.

    Args:
        name: Raw template name. May start with ``./`` or ``../`` for
            relative resolution.
        caller: Logical name of the template issuing the request (e.g.
            ``"pages/about.html"``). Required when ``name`` is relative.

    Returns:
        Normalized, root-relative name suitable for cache keys and loader
        lookups. For absolute names, this matches
        :func:`normalize_template_name` exactly.

    Raises:
        TemplateNotFoundError:
            - If ``name`` is relative but no ``caller`` is provided.
            - If resolution escapes above the template root.
            - If a non-relative ``name`` still contains ``..`` segments.
    """
    stripped = name.strip().replace("\\", "/")
    if stripped.startswith(("./", "../")):
        if not caller:
            from kida.exceptions import TemplateNotFoundError

            raise TemplateNotFoundError(
                f"Relative path '{name}' requires a caller template. "
                "Relative paths work only inside {% include %}, {% extends %}, "
                "{% embed %}, or {% from ... import ... %}. "
                "From Python, use the absolute template name."
            )
        caller_dir = posixpath.dirname(caller.replace("\\", "/"))
        joined = posixpath.join(caller_dir, stripped) if caller_dir else stripped
        resolved = posixpath.normpath(joined)
        if resolved == ".." or resolved.startswith("../"):
            from kida.exceptions import TemplateNotFoundError

            raise TemplateNotFoundError(
                f"Relative path '{name}' from '{caller}' escapes the template root."
            )
        # `./x` at the root produces `"x"`; `.` alone produces `"."` — treat as invalid.
        if resolved == ".":
            from kida.exceptions import TemplateNotFoundError

            raise TemplateNotFoundError(
                f"Relative path '{name}' from '{caller}' does not name a template."
            )
        return resolved
    return normalize_template_name(stripped)
