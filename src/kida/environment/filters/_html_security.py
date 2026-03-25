"""HTML and security filters for Kida templates."""

from __future__ import annotations

from typing import Any

from kida.utils.html import (
    Markup,
    html_escape_filter,
    strip_tags,
    xmlattr,
)


def _filter_escape(value: Any) -> Markup:
    """HTML-escape the value.

    Returns a Markup object so the result won't be escaped again by autoescape.
    Uses optimized html_escape_filter from utils.html module.

    """
    return html_escape_filter(value)


def _filter_safe(value: Any, reason: str | None = None) -> Markup:
    """Mark value as safe (no HTML escaping).

    Args:
        value: Content to mark as safe for raw HTML output.
        reason: Optional documentation of why this content is trusted.
            Purely for code review and audit purposes - not used at runtime.

    Example:
        {{ content | safe }}
        {{ user_html | safe(reason="sanitized by bleach library") }}
        {{ cms_block | safe(reason="trusted CMS output, admin-only") }}

    """
    return Markup(str(value))


def _filter_striptags(value: str) -> str:
    """Strip HTML tags."""
    return strip_tags(value)


def _filter_xmlattr(value: dict[str, Any]) -> Markup:
    """Convert dict to XML attributes.

    Returns Markup to prevent double-escaping when autoescape is enabled.

    """
    return xmlattr(value)


def _filter_csp_nonce(value: Any, nonce: str | None = None) -> str:
    """Inject CSP nonce into <script> and <style> tags.

    If no nonce is provided, reads from RenderContext metadata
    (``ctx.set_meta("csp_nonce", value)``).

    Example::

        {{ content | csp_nonce }}
        {{ content | csp_nonce("explicit-nonce") }}

    """
    from kida.utils.csp import csp_nonce_filter

    return csp_nonce_filter(value, nonce)
