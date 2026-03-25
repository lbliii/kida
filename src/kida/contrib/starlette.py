"""Starlette/FastAPI integration for Kida.

Provides ``KidaTemplates`` — a drop-in replacement for Starlette's
``Jinja2Templates``.

Usage::

    from fastapi import FastAPI
    from kida.contrib.starlette import KidaTemplates

    app = FastAPI()
    templates = KidaTemplates(directory="templates")

    @app.get("/")
    async def homepage(request: Request):
        return templates.TemplateResponse(
            request, "index.html", {"title": "Home"}
        )

"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from kida import Environment, FileSystemLoader

if TYPE_CHECKING:
    pass


class KidaTemplates:
    """Starlette-compatible template renderer powered by Kida.

    Args:
        directory: Path to template directory.
        env: Optional pre-configured Kida Environment.
            If not provided, one is created with FileSystemLoader.
        context_processors: Optional list of callables that take a request
            and return a dict of additional context variables.
        **env_kwargs: Additional kwargs passed to Environment() if env is None.
    """

    def __init__(
        self,
        directory: str | Path | None = None,
        *,
        env: Environment | None = None,
        context_processors: list[Any] | None = None,
        **env_kwargs: Any,
    ) -> None:
        if env is not None:
            self.env = env
        elif directory is not None:
            self.env = Environment(
                loader=FileSystemLoader(str(directory)),
                **env_kwargs,
            )
        else:
            raise ValueError("Either 'directory' or 'env' must be provided")

        self._context_processors = context_processors or []

    def get_template(self, name: str) -> Any:
        """Get a template by name."""
        return self.env.get_template(name)

    def TemplateResponse(  # noqa: N802 — matches Starlette convention
        self,
        request: Any,
        name: str,
        context: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        media_type: str | None = None,
    ) -> Any:
        """Render a template and return a Starlette Response.

        Args:
            request: Starlette Request object.
            name: Template name.
            context: Template context variables.
            status_code: HTTP status code.
            headers: Additional response headers.
            media_type: Response media type.

        Returns:
            starlette.responses.HTMLResponse
        """
        from starlette.responses import HTMLResponse  # type: ignore[import-untyped]

        ctx = {"request": request}
        if context:
            ctx.update(context)

        # Run context processors
        for processor in self._context_processors:
            ctx.update(processor(request))

        # Set HTMX metadata from request headers if available
        from kida.render_context import render_context

        with render_context(template_name=name) as rc:
            hx_request = request.headers.get("HX-Request")
            if hx_request:
                rc.set_meta("hx_request", hx_request == "true")
                rc.set_meta("hx_target", request.headers.get("HX-Target"))
                rc.set_meta("hx_trigger", request.headers.get("HX-Trigger"))
                rc.set_meta("hx_boosted", request.headers.get("HX-Boosted") == "true")

            template = self.env.get_template(name)
            content = template.render(**ctx)

        return HTMLResponse(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )
