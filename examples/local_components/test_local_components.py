"""Contracts for the app-owned local component example."""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING

from kida.cli import main as cli_main
from kida.diagnostics import DiagnosticOptions
from kida.inspection import TemplateRoot, diagnose_roots, inspect_components

if TYPE_CHECKING:
    from pathlib import Path


def test_server_rendered_state_is_accessible(example_app) -> None:
    output = example_app.output

    assert '<form class="search-panel__form" role="search" method="get">' in output
    assert 'role="status" aria-live="polite"' in output
    assert "2 results for “components”." in output
    assert '<label class="field__label" for="q">Search</label>' in output
    assert 'aria-describedby="search-help"' in output
    assert "Component authoring contract" in output
    assert '<li class="result-list__empty" hidden>' in output


def test_empty_state_is_rendered_on_the_server(example_app) -> None:
    output = example_app.render_page(query="missing", results=[])

    assert "0 results for “missing”." in output
    assert "No docs matched. Try a broader term." in output
    assert '<li class="result-list__empty">' in output
    assert "result-card" not in output


def test_check_and_component_metadata_are_machine_readable(
    example_app,
    capsys,
) -> None:
    check_exit = cli_main(
        [
            "check",
            "--root",
            f"app={example_app.TEMPLATES_DIR}",
            "--validate-calls",
            "--a11y",
            "--format",
            "json",
        ]
    )
    check_payload = json.loads(capsys.readouterr().out)

    components_exit = cli_main(
        [
            "components",
            "--root",
            f"app={example_app.TEMPLATES_DIR}",
            "--json",
        ]
    )
    components = json.loads(capsys.readouterr().out)

    assert check_exit == 0
    assert check_payload["diagnostics"] == []
    assert components_exit == 0
    assert [(row["owner"], row["template"], row["name"]) for row in components] == [
        ("app", "app/components/controls.html", "text_field"),
        ("app", "app/components/controls.html", "submit_button"),
        ("app", "app/patterns/search-panel.html", "search_panel"),
    ]
    search_panel = components[-1]
    assert set(search_panel["slots"]) == {"no_results", "result"}
    assert search_panel["source_path"] == str(
        (example_app.TEMPLATES_DIR / "patterns" / "search-panel.html").resolve()
    )


def test_invalid_prop_has_an_actionable_owned_diagnostic(
    example_app,
    tmp_path: Path,
) -> None:
    templates = tmp_path / "templates"
    shutil.copytree(example_app.TEMPLATES_DIR, templates)
    page_path = templates / "pages" / "search.html"
    page_path.write_text(
        page_path.read_text(encoding="utf-8").replace("query=query", "qurey=query"),
        encoding="utf-8",
    )

    report = diagnose_roots(
        (TemplateRoot("app", templates),),
        options=DiagnosticOptions(validate_calls=True),
    )

    assert [diagnostic.code for diagnostic in report.diagnostics] == ["K-CMP-001"]
    diagnostic = report.diagnostics[0]
    assert diagnostic.span.path == "app/pages/search.html"
    assert "unknown params: qurey" in diagnostic.message
    assert "missing required: query" in diagnostic.message
    assert dict(diagnostic.metadata) == {
        "def_name": "search_panel",
        "missing_required": "query",
        "owner": "app",
        "source_path": str(page_path),
        "unknown_params": "qurey",
    }


def test_broken_scoped_slot_contract_has_an_actionable_static_diagnostic(
    example_app,
    tmp_path: Path,
) -> None:
    templates = tmp_path / "templates"
    shutil.copytree(example_app.TEMPLATES_DIR, templates)
    page_path = templates / "pages" / "search.html"
    page_path.write_text(
        page_path.read_text(encoding="utf-8").replace(
            "{% slot result let:item %}",
            "{% slot result let: %}",
        ),
        encoding="utf-8",
    )
    report = diagnose_roots(
        (TemplateRoot("app", templates),),
        options=DiagnosticOptions(validate_calls=True),
    )

    assert [diagnostic.code for diagnostic in report.diagnostics] == ["K-PAR-001"]
    diagnostic = report.diagnostics[0]
    assert diagnostic.span.path == "app/pages/search.html"
    assert "Expected parameter name after 'let:'" in diagnostic.message
    assert diagnostic.suggestion == ("Scoped slot syntax: {% slot name let:item, let:index %}")
    assert dict(diagnostic.metadata) == {
        "owner": "app",
        "source_path": str(page_path),
    }


def test_programmatic_inventory_is_deterministic(example_app) -> None:
    roots = (TemplateRoot("app", example_app.TEMPLATES_DIR),)

    first = inspect_components(roots)
    second = inspect_components(roots)

    assert first == second
    assert first.diagnostics == ()
    assert first.partial is False
    assert (example_app.STYLES_DIR / "tokens.css").is_file()
    assert (example_app.STYLES_DIR / "components.css").is_file()
