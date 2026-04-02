"""Flask integration for Kida.

Provides ``init_kida`` to replace Flask's default Jinja2 engine with Kida.

Usage::

    from flask import Flask
    from kida.contrib.flask import init_kida

    app = Flask(__name__)
    kida_env = init_kida(app)

    @app.route("/")
    def index():
        return render_template("index.html", title="Home")

"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kida import Environment, FileSystemLoader


def init_kida(
    app: Any,
    *,
    template_folder: str | None = None,
    **env_kwargs: Any,
) -> Environment:
    """Initialize Kida as the template engine for a Flask app.

    Replaces Flask's default Jinja2 environment with Kida. Templates
    are loaded from the app's template folder.

    Args:
        app: Flask application instance.
        template_folder: Override for template directory.
            Defaults to ``app.template_folder``.
        **env_kwargs: Additional kwargs passed to Kida Environment.

    Returns:
        The configured Kida Environment.
    """
    folder = template_folder or app.template_folder or "templates"
    folder_path = Path(folder)
    if not folder_path.is_absolute():
        folder_path = Path(app.root_path) / folder_path
    folder = str(folder_path)

    env = Environment(
        loader=FileSystemLoader(folder),
        autoescape=True,
        **env_kwargs,
    )

    # Store the environment on the app for access
    app.extensions["kida"] = env

    # Override render_template
    def render_template(template_name: str, **context: Any) -> str:
        """Render a template using Kida."""
        template = env.get_template(template_name)
        return template.render(**context)

    # Monkey-patch Flask's render_template in the app context
    app.kida_env = env
    app.kida_render = render_template

    return env


def render_template(template_name: str, **context: Any) -> str:
    """Render a template using the current app's Kida environment.

    Call this from a Flask request context. Requires ``init_kida()``
    to have been called on the app.

    Args:
        template_name: Name of the template to render.
        **context: Template context variables.

    Returns:
        Rendered HTML string.
    """
    from flask import current_app  # type: ignore[import-untyped]

    env: Environment = current_app.extensions["kida"]
    template = env.get_template(template_name)
    return template.render(**context)
