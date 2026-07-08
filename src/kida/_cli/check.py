"""Implementation of ``kida check``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

from kida._cli.common import write_stderr, write_stdout


def execute(
    template_dir: Path,
    *,
    strict: bool,
    validate_calls: bool,
    a11y: bool,
    typed: bool,
    lint_fragile_paths: bool,
    output_format: str,
) -> int:
    """Collect diagnostics once and present the selected canonical surface."""
    from kida._check import collect_check_diagnostics
    from kida._diagnostic_renderers import (
        render_check_json,
        render_check_sarif,
        render_check_text,
    )

    result = collect_check_diagnostics(
        template_dir,
        strict=strict,
        validate_calls=validate_calls,
        a11y=a11y,
        typed=typed,
        lint_fragile_paths=lint_fragile_paths,
    )
    match output_format:
        case "text":
            rendered = render_check_text(result)
            if rendered:
                write_stderr(rendered, end="")
        case "json":
            write_stdout(render_check_json(result), end="")
        case "sarif":
            write_stdout(render_check_sarif(result), end="")
        case _:
            raise ValueError(f"unsupported check format: {output_format}")
    return result.exit_code


def run(args: argparse.Namespace) -> int:
    """Adapt parsed arguments to the check executor."""
    return execute(
        args.template_dir,
        strict=args.strict,
        validate_calls=args.validate_calls,
        a11y=args.a11y,
        typed=args.typed,
        lint_fragile_paths=args.lint_fragile_paths,
        output_format=args.output_format,
    )
