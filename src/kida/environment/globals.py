"""Default global functions and variables for templates.

This module provides built-in global functions that are available in all
templates. These functions are registered in the Environment by default.

HTMX Helpers:
    Functions for detecting and responding to HTMX requests in templates.
    These integrate with web frameworks (like Chirp) that set metadata via
    RenderContext.set_meta().

Security Helpers:
    Functions for CSRF token injection and other security features.

Usage:
    Frameworks should populate RenderContext metadata:

        from kida.render_context import render_context

        with render_context() as ctx:
            ctx.set_meta("hx_request", True)
            ctx.set_meta("hx_target", "user-list")
            ctx.set_meta("csrf_token", generate_token())

            html = template.render(**data)

    Templates can then access via globals:

        {% if hx_request() %}
          {# Render fragment for HTMX #}
        {% else %}
          {# Render full page #}
        {% end %}
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.template import Markup


def hx_request() -> bool:
    """Check if current request is from HTMX.

    Returns True if the framework has set the hx_request metadata flag,
    indicating this is an HTMX-initiated request rather than a full page load.

    Usage:
        {% if hx_request() %}
          {# Partial render - just the updated component #}
          {% block content %}...{% end %}
        {% else %}
          {# Full page render #}
          {% extends "base.html" %}
        {% end %}

    Framework Integration:
        # In your web framework (e.g., Chirp):
        from kida.render_context import render_context

        with render_context() as ctx:
            # Detect HTMX via HX-Request header
            is_htmx = request.headers.get("HX-Request") == "true"
            ctx.set_meta("hx_request", is_htmx)

            html = template.render(**data)

    Returns:
        bool: True if request is from HTMX, False otherwise
    """
    from kida.render_context import get_render_context

    ctx = get_render_context()
    if ctx is None:
        return False
    return ctx.get_meta("hx_request", False)


def hx_target() -> str | None:
    """Get HTMX target element ID.

    Returns the value of the HX-Target header, which indicates which element
    HTMX will swap content into. Useful for conditional rendering based on
    which part of the page is being updated.

    Usage:
        {% if hx_target() == "user-list" %}
          {# Render just the user list #}
          <ul id="user-list">
            {% for user in users %}
              <li>{{ user.name }}</li>
            {% end %}
          </ul>
        {% end %}

    Framework Integration:
        with render_context() as ctx:
            target = request.headers.get("HX-Target")
            ctx.set_meta("hx_target", target)

    Returns:
        str | None: Target element ID, or None if not set
    """
    from kida.render_context import get_render_context

    ctx = get_render_context()
    if ctx is None:
        return None
    return ctx.get_meta("hx_target", None)


def hx_trigger() -> str | None:
    """Get HTMX trigger element ID.

    Returns the value of the HX-Trigger header, which indicates which element
    triggered the HTMX request. Useful for tracking which button/link initiated
    an action.

    Usage:
        {% if hx_trigger() == "delete-button" %}
          <div class="alert alert-success">Item deleted</div>
        {% end %}

    Framework Integration:
        with render_context() as ctx:
            trigger = request.headers.get("HX-Trigger")
            ctx.set_meta("hx_trigger", trigger)

    Returns:
        str | None: Trigger element ID, or None if not set
    """
    from kida.render_context import get_render_context

    ctx = get_render_context()
    if ctx is None:
        return None
    return ctx.get_meta("hx_trigger", None)


def hx_boosted() -> bool:
    """Check if request is HTMX-boosted.

    Returns True if the request came from an element with hx-boost="true",
    which means HTMX is progressively enhancing a standard link/form to use
    AJAX instead of a full page load.

    Usage:
        {% if hx_boosted() %}
          {# Enhanced navigation - smooth transition #}
          <div class="page-transition">
            {% block content %}...{% end %}
          </div>
        {% else %}
          {# Standard page load #}
        {% end %}

    Framework Integration:
        with render_context() as ctx:
            boosted = request.headers.get("HX-Boosted") == "true"
            ctx.set_meta("hx_boosted", boosted)

    Returns:
        bool: True if request is boosted, False otherwise
    """
    from kida.render_context import get_render_context

    ctx = get_render_context()
    if ctx is None:
        return False
    return ctx.get_meta("hx_boosted", False)


def csrf_token() -> Markup:
    """Generate CSRF token hidden input for forms.

    Returns a hidden input field containing the CSRF token. The framework
    must set the token via RenderContext.set_meta("csrf_token", value).

    Renders as:
        <input type="hidden" name="csrf_token" value="TOKEN_VALUE">

    Usage:
        <form method="POST" action="/submit">
          {{ csrf_token() }}

          <input type="email" name="email" required>
          <button type="submit">Submit</button>
        </form>

    Framework Integration:
        # In your web framework:
        from kida.render_context import render_context

        with render_context() as ctx:
            # Generate token (framework-specific)
            token = session.generate_csrf_token()
            ctx.set_meta("csrf_token", token)

            html = template.render(**data)

        # Framework middleware should validate the token on POST

    Security:
        The token value is automatically HTML-escaped to prevent XSS.
        Returns Markup so the HTML is not double-escaped in templates.

    Returns:
        Markup: Safe HTML for hidden input field

    Warns:
        UserWarning: If csrf_token() is called but no token was set
    """
    from kida.render_context import get_render_context
    from kida.template import Markup

    ctx = get_render_context()
    token = ""

    if ctx is not None:
        token = ctx.get_meta("csrf_token", "")

    if not token:
        import warnings

        warnings.warn(
            "csrf_token() called but no token provided. "
            "Framework should call render_context.set_meta('csrf_token', token) "
            "before rendering. This form submission will fail CSRF validation.",
            UserWarning,
            stacklevel=2,
        )
        return Markup("")

    # Return Markup so it's not double-escaped
    # HTML-escape the token value for safety
    escaped_token = html.escape(token, quote=True)
    return Markup(f'<input type="hidden" name="csrf_token" value="{escaped_token}">')


# Default globals dictionary
# These are registered in Environment.__init__ when enable_htmx_helpers=True
HTMX_GLOBALS = {
    "hx_request": hx_request,
    "hx_target": hx_target,
    "hx_trigger": hx_trigger,
    "hx_boosted": hx_boosted,
    "csrf_token": csrf_token,
}


__all__ = [
    "HTMX_GLOBALS",
    "csrf_token",
    "hx_boosted",
    "hx_request",
    "hx_target",
    "hx_trigger",
]
