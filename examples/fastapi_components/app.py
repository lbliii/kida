"""Typed Kida components inside an existing FastAPI app."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from httpx import ASGITransport, AsyncClient

from kida.contrib.starlette import KidaTemplates

TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI()
templates = KidaTemplates(directory=TEMPLATES_DIR)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Render the full page with Kida's Starlette/FastAPI adapter."""
    return templates.TemplateResponse(
        request,
        "components.html",
        {"title": "First component", "summary": "Edit me"},
    )


@app.post("/preview", response_class=HTMLResponse)
async def preview(request: Request) -> HTMLResponse:
    """Return only the preview block without a multipart dependency."""
    form = parse_qs((await request.body()).decode())
    template = templates.get_template("components.html")
    html = template.render_block(
        "preview",
        title=form.get("title", [""])[0],
        summary=form.get("summary", [""])[0],
    )
    return HTMLResponse(html)


async def _smoke_async() -> None:
    """Exercise both routes through FastAPI's ASGI request path."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        page = await client.get("/")
        assert page.status_code == 200
        assert "Component form" in page.text

        fragment = await client.post(
            "/preview",
            data={"title": "<Admin>", "summary": "Static validation"},
        )
        assert fragment.status_code == 200
        assert "&lt;Admin&gt;" in fragment.text
        assert "<form" not in fragment.text


def smoke() -> None:
    """Run the asynchronous smoke path from a normal Python process."""
    asyncio.run(_smoke_async())
    print("fastapi_components OK")


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        smoke()
    else:
        import uvicorn

        uvicorn.run(app, host="127.0.0.1", port=8000)
