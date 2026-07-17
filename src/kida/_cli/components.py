"""Implementation of ``kida components``."""

from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING, NotRequired, TypedDict

from kida._cli.common import write_stderr, write_stdout

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

    from kida.inspection import ComponentRecord, TemplateRoot


class ComponentParamRow(TypedDict):
    name: str
    annotation: str | None
    has_default: bool
    required: bool


class ComponentRow(TypedDict):
    name: str
    template: str
    lineno: int
    params: list[ComponentParamRow]
    slots: list[str]
    has_default_slot: bool
    depends_on: list[str]
    vararg: str | None
    kwarg: str | None
    owner: NotRequired[str]
    source_path: NotRequired[str]


def collect_components(root: Path, *, filter_name: str | None) -> list[ComponentRow]:
    """Collect stable component metadata independently of presentation."""
    from kida import Environment, FileSystemLoader
    from kida.exceptions import TemplateSyntaxError

    env = Environment(loader=FileSystemLoader(str(root)), validate_calls=False)
    rows: list[ComponentRow] = []
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root).as_posix()
        try:
            template = env.get_template(relative)
        except TemplateSyntaxError:
            continue
        for metadata in template.def_metadata().values():
            if filter_name and filter_name.lower() not in metadata.name.lower():
                continue
            params: list[ComponentParamRow] = [
                {
                    "name": param.name,
                    "annotation": param.annotation,
                    "has_default": param.has_default,
                    "required": param.is_required,
                }
                for param in metadata.params
            ]
            rows.append(
                {
                    "name": metadata.name,
                    "template": relative,
                    "lineno": metadata.lineno,
                    "params": params,
                    "slots": list(metadata.slots),
                    "has_default_slot": metadata.has_default_slot,
                    "depends_on": sorted(metadata.depends_on),
                    "vararg": metadata.vararg,
                    "kwarg": metadata.kwarg,
                }
            )
    return rows


def _record_to_row(record: ComponentRecord) -> ComponentRow:
    metadata = record.metadata
    return {
        "name": metadata.name,
        "template": record.template,
        "lineno": metadata.lineno,
        "params": [
            {
                "name": param.name,
                "annotation": param.annotation,
                "has_default": param.has_default,
                "required": param.is_required,
            }
            for param in metadata.params
        ],
        "slots": list(metadata.slots),
        "has_default_slot": metadata.has_default_slot,
        "depends_on": sorted(metadata.depends_on),
        "vararg": metadata.vararg,
        "kwarg": metadata.kwarg,
        "owner": record.owner,
        "source_path": record.source_path,
    }


def render_text(rows: list[ComponentRow], *, use_color: bool) -> str:
    """Render component metadata using the existing human output contract."""
    lines: list[str] = []
    for template, definitions in groupby(rows, key=lambda row: row["template"]):
        lines.append(f"\033[1m{template}\033[0m" if use_color else template)
        for definition in definitions:
            parts: list[str] = []
            for param in definition["params"]:
                signature = param["name"]
                if param["annotation"]:
                    signature += f": {param['annotation']}"
                if not param["required"]:
                    signature += " = ..."
                parts.append(signature)
            if definition["vararg"]:
                parts.append(f"*{definition['vararg']}")
            if definition["kwarg"]:
                parts.append(f"**{definition['kwarg']}")
            lines.append(f"  def {definition['name']}({', '.join(parts)})")

            slots = list(definition["slots"])
            if definition["has_default_slot"]:
                slots.insert(0, "(default)")
            if slots:
                lines.append(f"    slots: {', '.join(slots)}")
            if definition["depends_on"]:
                lines.append(f"    depends_on: {', '.join(definition['depends_on'])}")
        lines.append("")
    lines.append(f"{len(rows)} component(s) found.")
    return "\n".join(lines) + "\n"


def execute(
    template_dir: Path | None,
    *,
    template_roots: tuple[TemplateRoot, ...] = (),
    json_output: bool,
    filter_name: str | None,
) -> int:
    """List components below one directory or explicit namespaced roots."""
    import json
    import os
    import sys

    diagnostics = ()
    partial = False
    if template_roots:
        from kida.inspection import inspect_components

        inspection = inspect_components(template_roots, filter_name=filter_name)
        rows = [_record_to_row(record) for record in inspection.components]
        diagnostics = inspection.diagnostics
        partial = inspection.partial
    else:
        if template_dir is None:
            write_stderr("kida components: provide TEMPLATE_DIR or at least one --root")
            return 2
        root = template_dir.resolve()
        if not root.is_dir():
            write_stderr(f"kida components: not a directory: {root}")
            return 2
        rows = collect_components(root, filter_name=filter_name)

    if diagnostics:
        if json_output:
            from kida._diagnostic_renderers import diagnostic_to_dict

            write_stdout(
                json.dumps(
                    {
                        "components": rows,
                        "diagnostics": [diagnostic_to_dict(item) for item in diagnostics],
                        "partial": partial,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            for diagnostic in diagnostics:
                write_stderr(f"kida components: {diagnostic.code}: {diagnostic.message}")
        return 2 if any(diagnostic.code == "K-TPL-005" for diagnostic in diagnostics) else 1
    if not rows:
        if filter_name:
            write_stderr(f"No components matching '{filter_name}' found.")
        else:
            write_stderr("No components found.")
        return 0
    if json_output:
        write_stdout(json.dumps(rows, indent=2))
        return 0

    use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    write_stdout(render_text(rows, use_color=use_color), end="")
    return 0


def run(args: argparse.Namespace) -> int:
    """Adapt parsed arguments to component collection."""
    import argparse

    from kida._cli.roots import parse_template_root

    try:
        roots = tuple(parse_template_root(value) for value in args.template_roots)
    except argparse.ArgumentTypeError as exc:
        write_stderr(f"kida components: {exc}")
        return 2
    return execute(
        args.template_dir,
        template_roots=roots,
        json_output=args.json_output,
        filter_name=args.filter_name,
    )
