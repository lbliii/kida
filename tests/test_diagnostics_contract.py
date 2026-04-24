"""Diagnostics and docs contract tests for the stability gate."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from kida import Environment, ErrorCode
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
            "params": [{"name": "label", "annotation": "str", "required": True}],
            "slots": [],
            "has_default_slot": False,
        },
        {
            "name": "card",
            "template": "card.html",
            "lineno": 1,
            "params": [
                {"name": "title", "annotation": "str", "required": True},
                {"name": "subtitle", "annotation": "str", "required": False},
            ],
            "slots": ["header"],
            "has_default_slot": True,
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
