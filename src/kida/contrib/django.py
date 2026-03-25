"""Django integration for Kida.

Provides a Django template backend that uses Kida for rendering.

Setup in ``settings.py``::

    TEMPLATES = [
        {
            "BACKEND": "kida.contrib.django.KidaTemplates",
            "DIRS": [BASE_DIR / "templates"],
            "OPTIONS": {
                "autoescape": True,
                "extensions": [],
            },
        },
    ]

Then use Django's standard template rendering::

    from django.shortcuts import render

    def index(request):
        return render(request, "index.html", {"title": "Home"})

"""

from __future__ import annotations

from typing import Any

from kida import Environment, FileSystemLoader


class KidaTemplates:
    """Django template backend for Kida."""

    app_dirname = "templates"

    def __init__(self, params: dict[str, Any]) -> None:
        options = params.get("OPTIONS", {})
        dirs = list(params.get("DIRS", []))

        self.env = Environment(
            loader=FileSystemLoader(dirs) if dirs else None,
            autoescape=options.get("autoescape", True),
            extensions=options.get("extensions", []),
        )

    def from_string(self, template_code: str) -> KidaTemplate:
        """Create a template from a string."""
        tpl = self.env.from_string(template_code)
        return KidaTemplate(tpl)

    def get_template(self, template_name: str) -> KidaTemplate:
        """Load a template by name."""
        tpl = self.env.get_template(template_name)
        return KidaTemplate(tpl)


class KidaTemplate:
    """Django-compatible template wrapper around a Kida Template."""

    def __init__(self, template: Any) -> None:
        self._template = template

    @property
    def origin(self) -> Any:
        """Template origin for Django's debug toolbar."""

        class _Origin:
            name = self._template.name or "<string>"
            template_name = self._template.name

        return _Origin()

    def render(
        self,
        context: dict[str, Any] | None = None,
        request: Any = None,
    ) -> str:
        """Render the template with the given context.

        Args:
            context: Template context dict.
            request: Django HttpRequest (added to context as 'request').

        Returns:
            Rendered HTML string.
        """
        ctx = context or {}
        if request is not None:
            ctx["request"] = request
        return self._template.render(**ctx)
