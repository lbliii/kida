"""Public and CLI contracts for explicit namespaced template roots."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kida import Environment
from kida.cli import main
from kida.diagnostics import DiagnosticOptions
from kida.environment import FileSystemLoader, PrefixLoader
from kida.inspection import TemplateRoot, diagnose_roots, inspect_components


def _write_roots(tmp_path: Path, *, invalid_call: bool = False) -> tuple[Path, Path]:
    framework = tmp_path / "framework"
    app = tmp_path / "app"
    framework.mkdir()
    app.mkdir()
    (framework / "components.html").write_text(
        "{% def card(title: str) %}<article>{{ title }}</article>{% end %}",
        encoding="utf-8",
    )
    argument = 'titl="Home"' if invalid_call else 'title="Home"'
    (app / "page.html").write_text(
        f'{{% from "framework/components.html" import card %}}{{{{ card({argument}) }}}}',
        encoding="utf-8",
    )
    return framework, app


def _root_args(framework: Path, app: Path) -> list[str]:
    return [
        "--root",
        f"framework={framework}",
        "--root",
        f"app={app}",
    ]


def test_programmatic_roots_support_cross_root_calls_and_components(tmp_path: Path) -> None:
    framework, app = _write_roots(tmp_path)
    roots = (
        TemplateRoot("framework", framework),
        TemplateRoot("app", app),
    )

    report = diagnose_roots(
        roots,
        options=DiagnosticOptions(validate_calls=True),
    )
    components = inspect_components(roots)

    assert report == type(report)(diagnostics=(), partial=False)
    assert len(components.components) == 1
    record = components.components[0]
    assert record.owner == "framework"
    assert record.template == "framework/components.html"
    assert record.source_path == str((framework / "components.html").resolve())
    assert record.metadata.name == "card"
    assert record.metadata.template_name == "framework/components.html"
    assert components.diagnostics == ()
    assert components.partial is False


def test_adapter_environment_supplies_filters_without_config_surface(tmp_path: Path) -> None:
    framework = tmp_path / "framework"
    app = tmp_path / "app"
    framework.mkdir()
    app.mkdir()
    (framework / "components.html").write_text(
        "{% def badge(label) %}{{ label | shout }}{% end %}",
        encoding="utf-8",
    )
    (app / "page.html").write_text(
        '{% from "framework/components.html" import badge %}{{ badge("ready") }}',
        encoding="utf-8",
    )
    roots = (TemplateRoot("framework", framework), TemplateRoot("app", app))
    env = Environment(
        loader=PrefixLoader(
            {
                "framework": FileSystemLoader(framework),
                "app": FileSystemLoader(app),
            }
        ),
        bytecode_cache=False,
    )
    env.add_filter("shout", lambda value: str(value).upper())

    report = diagnose_roots(roots, environment=env)
    components = inspect_components(roots, environment=env)

    assert report.diagnostics == ()
    assert report.partial is False
    assert [record.metadata.name for record in components.components] == ["badge"]
    assert components.diagnostics == ()


def test_adapter_loader_cannot_silently_change_root_ownership(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    other = tmp_path / "other"
    expected.mkdir()
    other.mkdir()
    (expected / "component.html").write_text(
        "{% def expected() %}expected{% end %}",
        encoding="utf-8",
    )
    (other / "component.html").write_text(
        "{% def other() %}other{% end %}",
        encoding="utf-8",
    )
    roots = (TemplateRoot("app", expected),)
    wrong_env = Environment(
        loader=PrefixLoader({"app": FileSystemLoader(other)}),
        bytecode_cache=False,
    )

    report = diagnose_roots(roots, environment=wrong_env)
    components = inspect_components(roots, environment=wrong_env)

    assert report.partial is True
    assert [diagnostic.code for diagnostic in report.diagnostics] == ["K-TPL-005"]
    assert "loader resolved 'app/component.html'" in report.diagnostics[0].message
    assert components.partial is True
    assert components.components == ()
    assert [diagnostic.code for diagnostic in components.diagnostics] == ["K-TPL-005"]


@pytest.mark.parametrize("output_format", ["text", "json", "sarif"])
def test_check_multi_root_diagnostics_preserve_surface_facts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    output_format: str,
) -> None:
    framework, app = _write_roots(tmp_path, invalid_call=True)

    exit_code = main(
        [
            "check",
            *_root_args(framework, app),
            "--validate-calls",
            "--format",
            output_format,
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    if output_format == "text":
        assert captured.out == ""
        assert "app/page.html" in captured.err
        assert "K-CMP-001" in captured.err
        return

    assert captured.err == ""
    payload = json.loads(captured.out)
    if output_format == "json":
        diagnostic = payload["diagnostics"][0]
        assert diagnostic["code"] == "K-CMP-001"
        assert diagnostic["path"] == "app/page.html"
        assert diagnostic["metadata"]["owner"] == "app"
        assert diagnostic["metadata"]["source_path"] == str((app / "page.html").resolve())
    else:
        result = payload["runs"][0]["results"][0]
        assert result["ruleId"] == "K-CMP-001"
        assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == (
            "app/page.html"
        )
        metadata = result["properties"]["metadata"]
        assert metadata["owner"] == "app"
        assert metadata["source_path"] == str((app / "page.html").resolve())


def test_components_multi_root_json_includes_ownership(tmp_path: Path, capsys) -> None:
    framework, app = _write_roots(tmp_path)

    exit_code = main(["components", *_root_args(framework, app), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert captured.err == ""
    assert payload == [
        {
            "depends_on": [],
            "has_default_slot": False,
            "kwarg": None,
            "lineno": 1,
            "name": "card",
            "owner": "framework",
            "params": [
                {
                    "annotation": "str",
                    "has_default": False,
                    "name": "title",
                    "required": True,
                }
            ],
            "slots": [],
            "source_path": str((framework / "components.html").resolve()),
            "template": "framework/components.html",
            "vararg": None,
        }
    ]


@pytest.mark.parametrize("output_format", ["text", "json", "sarif"])
def test_missing_check_root_is_actionable_on_every_surface(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    output_format: str,
) -> None:
    missing = tmp_path / "missing"
    argv = [
        "check",
        "--root",
        f"missing={missing}",
        "--format",
        output_format,
    ]

    exit_code = main(argv)
    captured = capsys.readouterr()

    assert exit_code == 2
    if output_format == "text":
        assert "K-TPL-005" in captured.err
        assert str(missing.resolve()) in captured.err
        return
    payload = json.loads(captured.out)
    if output_format == "json":
        diagnostic = payload["diagnostics"][0]
        assert diagnostic["code"] == "K-TPL-005"
        assert diagnostic["metadata"] == {
            "owner": "missing",
            "source_path": str(missing.resolve()),
        }
        assert payload["partial"] is True
    else:
        result = payload["runs"][0]["results"][0]
        assert result["ruleId"] == "K-TPL-005"
        assert result["properties"]["metadata"] == {
            "owner": "missing",
            "source_path": str(missing.resolve()),
        }
        invocation = payload["runs"][0]["invocations"][0]
        assert invocation["executionSuccessful"] is False


def test_missing_component_root_is_actionable_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing"

    exit_code = main(["components", "--root", f"missing={missing}", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["diagnostics"][0]["code"] == "K-TPL-005"
    assert payload["diagnostics"][0]["metadata"]["owner"] == "missing"
    assert payload["partial"] is True


def test_duplicate_namespaces_are_rejected_without_first_wins(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "one.html").write_text("one", encoding="utf-8")
    (second / "two.html").write_text("two", encoding="utf-8")

    report = diagnose_roots(
        (
            TemplateRoot("app", first),
            TemplateRoot("app", second),
        )
    )

    assert report.partial is True
    assert len(report.diagnostics) == 1
    assert report.diagnostics[0].code == "K-TPL-005"
    assert "duplicate template root namespace 'app'" in report.diagnostics[0].message


@pytest.mark.parametrize("output_format", ["text", "json", "sarif"])
def test_duplicate_namespace_check_failure_has_surface_parity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    output_format: str,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    exit_code = main(
        [
            "check",
            "--root",
            f"app={first}",
            "--root",
            f"app={second}",
            "--format",
            output_format,
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    if output_format == "text":
        assert "K-TPL-005" in captured.err
        assert "duplicate template root namespace 'app'" in captured.err
    else:
        payload = json.loads(captured.out)
        if output_format == "json":
            assert payload["diagnostics"][0]["code"] == "K-TPL-005"
        else:
            assert payload["runs"][0]["results"][0]["ruleId"] == "K-TPL-005"


def test_component_inventory_order_is_independent_of_root_order(tmp_path: Path) -> None:
    framework, app = _write_roots(tmp_path)
    (app / "local.html").write_text(
        "{% def local() %}local{% end %}",
        encoding="utf-8",
    )

    forward = inspect_components((TemplateRoot("framework", framework), TemplateRoot("app", app)))
    reverse = inspect_components((TemplateRoot("app", app), TemplateRoot("framework", framework)))

    assert forward.components == reverse.components
    assert [record.template for record in forward.components] == [
        "app/local.html",
        "framework/components.html",
    ]


def test_duplicate_namespace_components_json_is_structured(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    exit_code = main(
        [
            "components",
            "--root",
            f"app={first}",
            "--root",
            f"app={second}",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["components"] == []
    assert payload["diagnostics"][0]["code"] == "K-TPL-005"
    assert payload["partial"] is True


def test_imported_malformed_definition_retains_owning_root(tmp_path: Path) -> None:
    framework = tmp_path / "framework"
    app = tmp_path / "app"
    framework.mkdir()
    app.mkdir()
    (framework / "components.html").write_text(
        "{% def broken( %}",
        encoding="utf-8",
    )
    (app / "page.html").write_text(
        '{% from "framework/components.html" import broken %}{{ broken() }}',
        encoding="utf-8",
    )
    roots = (TemplateRoot("framework", framework), TemplateRoot("app", app))

    report = diagnose_roots(roots)
    components = inspect_components(roots)

    assert report.partial is True
    assert len(report.diagnostics) == 1
    diagnostic = report.diagnostics[0]
    assert diagnostic.span.path == "framework/components.html"
    assert dict(diagnostic.metadata) == {
        "owner": "framework",
        "source_path": str((framework / "components.html").resolve()),
    }
    assert components.partial is True
    assert len(components.diagnostics) == 1
    assert components.diagnostics[0].span.path == "framework/components.html"


def test_cli_rejects_mixing_positional_and_namespaced_roots(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["check", str(tmp_path), "--root", f"app={tmp_path}"])

    assert exc_info.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
