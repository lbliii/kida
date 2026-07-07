"""Contract tests for optional framework adapters.

Current frameworks are dev-only test dependencies. Focused doubles still prove
Kida's minimal-install import boundary and render-context handoff in isolation.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from kida.contrib.django import KidaTemplates as DjangoKidaTemplates
from kida.contrib.flask import init_kida
from kida.contrib.starlette import KidaTemplates as StarletteKidaTemplates
from kida.render_context import get_render_context_required

if TYPE_CHECKING:
    from kida import Environment


def test_contrib_modules_import_without_optional_frameworks() -> None:
    for module_name in (
        "kida.contrib.flask",
        "kida.contrib.django",
        "kida.contrib.starlette",
    ):
        assert importlib.import_module(module_name) is not None


def test_flask_init_registers_environment_and_app_render_helper(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "hello.html").write_text("Hello {{ name }}", encoding="utf-8")
    app = SimpleNamespace(
        root_path=str(tmp_path),
        template_folder="templates",
        extensions={},
    )

    env = init_kida(app, auto_reload=False)

    assert app.extensions["kida"] is env
    assert app.kida_env is env
    assert app.kida_render("hello.html", name="Kida") == "Hello Kida"


def test_flask_render_template_uses_current_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from kida.contrib.flask import render_template

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "hello.html").write_text("Hello {{ name }}", encoding="utf-8")
    app = SimpleNamespace(
        root_path=str(tmp_path),
        template_folder="templates",
        extensions={},
    )
    init_kida(app)

    flask_module = ModuleType("flask")
    flask_module.current_app = app
    monkeypatch.setitem(sys.modules, "flask", flask_module)

    assert render_template("hello.html", name="Flask") == "Hello Flask"


def test_flask_adapter_with_current_flask(tmp_path: Path) -> None:
    from flask import Flask

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "hello.html").write_text("Hello {{ name }}", encoding="utf-8")
    app = Flask(__name__, root_path=str(tmp_path), template_folder="templates")
    init_kida(app)

    @app.get("/")
    def home() -> str:
        return app.kida_render("hello.html", name="Flask 3")

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "Hello Flask 3"


def test_django_backend_loads_and_wraps_templates(tmp_path: Path) -> None:
    from django.template.utils import EngineHandler

    (tmp_path / "hello.html").write_text("Hello {{ name }}", encoding="utf-8")
    engines = EngineHandler(
        templates=[
            {
                "NAME": "kida",
                "BACKEND": "kida.contrib.django.KidaTemplates",
                "APP_DIRS": False,
                "DIRS": [tmp_path],
                "OPTIONS": {"autoescape": True, "extensions": []},
            }
        ]
    )
    backend = engines["kida"]

    assert isinstance(backend, DjangoKidaTemplates)
    template = backend.get_template("hello.html")
    request = object()

    assert template.render({"name": "Django 6"}, request) == "Hello Django 6"
    assert template.origin.name == "hello.html"
    assert template.origin.template_name == "hello.html"
    with pytest.warns(UserWarning, match=r"from_string\(\) without name="):
        inline = backend.from_string("Hi {{ name }}")
    assert inline.render({"name": "string"}) == "Hi string"


def test_django_backend_ignores_standard_engine_keys(tmp_path: Path) -> None:
    backend = DjangoKidaTemplates(
        {
            "NAME": "kida",
            "APP_DIRS": False,
            "DIRS": [tmp_path],
            "OPTIONS": {"autoescape": True, "extensions": []},
        }
    )

    assert backend.env is not None


class _FakeTemplate:
    def __init__(self) -> None:
        self.context: dict[str, object] = {}
        self.metadata: dict[str, object] = {}

    def render(self, **context: object) -> str:
        self.context = context
        render_ctx = get_render_context_required()
        self.metadata = {
            key: render_ctx.get_meta(key)
            for key in ("hx_request", "hx_target", "hx_trigger", "hx_boosted")
        }
        return f"Hello {context['name']}"


class _FakeEnvironment:
    def __init__(self, template: _FakeTemplate) -> None:
        self.template = template

    def get_template(self, name: str) -> _FakeTemplate:
        assert name == "hello.html"
        return self.template


def test_starlette_template_response_contract() -> None:
    from starlette.requests import Request
    from starlette.responses import HTMLResponse

    template = _FakeTemplate()
    env = _FakeEnvironment(template)
    templates = StarletteKidaTemplates(
        env=cast("Environment", env),
        context_processors=[lambda request: {"processor": request.state.user}],
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [
                (b"hx-request", b"true"),
                (b"hx-target", b"results"),
                (b"hx-trigger", b"search"),
                (b"hx-boosted", b"true"),
            ],
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )
    request.state.user = "Ada"

    response = templates.TemplateResponse(
        request,
        "hello.html",
        {"name": "Starlette"},
        status_code=201,
        headers={"X-Test": "yes"},
        media_type="text/custom",
    )

    assert isinstance(response, HTMLResponse)
    assert response.body == b"Hello Starlette"
    assert response.status_code == 201
    assert response.headers["X-Test"] == "yes"
    assert response.headers["content-type"] == "text/custom; charset=utf-8"
    assert template.context == {
        "request": request,
        "name": "Starlette",
        "processor": "Ada",
    }
    assert template.metadata == {
        "hx_request": True,
        "hx_target": "results",
        "hx_trigger": "search",
        "hx_boosted": True,
    }
