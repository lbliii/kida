"""Command-line interface for Kida (``kida check``, future subcommands)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kida import Environment, FileSystemLoader


def _cmd_check(template_dir: Path) -> int:
    """Parse every ``*.html`` under *template_dir*; exit non-zero on failure."""
    root = template_dir.resolve()
    if not root.is_dir():
        print(f"kida check: not a directory: {root}", file=sys.stderr)
        return 2

    env = Environment(loader=FileSystemLoader(str(root)))
    errors = 0
    for path in sorted(root.rglob("*.html")):
        rel = path.relative_to(root).as_posix()
        try:
            env.get_template(rel)
        except Exception as e:
            print(f"{rel}: {e}", file=sys.stderr)
            errors += 1
    if errors:
        print(f"kida check: {errors} template(s) failed", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m kida`` / the ``kida`` console script."""
    parser = argparse.ArgumentParser(prog="kida", description="Kida template engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser(
        "check",
        help="Parse all .html templates under a directory (syntax + loader resolution)",
    )
    p_check.add_argument(
        "template_dir",
        type=Path,
        help="Root directory passed to FileSystemLoader",
    )

    args = parser.parse_args(argv)
    if args.command == "check":
        return _cmd_check(args.template_dir)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
