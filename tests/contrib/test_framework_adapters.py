"""Contract tests for optional framework adapters.

The real frameworks are intentionally not test dependencies. Small doubles
prove Kida's adapter behavior and minimal-install import boundary.
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


def test_django_backend_loads_and_wraps_templates(tmp_path: Path) -> None:
    (tmp_path / "hello.html").write_text("Hello {{ name }}", encoding="utf-8")
    backend = DjangoKidaTemplates(
        {
            "DIRS": [tmp_path],
            "OPTIONS": {"autoescape": True, "extensions": []},
        }
    )

    template = backend.get_template("hello.html")
    request = object()

    assert template.render({"name": "Django"}, request) == "Hello Django"
    assert template.origin.name == "hello.html"
    assert template.origin.template_name == "hello.html"
    with pytest.warns(UserWarning, match=r"from_string\(\) without name="):
        inline = backend.from_string("Hi {{ name }}")
    assert inline.render({"name": "string"}) == "Hi string"


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


class _FakeHTMLResponse:
    def __init__(
        self,
        content: str,
        status_code: int,
        headers: dict[str, str] | None,
        media_type: str | None,
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = headers
        self.media_type = media_type


def test_starlette_template_response_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    starlette_module = ModuleType("starlette")
    starlette_module.__path__ = []
    responses_module = ModuleType("starlette.responses")
    responses_module.HTMLResponse = _FakeHTMLResponse
    monkeypatch.setitem(sys.modules, "starlette", starlette_module)
    monkeypatch.setitem(sys.modules, "starlette.responses", responses_module)

    template = _FakeTemplate()
    env = _FakeEnvironment(template)
    templates = StarletteKidaTemplates(
        env=cast("Environment", env),
        context_processors=[lambda request: {"processor": request.user}],
    )
    request = SimpleNamespace(
        user="Ada",
        headers={
            "HX-Request": "true",
            "HX-Target": "results",
            "HX-Trigger": "search",
            "HX-Boosted": "true",
        },
    )

    response = templates.TemplateResponse(
        request,
        "hello.html",
        {"name": "Starlette"},
        status_code=201,
        headers={"X-Test": "yes"},
        media_type="text/custom",
    )

    assert isinstance(response, _FakeHTMLResponse)
    assert response.content == "Hello Starlette"
    assert response.status_code == 201
    assert response.headers == {"X-Test": "yes"}
    assert response.media_type == "text/custom"
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
