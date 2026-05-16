"""Diagnostics and docs contract tests for the stability gate."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from kida import Environment, ErrorCode, FileSystemLoader, UndefinedError
from kida.cli import main


def test_every_error_code_is_documented() -> None:
    """Every public ErrorCode value must have an errors.md anchor."""
    docs = (Path(__file__).resolve().parents[1] / "site/content/docs/errors.md").read_text(
        encoding="utf-8"
    )
    missing = [code.value for code in ErrorCode if f"### {code.value.lower()}" not in docs]
    assert missing == []


def test_check_validate_calls_output_snapshot(tmp_path: Path, capsys) -> None:
    """Representative component diagnostics keep stable CLI formatting."""
    (tmp_path / "components.html").write_text(
        "{% def card(title: str, count: int) %}{{ title }}{% end %}",
        encoding="utf-8",
    )
    (tmp_path / "page.html").write_text(
        '{% from "components.html" import card %}'
        '{{ card(titl="Hi") }}'
        '{{ card("Hi", count="many") }}',
        encoding="utf-8",
    )

    assert main(["check", str(tmp_path), "--validate-calls"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "page.html:1: K-CMP-001: Call to 'card' — unknown params: titl; "
        "missing required: title, count\n"
        "kida check: 1 call-site issue(s)\n"
        "page.html:1: K-CMP-002: type: card() param 'count' expects int, "
        "got str ('many')\n"
        "kida check: 1 type mismatch(es) in call sites\n"
        "kida check: 2 problem(s)\n"
    )


def test_components_json_output_snapshot(tmp_path: Path, capsys) -> None:
    """Machine-readable component inventory JSON is stable for frameworks."""
    (tmp_path / "card.html").write_text(
        "{% def card(title: str, subtitle: str = None) %}"
        "<div>{% slot header %}{% slot %}</div>"
        "{% end %}"
        "{% def badge(label: str) %}<span>{{ label }}</span>{% end %}",
        encoding="utf-8",
    )

    assert main(["components", str(tmp_path), "--json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == [
        {
            "name": "badge",
            "template": "card.html",
            "lineno": 1,
            "params": [
                {
                    "name": "label",
                    "annotation": "str",
                    "has_default": False,
                    "required": True,
                }
            ],
            "slots": [],
            "has_default_slot": False,
            "depends_on": [],
            "vararg": None,
            "kwarg": None,
        },
        {
            "name": "card",
            "template": "card.html",
            "lineno": 1,
            "params": [
                {
                    "name": "title",
                    "annotation": "str",
                    "has_default": False,
                    "required": True,
                },
                {
                    "name": "subtitle",
                    "annotation": "str",
                    "has_default": True,
                    "required": False,
                },
            ],
            "slots": ["header"],
            "has_default_slot": True,
            "depends_on": [],
            "vararg": None,
            "kwarg": None,
        },
    ]


def test_component_warning_format_snapshot() -> None:
    """Environment(validate_calls=True) warnings keep stable formatting."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        env = Environment(validate_calls=True)
        env.from_string(
            "{% def card(title) %}{{ title }}{% end %}{{ card(titl='oops') }}",
            name="page.html",
        )

    assert [str(w.message) for w in caught] == [
        "[K-CMP-001] Call to 'card' has invalid arguments: unknown params: titl; "
        "missing required: title (page.html:1)\n"
        "  Hint: Check the component's {% def %} signature and rename, add, "
        "or remove arguments."
    ]


def test_undefined_error_structured_diagnostic_for_framework_views(tmp_path: Path) -> None:
    """UndefinedError exposes plain data so HTML views do not parse terminal text."""
    (tmp_path / "page.html").write_text(
        "\n".join(
            [
                "<main>",
                "  <script>{{ usernme }}</script>",
                "</main>",
            ]
        ),
        encoding="utf-8",
    )

    env = Environment(loader=FileSystemLoader(str(tmp_path)), fstring_coalescing=False)
    template = env.get_template("page.html")

    with pytest.raises(UndefinedError) as exc_info:
        template.render(username="Ada")

    exc = exc_info.value
    diagnostic = exc.to_diagnostic()

    assert diagnostic.code == "K-RUN-001"
    assert diagnostic.kind == "variable"
    assert diagnostic.location.template == "page.html"
    assert diagnostic.location.line == 2
    assert diagnostic.suggestion == "username"
    assert "Did you mean 'username'?" in diagnostic.hints
    assert diagnostic.docs_url == ErrorCode.UNDEFINED_VARIABLE.docs_url
    assert diagnostic.metadata_dict() == {
        "name": "usernme",
        "kind": "variable",
    }
    assert diagnostic.source_snippet is not None
    assert diagnostic.source_snippet.error_line == 2

    html = diagnostic.format_html_fragment()
    assert "&lt;script&gt;{{ usernme }}&lt;/script&gt;" in html
    assert "<script>{{ usernme }}</script>" not in html
    assert "K-RUN-001" in html
    assert "page.html:2" in html


def test_coalesced_output_preserves_undefined_source_line(tmp_path: Path) -> None:
    """F-string coalescing must not erase the line used by diagnostics."""
    (tmp_path / "page.html").write_text(
        "\n".join(
            [
                "<main>",
                "  <script>{{ usernme }}</script>",
                "</main>",
            ]
        ),
        encoding="utf-8",
    )

    env = Environment(loader=FileSystemLoader(str(tmp_path)))

    with pytest.raises(UndefinedError) as exc_info:
        env.get_template("page.html").render(username="Ada")

    diagnostic = exc_info.value.to_diagnostic()
    assert diagnostic.location.line == 2
    assert diagnostic.source_snippet is not None
    assert diagnostic.source_snippet.error_line == 2


def test_attribute_undefined_diagnostic_keeps_component_stack() -> None:
    """Attribute/key misses carry the same stack context as variable misses."""

    class User:
        name = "Ada"

    template = Environment().from_string(
        "{% def card(user) %}{{ user.nmae }}{% end %}{{ card(user) }}",
        name="page.html",
    )

    with pytest.raises(UndefinedError) as exc_info:
        template.render(user=User())

    diagnostic = exc_info.value.to_diagnostic()
    assert diagnostic.kind == "attribute/key"
    assert diagnostic.suggestion == "User.name"
    assert diagnostic.component_stack
    assert diagnostic.component_stack[0].template == "page.html"
    assert diagnostic.component_stack[0].line == 1
    assert diagnostic.component_stack[0].name == "card"


def test_imported_macro_slot_error_points_to_caller_template(tmp_path: Path) -> None:
    """Slot bodies from imported components report the caller source."""
    (tmp_path / "components.html").write_text(
        "{% def card() %}<section>{% slot %}</section>{% end %}",
        encoding="utf-8",
    )
    (tmp_path / "page.html").write_text(
        "\n".join(
            [
                '{% from "components.html" import card %}',
                "{% call card() %}",
                "  {{ missing_in_slot }}",
                "{% end %}",
            ]
        ),
        encoding="utf-8",
    )

    env = Environment(loader=FileSystemLoader(str(tmp_path)))

    with pytest.raises(UndefinedError) as exc_info:
        env.get_template("page.html").render()

    diagnostic = exc_info.value.to_diagnostic()
    assert diagnostic.location.template == "page.html"
    assert diagnostic.location.line == 3
    assert diagnostic.component_stack
    assert diagnostic.component_stack[0].template == "page.html"
    assert diagnostic.component_stack[0].line == 2
    assert all(frame.line > 0 for frame in diagnostic.component_stack)


def test_render_stream_enhances_generic_runtime_errors() -> None:
    """Streaming diagnostics match render() for generic runtime exceptions."""
    template = Environment().from_string("{{ 1 / zero }}", name="calc.html")

    with pytest.raises(Exception) as exc_info:
        list(template.render_stream(zero=0))

    exc = exc_info.value
    assert exc.__class__.__name__ == "TemplateRuntimeError"
    assert isinstance(exc.__cause__, ZeroDivisionError)
    assert exc.template_name == "calc.html"
    assert exc.lineno == 1


def test_undefined_diagnostic_markdown_escapes_surrounding_text(tmp_path: Path) -> None:
    """Markdown diagnostics share the same data without escaping code fences twice."""
    (tmp_path / "page.html").write_text(
        "## heading\n{{ missing_value }} | @here",
        encoding="utf-8",
    )

    env = Environment(loader=FileSystemLoader(str(tmp_path)), fstring_coalescing=False)

    with pytest.raises(UndefinedError) as exc_info:
        env.get_template("page.html").render()

    markdown = exc_info.value.to_diagnostic().format_markdown()
    assert "### K-RUN-001: Undefined variable" in markdown
    assert "**Location:** `page.html:2`" in markdown
    assert "```text" in markdown
    assert ">   2 | {{ missing_value }} | @here" in markdown
    assert "\\#\\# heading" not in markdown


def test_format_compact_uses_structured_kind() -> None:
    """Terminal compact output stays aligned with diagnostic kind."""
    err = UndefinedError("dict.nickname", kind="attribute/key")

    compact = err.format_compact()

    assert "Undefined attribute/key" in compact
    assert "x?.y" in compact


def test_undefined_diagnostic_html_page_leads_with_fix(tmp_path: Path) -> None:
    """Standalone HTML page keeps the actionable diagnostic before traceback copy."""
    (tmp_path / "page.html").write_text(
        "<main>{{ usernme }}</main>",
        encoding="utf-8",
    )
    env = Environment(loader=FileSystemLoader(str(tmp_path)), fstring_coalescing=False)

    with pytest.raises(UndefinedError) as exc_info:
        env.get_template("page.html").render(username="Ada")

    page = exc_info.value.to_diagnostic().format_html_page()

    assert page.startswith("<!doctype html>")
    assert "First fix:" in page
    assert "Did you mean &#x27;username&#x27;?" in page
    assert "Template Source" in page
    assert "&lt;main&gt;{{ usernme }}&lt;/main&gt;" in page
    assert "<main>{{ usernme }}</main>" not in page
    assert page.index("First fix:") < page.index("Template Source")
    assert page.index("Template Source") < page.index("Python traceback frames are secondary")
