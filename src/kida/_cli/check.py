"""Implementation of ``kida check``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

    from kida.inspection import TemplateRoot

from kida._cli.common import write_stderr, write_stdout


def execute(
    template_dir: Path | None,
    *,
    template_roots: tuple[TemplateRoot, ...] = (),
    strict: bool,
    validate_calls: bool,
    a11y: bool,
    typed: bool,
    lint_fragile_paths: bool,
    output_format: str,
) -> int:
    """Collect diagnostics once and present the selected canonical surface."""
    from kida._diagnostic_renderers import (
        render_check_json,
        render_check_sarif,
        render_check_text,
    )

    if template_roots:
        from kida.diagnostics import DiagnosticOptions
        from kida.inspection import _collect_root_check_result

        result = _collect_root_check_result(
            template_roots,
            environment=None,
            options=DiagnosticOptions(
                strict=strict,
                validate_calls=validate_calls,
                a11y=a11y,
                typed=typed,
                lint_fragile_paths=lint_fragile_paths,
            ),
        )
    else:
        if template_dir is None:
            write_stderr("kida check: provide TEMPLATE_DIR or at least one --root")
            return 2
        from kida._check import collect_check_diagnostics

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
    import argparse

    from kida._cli.roots import parse_template_root

    try:
        roots = tuple(parse_template_root(value) for value in args.template_roots)
    except argparse.ArgumentTypeError as exc:
        write_stderr(f"kida check: {exc}")
        return 2
    return execute(
        args.template_dir,
        template_roots=roots,
        strict=args.strict,
        validate_calls=args.validate_calls,
        a11y=args.a11y,
        typed=args.typed,
        lint_fragile_paths=args.lint_fragile_paths,
        output_format=args.output_format,
    )
