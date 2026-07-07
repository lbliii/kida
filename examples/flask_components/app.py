"""Typed Kida components inside an existing Flask app."""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, request

from kida.contrib.flask import init_kida, render_template

TEMPLATES_DIR = Path(__file__).parent / "templates"

app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
kida_env = init_kida(app)


@app.get("/")
def home() -> str:
    """Render the full page through Flask's current application context."""
    return render_template("components.html", title="First component", summary="Edit me")


@app.post("/preview")
def preview() -> str:
    """Return only the preview block for an HTML-over-the-wire update."""
    template = kida_env.get_template("components.html")
    return template.render_block(
        "preview",
        title=request.form.get("title", ""),
        summary=request.form.get("summary", ""),
    )


def smoke() -> None:
    """Exercise both the full-page and fragment routes without starting a server."""
    client = app.test_client()

    page = client.get("/")
    assert page.status_code == 200
    assert "Component form" in page.get_data(as_text=True)

    fragment = client.post(
        "/preview",
        data={"title": "<Admin>", "summary": "Static validation"},
    )
    fragment_html = fragment.get_data(as_text=True)
    assert fragment.status_code == 200
    assert "&lt;Admin&gt;" in fragment_html
    assert "<form" not in fragment_html
    print("flask_components OK")


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        smoke()
    else:
        app.run(debug=True)
