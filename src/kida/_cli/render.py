"""Implementation of ``kida render``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kida._cli.common import write_stderr

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

    from kida import Environment


def _ast_contains(node: object, cls: type) -> bool:
    from kida.nodes.base import Node

    if isinstance(node, cls):
        return True
    if isinstance(node, Node):
        return any(_ast_contains(child, cls) for child in node.iter_child_nodes())
    return False


def render_explanation(env: Environment, template: object) -> str:
    """Render the established compile-time optimization explanation."""
    lines = ["--- Compiler optimizations ---"]
    if env.fstring_coalescing:
        lines.append(
            "  [on]  f-string coalescing — merges consecutive outputs into single f-string appends"
        )
    else:
        lines.append("  [off] f-string coalescing")
    lines.append("  [on]  dead code elimination — removes const-only dead branches")
    if env.autoescape:
        lines.append("  [on]  type-aware escaping — skips HTML escape for int/float/bool")
    lines.append("  [on]  lazy loop context — skips LoopContext when loop.* unused")
    lines.append("  [off] partial evaluation (pass static_context to from_string() to enable)")
    lines.append("        ├─ with propagation — aliases static values through {% with %} blocks")
    lines.append("        ├─ match elimination — removes dead {% match %}/{% case %} branches")
    lines.append("        ├─ test folding — resolves is defined/is none/is odd at compile time")
    lines.append(
        "        ├─ sub-expression simplification — folds static operands in mixed expressions"
    )
    lines.append("        └─ filter constant folding — 67 pure filters available")
    if env.inline_components:
        lines.append("  [on]  component inlining — small defs with constant args expanded inline")
    else:
        lines.append("  [off] component inlining (enable with inline_components=True)")

    try:
        from kida.utils.workers import is_free_threading_enabled

        if is_free_threading_enabled():
            lines.append("  [on]  free-threading — GIL disabled, concurrent rendering available")
        else:
            lines.append("  [off] free-threading (GIL enabled)")
    except ImportError:
        lines.append("  [off] free-threading (detection unavailable)")

    optimized_ast = getattr(template, "_optimized_ast", None)
    if optimized_ast is not None:
        from kida.nodes import ListComp

        if _ast_contains(optimized_ast, ListComp):
            lines.append("  [on]  list comprehensions — compiled to native Python listcomp")
    lines.append("------------------------------")
    return "\n".join(lines) + "\n\n"


def _coerce_json_context(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {"data": value}


def execute(
    template_path: Path,
    *,
    data_file: Path | None,
    data_str: str | None,
    data_format: str,
    width: int | None,
    color: str | None,
    mode: str,
    stream: bool = False,
    stream_delay: float = 0.02,
    explain: bool = False,
    set_vars: list[str] | None = None,
) -> int:
    """Render a single template to standard output."""
    import json
    import sys

    from kida import Environment, FileSystemLoader

    template_path = template_path.resolve()
    if not template_path.is_file():
        write_stderr(f"kida render: not a file: {template_path}")
        return 2

    context: dict[str, Any] = {}
    if data_file is not None:
        if data_format == "junit-xml":
            from kida.utils.junit_xml import junit_to_dict

            try:
                context = {**junit_to_dict(data_file)}
            except Exception as exc:
                write_stderr(f"kida render: invalid JUnit XML in {data_file}: {exc}")
                return 2
        elif data_format == "sarif":
            from kida.utils.sarif import sarif_to_dict

            try:
                context = {**sarif_to_dict(data_file)}
            except Exception as exc:
                write_stderr(f"kida render: invalid SARIF in {data_file}: {exc}")
                return 2
        elif data_format == "lcov":
            from kida.utils.lcov import lcov_to_dict

            try:
                context = lcov_to_dict(data_file)
            except Exception as exc:
                write_stderr(f"kida render: invalid LCOV in {data_file}: {exc}")
                return 2
        else:
            try:
                context = _coerce_json_context(json.loads(data_file.read_text(encoding="utf-8")))
            except Exception as exc:
                write_stderr(f"kida render: invalid JSON in {data_file}: {exc}")
                return 2
    elif data_str is not None:
        try:
            context = _coerce_json_context(json.loads(data_str))
        except Exception as exc:
            write_stderr(f"kida render: invalid JSON: {exc}")
            return 2

    for item in set_vars or []:
        if "=" not in item:
            write_stderr(f"kida render: --set requires KEY=VALUE, got: {item}")
            return 2
        key, raw = item.split("=", 1)
        try:
            context[key] = json.loads(raw)
        except ValueError:
            context[key] = raw

    template_dir = template_path.parent
    template_name = template_path.name
    if mode == "terminal":
        from kida.terminal import terminal_env

        terminal_options: dict[str, object] = {
            "loader": FileSystemLoader(str(template_dir)),
        }
        if width is not None:
            terminal_options["terminal_width"] = width
        if color is not None:
            terminal_options["terminal_color"] = color
        env = terminal_env(**terminal_options)
    elif mode == "markdown":
        from kida.markdown import markdown_env

        env = markdown_env(loader=FileSystemLoader(str(template_dir)))
    else:
        env = Environment(loader=FileSystemLoader(str(template_dir)))

    template = env.get_template(template_name)
    if explain:
        sys.stderr.write(render_explanation(env, template))
    try:
        if stream:
            from kida.terminal.live import stream_to_terminal

            stream_to_terminal(template, context, delay=stream_delay)
        else:
            output = template.render(**context)
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
    except Exception as exc:
        write_stderr(f"kida render: {exc}")
        return 1
    return 0


def run(args: argparse.Namespace) -> int:
    """Adapt parsed arguments to template rendering."""
    return execute(
        args.template,
        data_file=args.data,
        data_str=args.data_str,
        data_format=args.data_format,
        width=args.width,
        color=args.color,
        mode=args.mode,
        stream=args.stream,
        stream_delay=args.stream_delay,
        explain=args.explain,
        set_vars=args.set,
    )
