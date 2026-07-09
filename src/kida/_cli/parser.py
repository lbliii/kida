"""Argument parsing for the public ``kida`` command."""

from __future__ import annotations

import argparse
from pathlib import Path


def _add_check(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "check",
        help="Parse all templates under a directory (syntax + loader resolution)",
    )
    parser.add_argument(
        "template_dir",
        type=Path,
        help="Root directory passed to FileSystemLoader",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Fail if bare 'end' closers are used instead of explicit endif / endcall / endblock / …"
        ),
    )
    parser.add_argument(
        "--validate-calls",
        action="store_true",
        help="Validate macro call sites against def signatures in each template",
    )
    parser.add_argument(
        "--a11y",
        action="store_true",
        help="Check templates for accessibility issues (missing alt, heading order, etc.)",
    )
    parser.add_argument(
        "--typed",
        action="store_true",
        help="Type-check templates against {%% template %%} declarations",
    )
    parser.add_argument(
        "--lint-fragile-paths",
        action="store_true",
        help=(
            "Suggest ./ relative paths for same-folder includes / extends / embeds / imports "
            "so folder moves stay zero-edit"
        ),
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "sarif"],
        default="text",
        dest="output_format",
        help="Diagnostic output format (default: text)",
    )


def _add_render(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("render", help="Render a template to stdout")
    parser.add_argument("template", type=Path, help="Path to the template file to render")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        metavar="FILE",
        help="JSON file providing template context variables",
    )
    parser.add_argument(
        "--data-str",
        type=str,
        default=None,
        metavar="JSON",
        help="Inline JSON string providing template context variables",
    )
    parser.add_argument(
        "--mode",
        choices=["html", "terminal", "markdown"],
        default="html",
        help="Rendering mode (default: html)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Override terminal width (terminal mode only)",
    )
    parser.add_argument(
        "--color",
        choices=["none", "basic", "256", "truecolor"],
        default=None,
        help="Override color depth (terminal mode only)",
    )
    parser.add_argument(
        "--data-format",
        choices=["json", "junit-xml", "sarif", "lcov"],
        default="json",
        help="Format of the data file (default: json)",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Progressive output: reveal template chunks with a brief delay",
    )
    parser.add_argument(
        "--stream-delay",
        type=float,
        default=0.02,
        metavar="SECONDS",
        help="Delay between stream chunks (default: 0.02s, requires --stream)",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show which compile-time optimizations were applied",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Set template variables (repeatable). Values are parsed as JSON if valid, "
        "otherwise kept as strings. Examples: --set count=42 (int), --set name=hello (string), "
        '--set items=\'["a","b"]\' (list). To force a string that looks like JSON: --set x=\'"42"\'.',
    )


def _add_extract(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "extract",
        help="Extract translatable messages from templates into a .pot file",
    )
    parser.add_argument(
        "template_dir",
        type=Path,
        help="Root directory to scan for templates",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write output to FILE instead of stdout",
    )
    parser.add_argument(
        "--ext",
        action="append",
        default=None,
        metavar=".EXT",
        help="File extensions to scan (default: .html .kida .txt .xml). Repeatable.",
    )


def _add_readme(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "readme",
        help="Generate a README from auto-detected project metadata",
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(),
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write to file instead of stdout",
    )
    parser.add_argument(
        "--preset",
        choices=["default", "minimal", "library", "cli"],
        default=None,
        help="Built-in template preset (default: auto-detected from project type)",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to a custom Kida template (overrides --preset)",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override detected values (value is parsed as JSON, falls back to string). Repeatable.",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Directory tree depth (default: 2)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="dump_json",
        help="Dump auto-detected context as JSON instead of rendering",
    )


def _add_components(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "components",
        help="List all def components across templates",
    )
    parser.add_argument(
        "template_dir",
        type=Path,
        help="Root directory passed to FileSystemLoader",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON for machine consumption",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        dest="filter_name",
        metavar="NAME",
        help="Filter components by name (case-insensitive substring match)",
    )


def _add_manifest(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "manifest",
        help="Render templates and output a capture manifest as JSON",
    )
    parser.add_argument(
        "template_dir",
        type=Path,
        help="Root directory passed to FileSystemLoader",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write manifest to FILE instead of stdout",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        metavar="FILE",
        help="JSON file mapping template names to context dicts",
    )
    parser.add_argument(
        "--search",
        action="store_true",
        help="Output a search manifest instead of a raw capture manifest",
    )


def _add_diff(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("diff", help="Semantic diff between two render manifests")
    parser.add_argument(
        "old_manifest",
        type=Path,
        help="Path to the old manifest JSON file",
    )
    parser.add_argument(
        "new_manifest",
        type=Path,
        help="Path to the new manifest JSON file",
    )


def _add_fmt(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("fmt", help="Auto-format Kida template files")
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Files or directories to format",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Spaces per indentation level (default: 2)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check formatting without modifying files (exit 1 if changes needed)",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the stable public command and flag tree."""
    parser = argparse.ArgumentParser(prog="kida", description="Kida template engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    for configure in (
        _add_check,
        _add_render,
        _add_extract,
        _add_readme,
        _add_components,
        _add_manifest,
        _add_diff,
        _add_fmt,
    ):
        configure(sub)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse public CLI arguments without importing any command implementation."""
    return build_parser().parse_args(argv)
