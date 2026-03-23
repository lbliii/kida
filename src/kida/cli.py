"""Command-line interface for Kida (``kida check``, future subcommands)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kida import Environment, FileSystemLoader
from kida.analysis.analyzer import BlockAnalyzer
from kida.lexer import Lexer
from kida.parser import Parser


def _explicit_close_suggestion(block_type: str) -> str:
    if block_type == "block":
        return "{% endblock %}"
    return f"{{% end{block_type} %}}"


def _cmd_check(
    template_dir: Path,
    *,
    strict: bool,
    validate_calls: bool,
) -> int:
    """Parse every ``*.html`` under *template_dir*; exit non-zero on failure."""
    root = template_dir.resolve()
    if not root.is_dir():
        print(f"kida check: not a directory: {root}", file=sys.stderr)
        return 2

    env = Environment(loader=FileSystemLoader(str(root)), validate_calls=False)
    errors = 0
    strict_warnings = 0
    call_issues = 0

    for path in sorted(root.rglob("*.html")):
        rel = path.relative_to(root).as_posix()
        try:
            tpl = env.get_template(rel)
        except Exception as e:
            print(f"{rel}: {e}", file=sys.stderr)
            errors += 1
            continue

        if strict:
            source = path.read_text(encoding="utf-8")
            lexer = Lexer(source, env._lexer_config)
            tokens = list(lexer.tokenize())
            should_escape = env.autoescape(rel) if callable(env.autoescape) else env.autoescape
            sparser = Parser(
                tokens,
                name=rel,
                filename=str(path),
                source=source,
                autoescape=should_escape,
            )
            sparser.parse()
            for lineno, _col, closing in sparser._unified_end_closures:
                want = _explicit_close_suggestion(closing)
                print(
                    f"{rel}:{lineno}: strict: unified {{% end %}} closes "
                    f"'{closing}' — prefer {want}",
                    file=sys.stderr,
                )
                strict_warnings += 1

        if validate_calls and tpl._optimized_ast is not None:
            for issue in BlockAnalyzer().validate_calls(tpl._optimized_ast):
                parts: list[str] = []
                if issue.unknown_params:
                    parts.append(f"unknown params: {', '.join(issue.unknown_params)}")
                if issue.missing_required:
                    parts.append(f"missing required: {', '.join(issue.missing_required)}")
                if issue.duplicate_params:
                    parts.append(f"duplicate params: {', '.join(issue.duplicate_params)}")
                loc = f"{rel}:{issue.lineno}"
                msg = f"Call to '{issue.def_name}' at {loc} — {'; '.join(parts)}"
                print(msg, file=sys.stderr)
                call_issues += 1

    if strict and strict_warnings:
        print(
            f"kida check: strict: {strict_warnings} unified {{% end %}} tag(s)",
            file=sys.stderr,
        )
        errors += strict_warnings

    if validate_calls and call_issues:
        print(f"kida check: {call_issues} call-site issue(s)", file=sys.stderr)
        errors += call_issues

    if errors:
        print(f"kida check: {errors} problem(s)", file=sys.stderr)
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
    p_check.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Fail if bare 'end' closers are used instead of explicit endif / endcall / endblock / …"
        ),
    )
    p_check.add_argument(
        "--validate-calls",
        action="store_true",
        help="Validate macro call sites against def signatures in each template",
    )

    args = parser.parse_args(argv)
    if args.command == "check":
        return _cmd_check(
            args.template_dir,
            strict=args.strict,
            validate_calls=args.validate_calls,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
