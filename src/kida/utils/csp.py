"""Content Security Policy (CSP) nonce injection.

Auto-injects ``nonce="..."`` into ``<script>`` and ``<style>`` tags for
CSP compliance. Works as a post-processing step on rendered HTML.

Usage via RenderContext metadata::

    from kida.render_context import render_context

    with render_context() as ctx:
        ctx.set_meta("csp_nonce", "abc123")
        html = template.render(**data)
    # All <script> and <style> tags now have nonce="abc123"

Usage as a filter::

    {{ content | csp_nonce("abc123") }}

Usage as a standalone function::

    from kida.utils.csp import inject_csp_nonce
    safe_html = inject_csp_nonce(html, "abc123")

"""

from __future__ import annotations

import html
import re
from typing import Any

# Match opening <script> and <style> tags (case-insensitive)
# Captures: tag name, existing attributes, self-closing slash
_TAG_RE = re.compile(
    r"(<\s*(?:script|style))"  # Opening + tag name
    r"(\s[^>]*)?"  # Optional attributes
    r"(>)",  # Closing >
    re.IGNORECASE,
)

# Check if a nonce attribute already exists
_HAS_NONCE_RE = re.compile(r"\bnonce\s*=", re.IGNORECASE)


def inject_csp_nonce(html_content: str, nonce: str) -> str:
    """Inject CSP nonce into all <script> and <style> tags.

    Adds ``nonce="..."`` to every ``<script>`` and ``<style>`` tag that
    doesn't already have a nonce attribute. The nonce value is HTML-escaped
    for safety.

    Args:
        html_content: Rendered HTML string.
        nonce: CSP nonce value (typically base64-encoded random bytes).

    Returns:
        HTML with nonce attributes injected.

    Example::

        >>> inject_csp_nonce('<script>alert(1)</script>', 'abc123')
        '<script nonce="abc123">alert(1)</script>'

        >>> inject_csp_nonce('<script nonce="old">x</script>', 'new')
        '<script nonce="old">x</script>'

    """
    if not nonce:
        return html_content

    escaped_nonce = html.escape(nonce, quote=True)
    nonce_attr = f' nonce="{escaped_nonce}"'

    def _inject(match: re.Match[str]) -> str:
        tag_open = match.group(1)  # e.g. "<script"
        attrs = match.group(2) or ""  # existing attributes
        close = match.group(3)  # ">"

        # Don't add nonce if one already exists
        if _HAS_NONCE_RE.search(attrs):
            return match.group(0)

        return f"{tag_open}{attrs}{nonce_attr}{close}"

    return _TAG_RE.sub(_inject, html_content)


def csp_nonce_filter(value: Any, nonce: str | None = None) -> str:
    """Template filter: inject CSP nonce into HTML content.

    If no nonce is provided, reads from the current RenderContext metadata
    (set by the framework via ``ctx.set_meta("csp_nonce", value)``).

    Usage in templates::

        {{ content | csp_nonce }}
        {{ content | csp_nonce("explicit-nonce") }}

    """
    if nonce is None:
        from kida.render_context import get_render_context

        ctx = get_render_context()
        if ctx is not None:
            nonce = ctx.get_meta("csp_nonce", None)  # type: ignore[assignment]

    if not nonce:
        return str(value)

    return inject_csp_nonce(str(value), nonce)


def csp_nonce_global() -> str:
    """Template global: get the current CSP nonce value.

    Returns the nonce string from RenderContext metadata, or empty string
    if not set.

    Usage in templates::

        <script nonce="{{ csp_nonce() }}">
            // inline script
        </script>

    """
    from kida.render_context import get_render_context

    ctx = get_render_context()
    if ctx is not None:
        nonce = ctx.get_meta("csp_nonce", "")
        return str(nonce) if nonce else ""
    return ""
