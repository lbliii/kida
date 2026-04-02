"""Public composition API for template structure and block validation.

Provides validation helpers for frameworks like Chirp that compose templates
via block rendering and layout assembly. Use these to validate block existence
and structure before rendering, enabling clearer errors and composition planning.

Example:
    >>> from kida import Environment
    >>> from kida.composition import validate_block_exists, get_structure
    >>> env = Environment(loader=FileSystemLoader("templates/"))
    >>> if validate_block_exists(env, "page.html", "content"):
    ...     html = env.get_template("page.html").render_block("content", ...)
    >>> struct = get_structure(env, "page.html")
    >>> if struct and "page_root" in struct.block_names:
    ...     ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kida.analysis.metadata import TemplateStructureManifest
    from kida.environment import Environment
    from kida.template import Template


def validate_block_exists(
    env: Environment,
    template_name: str,
    block_name: str,
) -> bool:
    """Check if a block exists in a template (including inherited blocks).

    Uses list_blocks() which reflects the effective block map after
    inheritance. Useful for frameworks to validate ViewRef/block_name
    before calling render_block().

    Args:
        env: Kida Environment.
        template_name: Template identifier (e.g., "page.html").
        block_name: Block to check (e.g., "content", "page_root").

    Returns:
        True if the block exists, False if template not found or block missing.

    Example:
        >>> if validate_block_exists(env, "skills/page.html", "page_content"):
        ...     html = env.get_template("skills/page.html").render_block(...)
    """
    if not block_name:
        return False
    try:
        from kida.exceptions import (
            TemplateNotFoundError,
            TemplateSyntaxError,
        )

        template = env.get_template(template_name)
        return block_name in template.list_blocks()
    except TemplateNotFoundError, TemplateSyntaxError, RuntimeError:
        return False


def validate_template_block(template: Template, block_name: str) -> bool:
    """Check if a block exists in a Template instance.

    Convenience when you already have a loaded Template. Uses list_blocks()
    which includes inherited blocks.

    Args:
        template: Loaded Kida Template.
        block_name: Block to check.

    Returns:
        True if the block exists.
    """
    return block_name in template.list_blocks() if block_name else False


def get_structure(env: Environment, template_name: str) -> TemplateStructureManifest | None:
    """Get lightweight structure manifest for a template.

    Returns block names, extends parent, block hashes, and dependencies.
    Cached by Environment for reuse. Returns None if template not found
    or analysis unavailable (e.g., no preserved AST).

    Args:
        env: Kida Environment.
        template_name: Template identifier.

    Returns:
        TemplateStructureManifest or None.

    Example:
        >>> struct = get_structure(env, "page.html")
        >>> if struct:
        ...     print(f"Blocks: {struct.block_names}")
        ...     print(f"Extends: {struct.extends}")
    """
    return env.get_template_structure(template_name)


def block_role_for_framework(
    block_metadata: Any,
    *,
    content_roles: frozenset[str] = frozenset({"content", "main", "page_content"}),
    root_roles: frozenset[str] = frozenset({"page_root", "root", "layout"}),
) -> str | None:
    """Classify block metadata into framework-relevant roles.

    Maps BlockMetadata.inferred_role and block name to Chirp-style roles:
    - "fragment": suitable for narrow fragment (content, main)
    - "page_root": suitable for boosted page root
    - None: unknown or not applicable

    Args:
        block_metadata: BlockMetadata from template_metadata().blocks.
        content_roles: Block names treated as content/fragment.
        root_roles: Block names treated as page root.

    Returns:
        "fragment", "page_root", or None.
    """
    if block_metadata is None:
        return None
    name = getattr(block_metadata, "name", "")
    role = getattr(block_metadata, "inferred_role", "unknown")
    if name in content_roles or role == "content":
        return "fragment"
    if name in root_roles or role in ("header", "footer", "navigation"):
        return "page_root" if name in root_roles else None
    return None
