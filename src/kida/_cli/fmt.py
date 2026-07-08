"""Implementation of ``kida fmt``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida._cli.common import iter_templates, write_stderr, write_stdout

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


def execute(paths: list[Path], *, indent: int, check_only: bool) -> int:
    """Format template files and preserve the established status contract."""
    from kida.formatter import format_template

    changed = 0
    total = 0
    for path in paths:
        if path.is_dir():
            files = iter_templates(path)
        elif path.is_file():
            files = [path]
        else:
            write_stderr(f"kida fmt: not found: {path}")
            continue

        for file in files:
            total += 1
            try:
                source = file.read_text(encoding="utf-8")
                formatted = format_template(source, indent=indent)
                if source != formatted:
                    changed += 1
                    if check_only:
                        write_stdout(f"would reformat {file}")
                    else:
                        file.write_text(formatted, encoding="utf-8")
                        write_stdout(f"reformatted {file}")
            except Exception as exc:
                write_stderr(f"kida fmt: {file}: {exc}")

    if check_only and changed:
        write_stderr(f"{changed} file(s) would be reformatted")
        return 1
    if not check_only:
        unchanged = total - changed
        write_stdout(f"{changed} file(s) reformatted, {unchanged} already formatted.")
    return 0


def run(args: argparse.Namespace) -> int:
    """Adapt parsed arguments to the formatter executor."""
    return execute(args.paths, indent=args.indent, check_only=args.check)
