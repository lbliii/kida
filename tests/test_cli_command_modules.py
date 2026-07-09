"""Focused contracts for the command-owned CLI implementation."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kida._cli import check as check_command
from kida._cli import components as components_command
from kida._cli import diff as diff_command
from kida._cli import extract as extract_command
from kida._cli import fmt as fmt_command
from kida._cli import manifest as manifest_command
from kida._cli import readme as readme_command
from kida._cli import render as render_command
from kida._cli.parser import parse_args
from kida.cli import main


def test_public_facade_keeps_main_signature_and_identity() -> None:
    assert main.__module__ == "kida.cli"
    assert str(inspect.signature(main)) == "(argv: 'list[str] | None' = None) -> 'int'"


def test_importing_public_facade_does_not_load_parser_or_commands() -> None:
    code = """
import json
import sys
import kida.cli
tracked = [
    "kida._cli.bootstrap",
    "kida._cli.parser",
    "kida._cli.check",
    "kida._cli.render",
    "kida._cli.extract",
    "kida._cli.readme",
    "kida._cli.components",
    "kida._cli.manifest",
    "kida._cli.diff",
    "kida._cli.fmt",
    "kida._check",
    "kida._diagnostic_renderers",
    "kida.formatter",
    "kida.analysis.i18n",
]
print(json.dumps([name for name in tracked if name in sys.modules]))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []


def test_dispatch_loads_only_selected_command() -> None:
    code = """
import json
import sys
from kida.cli import main
status = main(["fmt", "/path/that/does/not/exist"])
tracked = [
    "kida._cli.check",
    "kida._cli.render",
    "kida._cli.extract",
    "kida._cli.readme",
    "kida._cli.components",
    "kida._cli.manifest",
    "kida._cli.diff",
    "kida._cli.fmt",
]
print(json.dumps({"status": status, "loaded": [name for name in tracked if name in sys.modules]}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout.splitlines()[-1])

    assert payload == {"status": 0, "loaded": ["kida._cli.fmt"]}
    assert "kida fmt: not found:" in result.stderr


def test_parser_returns_command_owned_arguments_without_loading_handler() -> None:
    args = parse_args(["render", "page.html", "--set", "count=2", "--stream"])

    assert args.command == "render"
    assert args.template == Path("page.html")
    assert args.set == ["count=2"]
    assert args.stream is True


def test_check_rejects_non_public_format_after_collection(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported check format: yaml"):
        check_command.execute(
            tmp_path,
            strict=False,
            validate_calls=False,
            a11y=False,
            typed=False,
            lint_fragile_paths=False,
            output_format="yaml",
        )


def test_extract_executor_owns_missing_root_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        extract_command.execute(
            tmp_path / "missing",
            output=None,
            extensions=[".html"],
        )
        == 2
    )
    assert "kida extract: not a directory:" in capsys.readouterr().err


def test_component_collection_and_presentation_are_independent(tmp_path: Path) -> None:
    (tmp_path / "card.html").write_text(
        "{% def card(title: str, *items, **attrs) %}"
        "{% slot header %}{{ title }}{{ site.name }}{% end %}",
        encoding="utf-8",
    )
    (tmp_path / "broken.html").write_text("{% if %}", encoding="utf-8")

    rows = components_command.collect_components(tmp_path, filter_name="CARD")
    rendered = components_command.render_text(rows, use_color=False)

    assert len(rows) == 1
    assert rows[0]["template"] == "card.html"
    assert rows[0]["slots"] == ["header"]
    assert "def card(title: str, *items, **attrs)" in rendered
    assert "slots: header" in rendered
    assert rendered.endswith("1 component(s) found.\n")


def test_component_text_renderer_preserves_color_boundary() -> None:
    rows: list[components_command.ComponentRow] = [
        {
            "name": "badge",
            "template": "ui.html",
            "lineno": 1,
            "params": [],
            "slots": [],
            "has_default_slot": False,
            "depends_on": [],
            "vararg": None,
            "kwarg": None,
        }
    ]

    assert components_command.render_text(rows, use_color=True).startswith(
        "\033[1mui.html\033[0m\n"
    )


def _manifest(*entries: dict[str, object]) -> dict[str, object]:
    return {"version": 1, "entries": list(entries)}


def test_diff_compare_and_render_cover_all_change_families() -> None:
    old = _manifest(
        {"url": "removed.html", "blocks": {}},
        {
            "url": "changed.html",
            "blocks": {"main": {"role": "main", "content_hash": "old"}},
        },
        {"url": "same.html", "blocks": {}},
    )
    new = _manifest(
        {
            "url": "changed.html",
            "blocks": {"main": {"role": "main", "content_hash": "new"}},
        },
        {"url": "same.html", "blocks": {}},
        {"url": "added.html", "blocks": {}},
    )

    result = diff_command.compare(old, new)
    rendered = diff_command.render_text(result)

    assert result.added == ("added.html",)
    assert result.removed == ("removed.html",)
    assert result.unchanged == 1
    assert "Changed (1):\n  changed.html:" in rendered
    assert "main (main): old → new" in rendered
    assert rendered.endswith("Summary: 1 added, 1 removed, 1 changed, 1 unchanged\n")


def test_diff_command_exit_and_missing_file_contracts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text(json.dumps(_manifest()), encoding="utf-8")
    new.write_text(json.dumps(_manifest()), encoding="utf-8")

    assert main(["diff", str(old), str(new)]) == 0
    assert "No changes." in capsys.readouterr().out
    assert main(["diff", str(tmp_path / "missing.json"), str(new)]) == 2
    assert "kida diff: not found:" in capsys.readouterr().err
    assert main(["diff", str(old), str(tmp_path / "missing-new.json")]) == 2
    assert "missing-new.json" in capsys.readouterr().err


def test_manifest_command_writes_capture_and_search_shapes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "page.html").write_text("<h1>Hello</h1>", encoding="utf-8")

    assert manifest_command.execute(tmp_path, output=None, data_file=None, search=False) == 0
    capture = json.loads(capsys.readouterr().out)
    assert capture["version"] == 1
    assert [entry["url"] for entry in capture["entries"]] == ["page.html"]

    assert manifest_command.execute(tmp_path, output=None, data_file=None, search=True) == 0
    search = json.loads(capsys.readouterr().out)
    assert search["version"] == 1


def test_manifest_output_and_failure_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "page.html").write_text("{{ title }}", encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text(json.dumps({"page.html": {"title": "Hello"}}), encoding="utf-8")
    output = tmp_path / "manifest.json"

    assert (
        manifest_command.execute(
            templates,
            output=output,
            data_file=data,
            search=False,
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["entries"][0]["url"] == "page.html"
    assert "1 templates" in capsys.readouterr().err
    assert (
        manifest_command.execute(
            tmp_path / "missing",
            output=None,
            data_file=None,
            search=False,
        )
        == 2
    )
    assert "not a directory" in capsys.readouterr().err
    assert main(["manifest", str(tmp_path / "missing")]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_manifest_continues_after_load_and_render_failures(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "broken.html").write_text("{% if %}", encoding="utf-8")
    (tmp_path / "explode.html").write_text("{{ 1 / 0 }}", encoding="utf-8")
    (tmp_path / "valid.html").write_text("valid", encoding="utf-8")

    assert manifest_command.execute(tmp_path, output=None, data_file=None, search=False) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert [entry["url"] for entry in payload["entries"]] == ["valid.html"]
    assert "kida manifest: skip broken.html:" in captured.err
    assert "kida manifest: render error explode.html:" in captured.err


def test_fmt_check_write_and_missing_path_contracts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    template = tmp_path / "page.html"
    template.write_text("{% if ok %}\nhello\n{% end %}\n", encoding="utf-8")

    assert fmt_command.execute([template], indent=2, check_only=True) == 1
    checked = capsys.readouterr()
    assert f"would reformat {template}" in checked.out
    assert "1 file(s) would be reformatted" in checked.err

    assert fmt_command.execute([template], indent=2, check_only=False) == 0
    formatted = capsys.readouterr()
    assert f"reformatted {template}" in formatted.out
    assert "1 file(s) reformatted, 0 already formatted." in formatted.out
    assert fmt_command.execute([tmp_path / "missing"], indent=2, check_only=False) == 0
    assert "kida fmt: not found:" in capsys.readouterr().err
    assert main(["fmt", str(tmp_path / "missing")]) == 0
    capsys.readouterr()

    invalid = tmp_path / "invalid.html"
    invalid.write_bytes(b"\xff")
    assert fmt_command.execute([invalid], indent=2, check_only=False) == 0
    assert "kida fmt:" in capsys.readouterr().err


def test_render_explain_and_invalid_set_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    template = tmp_path / "page.html"
    template.write_text("Hello {{ name }}", encoding="utf-8")

    assert (
        render_command.execute(
            template,
            data_file=None,
            data_str=None,
            data_format="json",
            width=None,
            color=None,
            mode="html",
            explain=True,
            set_vars=["name=Kida"],
        )
        == 0
    )
    rendered = capsys.readouterr()
    assert rendered.out == "Hello Kida\n"
    assert "--- Compiler optimizations ---" in rendered.err
    assert (
        render_command.execute(
            template,
            data_file=None,
            data_str=None,
            data_format="json",
            width=None,
            color=None,
            mode="html",
            set_vars=["invalid"],
        )
        == 2
    )
    assert "--set requires KEY=VALUE" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("data_format", "contents"),
    [
        ("junit-xml", '<testsuite name="empty" tests="0"/>'),
        ("sarif", '{"version":"2.1.0","runs":[]}'),
        ("lcov", "TN:\nSF:file.py\nDA:1,1\nend_of_record\n"),
    ],
)
def test_render_accepts_each_report_data_format(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    data_format: str,
    contents: str,
) -> None:
    template = tmp_path / "page.html"
    template.write_text("ok", encoding="utf-8")
    data = tmp_path / f"data.{data_format}"
    data.write_text(contents, encoding="utf-8")

    assert (
        render_command.execute(
            template,
            data_file=data,
            data_str=None,
            data_format=data_format,
            width=None,
            color=None,
            mode="html",
        )
        == 0
    )
    assert capsys.readouterr().out == "ok\n"


@pytest.mark.parametrize("mode", ["terminal", "markdown"])
def test_render_command_loads_non_html_surface_on_demand(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mode: str,
) -> None:
    template = tmp_path / "page.html"
    template.write_text("hello", encoding="utf-8")

    assert (
        render_command.execute(
            template,
            data_file=None,
            data_str=None,
            data_format="json",
            width=40,
            color=None,
            mode=mode,
        )
        == 0
    )
    assert capsys.readouterr().out == "hello\n"


def test_readme_command_failure_boundaries(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        readme_command.execute(
            tmp_path / "missing",
            output=None,
            preset=None,
            template=None,
            set_vars=None,
            depth=2,
            dump_json=False,
        )
        == 2
    )
    assert "not a directory" in capsys.readouterr().err
    assert (
        readme_command.execute(
            tmp_path,
            output=None,
            preset=None,
            template=None,
            set_vars=["invalid"],
            depth=2,
            dump_json=False,
        )
        == 2
    )
    assert "--set requires KEY=VALUE" in capsys.readouterr().err
    assert (
        readme_command.execute(
            tmp_path,
            output=None,
            preset=None,
            template=tmp_path / "missing.kida",
            set_vars=None,
            depth=2,
            dump_json=False,
        )
        == 1
    )
    assert "kida readme:" in capsys.readouterr().err
