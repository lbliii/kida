"""Implementation of ``kida readme``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida._cli.common import write_stderr, write_stdout

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


def execute(
    root: Path,
    *,
    output: Path | None,
    preset: str | None,
    template: Path | None,
    set_vars: list[str] | None,
    depth: int,
    dump_json: bool,
) -> int:
    """Generate a README from auto-detected project metadata."""
    import json
    import sys

    from kida.readme.detect import detect_project

    root = root.resolve()
    if not root.is_dir():
        write_stderr(f"kida readme: not a directory: {root}")
        return 2

    context = detect_project(root, depth=depth)
    if preset is None:
        preset = context.get("suggested_preset", "default")
    for item in set_vars or []:
        if "=" not in item:
            write_stderr(f"kida readme: --set requires KEY=VALUE, got: {item}")
            return 2
        key, raw = item.split("=", 1)
        try:
            context[key] = json.loads(raw)
        except ValueError:
            context[key] = raw

    if dump_json:
        write_stdout(json.dumps(context, indent=2, default=str))
        return 0

    from kida.readme import render_readme

    try:
        markdown = render_readme(
            root,
            preset=preset,
            template=template,
            context=context,
            depth=depth,
        )
    except Exception as exc:
        write_stderr(f"kida readme: {exc}")
        return 1

    if output is not None:
        output.write_text(markdown, encoding="utf-8")
        write_stderr(f"Wrote {output}")
    else:
        sys.stdout.write(markdown)
        if not markdown.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def run(args: argparse.Namespace) -> int:
    """Adapt parsed arguments to README generation."""
    return execute(
        args.root,
        output=args.output,
        preset=args.preset,
        template=args.template,
        set_vars=args.set,
        depth=args.depth,
        dump_json=args.dump_json,
    )
