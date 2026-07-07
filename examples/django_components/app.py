"""Typed Kida components inside an existing Django app."""

from __future__ import annotations

import sys
from pathlib import Path

import django
from django.conf import settings
from django.core.management import execute_from_command_line
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template import engines
from django.test import Client
from django.urls import path

TEMPLATES_DIR = Path(__file__).parent / "templates"

if not settings.configured:
    settings.configure(
        ALLOWED_HOSTS=["localhost", "testserver"],
        DEBUG=True,
        MIDDLEWARE=[],
        ROOT_URLCONF=__name__,
        SECRET_KEY="kida-example",
        TEMPLATES=[
            {
                "BACKEND": "kida.contrib.django.KidaTemplates",
                "DIRS": [TEMPLATES_DIR],
                "NAME": "kida",
                "OPTIONS": {"autoescape": True},
            }
        ],
    )

django.setup()


def home(request: HttpRequest) -> HttpResponse:
    """Render the full page through Django's configured template backend."""
    return render(
        request,
        "components.html",
        {"title": "First component", "summary": "Edit me"},
    )


def preview(request: HttpRequest) -> HttpResponse:
    """Return only the preview block through the configured Kida backend."""
    template = engines["kida"].env.get_template("components.html")
    html = template.render_block(
        "preview",
        title=request.POST.get("title", ""),
        summary=request.POST.get("summary", ""),
    )
    return HttpResponse(html)


urlpatterns = [
    path("", home),
    path("preview", preview),
]


def smoke() -> None:
    """Exercise both routes with Django's real test client."""
    client = Client()

    page = client.get("/")
    assert page.status_code == 200
    assert "Component form" in page.content.decode()

    fragment = client.post(
        "/preview",
        {"title": "<Admin>", "summary": "Static validation"},
    )
    fragment_html = fragment.content.decode()
    assert fragment.status_code == 200
    assert "&lt;Admin&gt;" in fragment_html
    assert "<form" not in fragment_html
    print("django_components OK")


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        smoke()
    else:
        execute_from_command_line([sys.argv[0], "runserver", "127.0.0.1:8000"])
