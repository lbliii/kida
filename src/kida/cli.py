"""Command-line interface for Kida (``kida check``, future subcommands)."""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from kida.analysis.i18n import ExtractedMessage

from kida import Environment, FileSystemLoader
from kida.analysis.analyzer import BlockAnalyzer
from kida.exceptions import ErrorCode, TemplateSyntaxError
from kida.lexer import Lexer
from kida.parser import Parser


class _ComponentParamRow(TypedDict):
    name: str
    annotation: str | None
    required: bool


class _ComponentRow(TypedDict):
    name: str
    template: str
    lineno: int
    params: list[_ComponentParamRow]
    slots: list[str]
    has_default_slot: bool


_TEMPLATE_GLOBS = ("*.html", "*.kida")


def _iter_templates(root: Path) -> list[Path]:
    """Collect template files matching all known extensions, sorted."""
    seen: set[Path] = set()
    for glob in _TEMPLATE_GLOBS:
        for p in root.rglob(glob):
            seen.add(p)
    return sorted(seen)


def _explicit_close_suggestion(block_type: str) -> str:
    if block_type == "block":
        return "{% endblock %}"
    return f"{{% end{block_type} %}}"


def _cmd_check(
    template_dir: Path,
    *,
    strict: bool,
    validate_calls: bool,
    a11y: bool,
    typed: bool,
) -> int:
    """Parse every template under *template_dir*; exit non-zero on failure."""
    root = template_dir.resolve()
    if not root.is_dir():
        print(f"kida check: not a directory: {root}", file=sys.stderr)
        return 2

    env = Environment(loader=FileSystemLoader(str(root)), validate_calls=False)
    errors = 0
    strict_warnings = 0
    call_issues = 0
    failed_loads: set[str] = set()

    for path in _iter_templates(root):
        rel = path.relative_to(root).as_posix()
        try:
            tpl = env.get_template(rel)
        except Exception as e:
            print(f"{rel}: {e}", file=sys.stderr)
            errors += 1
            failed_loads.add(rel)
            continue

        if strict:
            try:
                source = path.read_text(encoding="utf-8")
                lexer = Lexer(source, env._lexer_config)
                tokens = list(lexer.tokenize())
                should_escape = env.select_autoescape(rel)
                sparser = Parser(
                    tokens,
                    name=rel,
                    filename=str(path),
                    source=source,
                    autoescape=should_escape,
                )
                sparser.parse()
            except OSError as e:
                print(f"{rel}: {e}", file=sys.stderr)
                errors += 1
                continue
            except TemplateSyntaxError as e:
                print(f"{rel}: {e}", file=sys.stderr)
                errors += 1
                continue
            for lineno, _col, closing in sparser._unified_end_closures:
                want = _explicit_close_suggestion(closing)
                print(
                    f"{rel}:{lineno}: strict: unified {{% end %}} closes "
                    f"'{closing}' — prefer {want}",
                    file=sys.stderr,
                )
                strict_warnings += 1

        if validate_calls and tpl._optimized_ast is not None:
            imported_defs = env._collect_imported_def_metadata(tpl._optimized_ast, rel)
            for issue in BlockAnalyzer().validate_calls_with_external_defs(
                tpl._optimized_ast,
                imported_defs,
            ):
                parts: list[str] = []
                if issue.unknown_params:
                    parts.append(f"unknown params: {', '.join(issue.unknown_params)}")
                if issue.missing_required:
                    parts.append(f"missing required: {', '.join(issue.missing_required)}")
                if issue.duplicate_params:
                    parts.append(f"duplicate params: {', '.join(issue.duplicate_params)}")
                loc = f"{rel}:{issue.lineno}"
                msg = (
                    f"{loc}: {ErrorCode.COMPONENT_CALL_SIGNATURE.value}: "
                    f"Call to '{issue.def_name}' — {'; '.join(parts)}"
                )
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

    type_mismatches = 0
    if validate_calls:
        for path in sorted(root.rglob("*.html")):
            rel = path.relative_to(root).as_posix()
            if rel in failed_loads:
                continue
            try:
                tpl = env.get_template(rel)
            except Exception as e:
                print(f"{rel}: {e}", file=sys.stderr)
                errors += 1
                failed_loads.add(rel)
                continue
            if tpl._optimized_ast is not None:
                imported_defs = env._collect_imported_def_metadata(tpl._optimized_ast, rel)
                for mm in BlockAnalyzer().validate_call_types_with_external_defs(
                    tpl._optimized_ast,
                    imported_defs,
                ):
                    print(
                        f"{rel}:{mm.lineno}: {ErrorCode.COMPONENT_TYPE_MISMATCH.value}: "
                        f"type: {mm.def_name}() param '{mm.param_name}' "
                        f"expects {mm.expected}, got {mm.actual_type} ({mm.actual_value!r})",
                        file=sys.stderr,
                    )
                    type_mismatches += 1
        if type_mismatches:
            print(
                f"kida check: {type_mismatches} type mismatch(es) in call sites",
                file=sys.stderr,
            )
            errors += type_mismatches

    type_issues = 0
    if typed:
        from kida.analysis.type_checker import check_types

        for path in _iter_templates(root):
            rel = path.relative_to(root).as_posix()
            if rel in failed_loads:
                continue
            try:
                tpl = env.get_template(rel)
            except Exception as e:
                print(f"{rel}: {e}", file=sys.stderr)
                errors += 1
                failed_loads.add(rel)
                continue
            if tpl._optimized_ast is not None:
                issues = check_types(tpl._optimized_ast)
                for issue in issues:
                    sev = issue.severity.upper()
                    print(
                        f"{rel}:{issue.lineno}: type/{issue.rule} [{sev}]: {issue.message}",
                        file=sys.stderr,
                    )
                    type_issues += 1
        if type_issues:
            print(f"kida check: {type_issues} type issue(s)", file=sys.stderr)
            errors += type_issues

    a11y_issues = 0
    if a11y:
        from kida.analysis.a11y import check_a11y

        for path in _iter_templates(root):
            rel = path.relative_to(root).as_posix()
            if rel in failed_loads:
                continue
            try:
                tpl = env.get_template(rel)
            except Exception as e:
                print(f"{rel}: {e}", file=sys.stderr)
                errors += 1
                failed_loads.add(rel)
                continue
            if tpl._optimized_ast is not None:
                issues = check_a11y(tpl._optimized_ast)
                for issue in issues:
                    sev = issue.severity.upper()
                    print(
                        f"{rel}:{issue.lineno}: a11y/{issue.rule} [{sev}]: {issue.message}",
                        file=sys.stderr,
                    )
                    a11y_issues += 1
        if a11y_issues:
            print(f"kida check: {a11y_issues} accessibility issue(s)", file=sys.stderr)
            errors += a11y_issues

    if errors:
        print(f"kida check: {errors} problem(s)", file=sys.stderr)
        return 1
    return 0


def _format_pot(messages: list[ExtractedMessage], *, template_dir: Path | None = None) -> str:
    """Format extracted messages as a PO template (.pot) file."""
    from datetime import datetime

    lines: list[str] = []
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M%z")
    lines.append("# SOME DESCRIPTIVE TITLE.")
    lines.append("# Copyright (C) YEAR THE PACKAGE'S COPYRIGHT HOLDER")
    lines.append("# This file is distributed under the same license as the PACKAGE package.")
    lines.append("# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.")
    lines.append("#")
    lines.append('msgid ""')
    lines.append('msgstr ""')
    lines.append(f'"POT-Creation-Date: {now}\\n"')
    lines.append('"Content-Type: text/plain; charset=UTF-8\\n"')
    lines.append('"Content-Transfer-Encoding: 8bit\\n"')
    lines.append("")

    # Aggregate locations per unique message key
    from collections import OrderedDict

    locations: OrderedDict[str | tuple[str, str], list[str]] = OrderedDict()
    for msg in messages:
        key = msg.message
        filename = msg.filename
        if template_dir is not None:
            with contextlib.suppress(ValueError):
                filename = str(Path(filename).relative_to(template_dir))
        loc = f"{filename}:{msg.lineno}"
        locations.setdefault(key, []).append(loc)

    for key, locs in locations.items():
        # Location comments (one #: line per occurrence)
        lines.extend(f"#: {loc}" for loc in locs)

        if isinstance(key, tuple):
            singular, plural = key
            lines.append(f'msgid "{_pot_escape(singular)}"')
            lines.append(f'msgid_plural "{_pot_escape(plural)}"')
            lines.append('msgstr[0] ""')
            lines.append('msgstr[1] ""')
        else:
            lines.append(f'msgid "{_pot_escape(key)}"')
            lines.append('msgstr ""')
        lines.append("")

    return "\n".join(lines) + "\n"


def _pot_escape(s: str) -> str:
    """Escape a string for POT file output."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _cmd_extract(
    template_dir: Path,
    *,
    output: Path | None,
    extensions: list[str],
) -> int:
    """Extract translatable messages from templates under *template_dir*."""
    from kida.analysis.i18n import ExtractMessagesVisitor

    root = template_dir.resolve()
    if not root.is_dir():
        print(f"kida extract: not a directory: {root}", file=sys.stderr)
        return 2

    env = Environment(loader=FileSystemLoader(str(root)))
    all_messages: list[ExtractedMessage] = []

    for ext in extensions:
        for path in sorted(root.rglob(f"*{ext}")):
            rel = path.relative_to(root).as_posix()
            try:
                source = path.read_text(encoding="utf-8")
                lexer = Lexer(source, env._lexer_config)
                tokens = list(lexer.tokenize())
                should_escape = env.select_autoescape(rel)
                sparser = Parser(
                    tokens,
                    name=rel,
                    filename=str(path),
                    source=source,
                    autoescape=should_escape,
                )
                ast = sparser.parse()
                visitor = ExtractMessagesVisitor(filename=rel)
                all_messages.extend(visitor.extract(ast))
            except Exception as e:
                print(f"kida extract: {rel}: {e}", file=sys.stderr)
                continue

    pot_content = _format_pot(all_messages, template_dir=root)
    unique_count = len({m.message for m in all_messages})

    if output is not None:
        output.write_text(pot_content, encoding="utf-8")
        print(
            f"Extracted {unique_count} unique message(s) to {output}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(pot_content)

    return 0


def _cmd_fmt(
    paths: list[Path],
    *,
    indent: int,
    check_only: bool,
) -> int:
    """Format template files."""
    from kida.formatter import format_template

    changed = 0
    total = 0

    for path in paths:
        if path.is_dir():
            files = _iter_templates(path)
        elif path.is_file():
            files = [path]
        else:
            print(f"kida fmt: not found: {path}", file=sys.stderr)
            continue

        for file in files:
            total += 1
            try:
                source = file.read_text(encoding="utf-8")
                formatted = format_template(source, indent=indent)
                if source != formatted:
                    changed += 1
                    if check_only:
                        print(f"would reformat {file}")
                    else:
                        file.write_text(formatted, encoding="utf-8")
                        print(f"reformatted {file}")
            except Exception as e:
                print(f"kida fmt: {file}: {e}", file=sys.stderr)

    if check_only and changed:
        print(f"{changed} file(s) would be reformatted", file=sys.stderr)
        return 1
    if not check_only:
        unchanged = total - changed
        print(f"{changed} file(s) reformatted, {unchanged} already formatted.")
    return 0


def _ast_contains(node: object, cls: type) -> bool:
    """Check if a Kida AST tree contains any node of the given type."""
    from kida.nodes.base import Node

    if isinstance(node, cls):
        return True
    if isinstance(node, Node):
        for child in node.iter_child_nodes():
            if _ast_contains(child, cls):
                return True
    return False


def _print_explain(env: Environment, tpl: object) -> None:
    """Print which compile-time optimizations are active for this template."""
    import sys as _sys

    lines: list[str] = []
    lines.append("--- Compiler optimizations ---")

    # F-string coalescing
    if env.fstring_coalescing:
        lines.append(
            "  [on]  f-string coalescing — merges consecutive outputs into single f-string appends"
        )
    else:
        lines.append("  [off] f-string coalescing")

    # Dead code elimination (always on)
    lines.append("  [on]  dead code elimination — removes const-only dead branches")

    # Type-aware escaping (always on for HTML mode)
    if env.autoescape:
        lines.append("  [on]  type-aware escaping — skips HTML escape for int/float/bool")

    # Lazy LoopContext (always on when loop vars unused)
    lines.append("  [on]  lazy loop context — skips LoopContext when loop.* unused")

    # Partial evaluation
    # The CLI loads templates via get_template() which doesn't support
    # static_context — partial eval requires from_string(src, static_context={...}).
    # Report the capability rather than the current state.
    lines.append("  [off] partial evaluation (pass static_context to from_string() to enable)")
    lines.append("        ├─ with propagation — aliases static values through {% with %} blocks")
    lines.append("        ├─ match elimination — removes dead {% match %}/{% case %} branches")
    lines.append("        ├─ test folding — resolves is defined/is none/is odd at compile time")
    lines.append(
        "        ├─ sub-expression simplification — folds static operands in mixed expressions"
    )
    lines.append("        └─ filter constant folding — 67 pure filters available")

    # Component inlining
    if env.inline_components:
        lines.append("  [on]  component inlining — small defs with constant args expanded inline")
    else:
        lines.append("  [off] component inlining (enable with inline_components=True)")

    # Free-threading
    try:
        from kida.utils.workers import is_free_threading_enabled

        if is_free_threading_enabled():
            lines.append("  [on]  free-threading — GIL disabled, concurrent rendering available")
        else:
            lines.append("  [off] free-threading (GIL enabled)")
    except ImportError:
        lines.append("  [off] free-threading (detection unavailable)")

    # List comprehensions
    optimized_ast = getattr(tpl, "_optimized_ast", None)
    if optimized_ast is not None:
        from kida.nodes import ListComp

        if _ast_contains(optimized_ast, ListComp):
            lines.append("  [on]  list comprehensions — compiled to native Python listcomp")

    lines.append("------------------------------")
    _sys.stderr.write("\n".join(lines) + "\n\n")


def _cmd_render(
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
    """Render a single template to stdout."""
    import json

    template_path = template_path.resolve()
    if not template_path.is_file():
        print(f"kida render: not a file: {template_path}", file=sys.stderr)
        return 2

    # Build context from --data / --data-str
    context: dict[str, Any] = {}
    if data_file is not None:
        if data_format == "junit-xml":
            from kida.utils.junit_xml import junit_to_dict

            try:
                context = {**junit_to_dict(data_file)}
            except Exception as e:
                print(f"kida render: invalid JUnit XML in {data_file}: {e}", file=sys.stderr)
                return 2
        elif data_format == "sarif":
            from kida.utils.sarif import sarif_to_dict

            try:
                context = {**sarif_to_dict(data_file)}
            except Exception as e:
                print(f"kida render: invalid SARIF in {data_file}: {e}", file=sys.stderr)
                return 2
        elif data_format == "lcov":
            from kida.utils.lcov import lcov_to_dict

            try:
                context = lcov_to_dict(data_file)
            except Exception as e:
                print(f"kida render: invalid LCOV in {data_file}: {e}", file=sys.stderr)
                return 2
        else:
            try:
                context = json.loads(data_file.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"kida render: invalid JSON in {data_file}: {e}", file=sys.stderr)
                return 2
    elif data_str is not None:
        try:
            context = json.loads(data_str)
        except Exception as e:
            print(f"kida render: invalid JSON: {e}", file=sys.stderr)
            return 2

    # Merge --set key=value overrides
    for item in set_vars or []:
        if "=" not in item:
            print(f"kida render: --set requires KEY=VALUE, got: {item}", file=sys.stderr)
            return 2
        key, raw = item.split("=", 1)
        try:
            context[key] = json.loads(raw)
        except ValueError:
            context[key] = raw

    # Build environment
    template_dir = template_path.parent
    template_name = template_path.name

    if mode == "terminal":
        from kida.terminal import terminal_env

        term_kwargs: dict[str, object] = {
            "loader": FileSystemLoader(str(template_dir)),
        }
        if width is not None:
            term_kwargs["terminal_width"] = width
        if color is not None:
            term_kwargs["terminal_color"] = color

        env = terminal_env(**term_kwargs)
    elif mode == "markdown":
        from kida.markdown import markdown_env

        env = markdown_env(loader=FileSystemLoader(str(template_dir)))
    else:
        env = Environment(loader=FileSystemLoader(str(template_dir)))

    tpl = env.get_template(template_name)

    if explain:
        _print_explain(env, tpl)

    try:
        if stream:
            from kida.terminal.live import stream_to_terminal

            stream_to_terminal(tpl, context, delay=stream_delay)
        else:
            output = tpl.render(**context)
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
    except Exception as e:
        print(f"kida render: {e}", file=sys.stderr)
        return 1

    return 0


def _cmd_components(
    template_dir: Path,
    *,
    json_output: bool,
    filter_name: str | None,
) -> int:
    """List all ``{% def %}`` components across templates in *template_dir*."""
    import json as json_mod

    root = template_dir.resolve()
    if not root.is_dir():
        print(f"kida components: not a directory: {root}", file=sys.stderr)
        return 2

    env = Environment(loader=FileSystemLoader(str(root)), validate_calls=False)

    # Collect all def metadata across templates
    all_defs: list[_ComponentRow] = []
    for path in sorted(root.rglob("*.html")):
        rel = path.relative_to(root).as_posix()
        try:
            tpl = env.get_template(rel)
        except TemplateSyntaxError:
            continue

        meta = tpl.def_metadata()
        for dm in meta.values():
            if filter_name and filter_name.lower() not in dm.name.lower():
                continue
            all_defs.append(
                {
                    "name": dm.name,
                    "template": rel,
                    "lineno": dm.lineno,
                    "params": [
                        {
                            "name": p.name,
                            "annotation": p.annotation,
                            "required": p.is_required,
                        }
                        for p in dm.params
                    ],
                    "slots": list(dm.slots),
                    "has_default_slot": dm.has_default_slot,
                }
            )

    if not all_defs:
        if filter_name:
            print(f"No components matching '{filter_name}' found.", file=sys.stderr)
        else:
            print("No components found.", file=sys.stderr)
        return 0

    if json_output:
        print(json_mod.dumps(all_defs, indent=2))
        return 0

    # Human-readable output grouped by template
    from itertools import groupby

    use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    for template, defs in groupby(all_defs, key=lambda d: d["template"]):
        print(f"\033[1m{template}\033[0m" if use_color else template)
        for d in defs:
            # Build signature
            parts: list[str] = []
            for p in d["params"]:
                sig = p["name"]
                if p["annotation"]:
                    sig += f": {p['annotation']}"
                if not p["required"]:
                    sig += " = ..."
                parts.append(sig)
            sig_str = ", ".join(parts)
            print(f"  def {d['name']}({sig_str})")

            # Slots
            slots = list(d["slots"])
            if d["has_default_slot"]:
                slots.insert(0, "(default)")
            if slots:
                print(f"    slots: {', '.join(slots)}")
        print()

    print(f"{len(all_defs)} component(s) found.")
    return 0


def _cmd_readme(
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

    from kida.readme.detect import detect_project

    root = root.resolve()
    if not root.is_dir():
        print(f"kida readme: not a directory: {root}", file=sys.stderr)
        return 2

    ctx = detect_project(root, depth=depth)

    # Auto-detect preset if not explicitly specified
    if preset is None:
        preset = ctx.get("suggested_preset", "default")

    # Apply --set overrides
    for item in set_vars or []:
        if "=" not in item:
            print(f"kida readme: --set requires KEY=VALUE, got: {item}", file=sys.stderr)
            return 2
        key, raw = item.split("=", 1)
        try:
            ctx[key] = json.loads(raw)
        except ValueError:
            ctx[key] = raw

    # --json mode: dump context and exit
    if dump_json:
        # tree is a nested dict, tree_str is the rendered string — both serialize fine
        print(json.dumps(ctx, indent=2, default=str))
        return 0

    # Render
    from kida.readme import render_readme

    try:
        md = render_readme(root, preset=preset, template=template, context=ctx, depth=depth)
    except Exception as e:
        print(f"kida readme: {e}", file=sys.stderr)
        return 1

    if output is not None:
        output.write_text(md, encoding="utf-8")
        print(f"Wrote {output}", file=sys.stderr)
    else:
        sys.stdout.write(md)
        if not md.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def _cmd_manifest(
    template_dir: Path,
    *,
    output: Path | None,
    data_file: Path | None,
    search: bool,
) -> int:
    """Render templates and output a capture manifest as JSON."""
    import json as json_mod

    from kida.render_capture import captured_render
    from kida.render_manifest import RenderManifest, SearchManifestBuilder

    root = template_dir.resolve()
    if not root.is_dir():
        print(f"kida manifest: not a directory: {root}", file=sys.stderr)
        return 2

    env = Environment(
        loader=FileSystemLoader(str(root)),
        enable_capture=True,
        strict_undefined=False,
    )

    # Load per-template context data if provided
    context_data: dict[str, dict[str, Any]] = {}
    if data_file is not None:
        context_data = json_mod.loads(data_file.read_text(encoding="utf-8"))

    manifest = RenderManifest()
    templates = _iter_templates(root)
    rendered = 0

    for path in templates:
        rel = path.relative_to(root).as_posix()
        try:
            tpl = env.get_template(rel)
        except Exception as e:
            print(f"kida manifest: skip {rel}: {e}", file=sys.stderr)
            continue

        ctx = context_data.get(rel, {})
        capture_ctx = frozenset(ctx.keys()) if ctx else None

        try:
            with captured_render(capture_context=capture_ctx) as cap:
                tpl.render(**ctx)
        except Exception as e:
            print(f"kida manifest: render error {rel}: {e}", file=sys.stderr)
            continue

        manifest.add(rel, cap)
        rendered += 1

    if search:
        result = SearchManifestBuilder().build(manifest)
    else:
        # Serialize manifest as JSON
        entries = []
        for url, cap in manifest.captures:
            entry: dict[str, Any] = {
                "url": url,
                "template": cap.template_name,
                "blocks": {
                    name: {
                        "role": frag.role,
                        "content_hash": frag.content_hash,
                        "depends_on": sorted(frag.depends_on),
                        "html_length": len(frag.html),
                    }
                    for name, frag in cap.blocks.items()
                },
            }
            if cap.context_keys:
                entry["context_keys"] = list(cap.context_keys.keys())
            entries.append(entry)
        result = {"version": manifest.version, "entries": entries}

    json_str = json_mod.dumps(result, indent=2, ensure_ascii=False)

    if output is not None:
        output.write_text(json_str + "\n", encoding="utf-8")
        print(f"kida manifest: {rendered} templates → {output}", file=sys.stderr)
    else:
        print(json_str)

    return 0


def _cmd_diff(old_path: Path, new_path: Path) -> int:
    """Semantic diff between two render manifests."""
    import json as json_mod

    if not old_path.exists():
        print(f"kida diff: not found: {old_path}", file=sys.stderr)
        return 2
    if not new_path.exists():
        print(f"kida diff: not found: {new_path}", file=sys.stderr)
        return 2

    old_data = json_mod.loads(old_path.read_text(encoding="utf-8"))
    new_data = json_mod.loads(new_path.read_text(encoding="utf-8"))

    old_entries = {e["url"]: e for e in old_data.get("entries", [])}
    new_entries = {e["url"]: e for e in new_data.get("entries", [])}

    added = [url for url in new_entries if url not in old_entries]
    removed = [url for url in old_entries if url not in new_entries]

    changed: dict[str, list[str]] = {}
    unchanged = 0

    for url in new_entries:
        if url not in old_entries:
            continue
        old_blocks = old_entries[url].get("blocks", {})
        new_blocks = new_entries[url].get("blocks", {})
        diffs = []
        all_block_names = set(old_blocks.keys()) | set(new_blocks.keys())
        for block_name in sorted(all_block_names):
            old_hash = old_blocks.get(block_name, {}).get("content_hash", "")
            new_hash = new_blocks.get(block_name, {}).get("content_hash", "")
            if old_hash != new_hash:
                old_role = old_blocks.get(block_name, {}).get("role", "?")
                new_role = new_blocks.get(block_name, {}).get("role", old_role)
                diffs.append(f"  {block_name} ({new_role}): {old_hash} → {new_hash}")
        if diffs:
            changed[url] = diffs
        else:
            unchanged += 1

    # Output
    if added:
        print(f"Added ({len(added)}):")
        for url in added:
            print(f"  + {url}")
    if removed:
        print(f"Removed ({len(removed)}):")
        for url in removed:
            print(f"  - {url}")
    if changed:
        print(f"Changed ({len(changed)}):")
        for url, diffs in sorted(changed.items()):
            print(f"  {url}:")
            for d in diffs:
                print(f"    {d}")
    if not added and not removed and not changed:
        print("No changes.")

    print(
        f"\nSummary: {len(added)} added, {len(removed)} removed, "
        f"{len(changed)} changed, {unchanged} unchanged"
    )

    return 1 if (added or removed or changed) else 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m kida`` / the ``kida`` console script."""
    parser = argparse.ArgumentParser(prog="kida", description="Kida template engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser(
        "check",
        help="Parse all templates under a directory (syntax + loader resolution)",
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
    p_check.add_argument(
        "--a11y",
        action="store_true",
        help="Check templates for accessibility issues (missing alt, heading order, etc.)",
    )
    p_check.add_argument(
        "--typed",
        action="store_true",
        help="Type-check templates against {%% template %%} declarations",
    )

    p_render = sub.add_parser(
        "render",
        help="Render a template to stdout",
    )
    p_render.add_argument(
        "template",
        type=Path,
        help="Path to the template file to render",
    )
    p_render.add_argument(
        "--data",
        type=Path,
        default=None,
        metavar="FILE",
        help="JSON file providing template context variables",
    )
    p_render.add_argument(
        "--data-str",
        type=str,
        default=None,
        metavar="JSON",
        help="Inline JSON string providing template context variables",
    )
    p_render.add_argument(
        "--mode",
        choices=["html", "terminal", "markdown"],
        default="html",
        help="Rendering mode (default: html)",
    )
    p_render.add_argument(
        "--width",
        type=int,
        default=None,
        help="Override terminal width (terminal mode only)",
    )
    p_render.add_argument(
        "--color",
        choices=["none", "basic", "256", "truecolor"],
        default=None,
        help="Override color depth (terminal mode only)",
    )
    p_render.add_argument(
        "--data-format",
        choices=["json", "junit-xml", "sarif", "lcov"],
        default="json",
        help="Format of the data file (default: json)",
    )
    p_render.add_argument(
        "--stream",
        action="store_true",
        help="Progressive output: reveal template chunks with a brief delay",
    )
    p_render.add_argument(
        "--stream-delay",
        type=float,
        default=0.02,
        metavar="SECONDS",
        help="Delay between stream chunks (default: 0.02s, requires --stream)",
    )
    p_render.add_argument(
        "--explain",
        action="store_true",
        help="Show which compile-time optimizations were applied",
    )
    p_render.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Set template variables (repeatable). Values are parsed as JSON if valid, "
        "otherwise kept as strings. Examples: --set count=42 (int), --set name=hello (string), "
        '--set items=\'["a","b"]\' (list). To force a string that looks like JSON: --set x=\'"42"\'.',
    )

    p_extract = sub.add_parser(
        "extract",
        help="Extract translatable messages from templates into a .pot file",
    )
    p_extract.add_argument(
        "template_dir",
        type=Path,
        help="Root directory to scan for templates",
    )
    p_extract.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write output to FILE instead of stdout",
    )
    p_extract.add_argument(
        "--ext",
        action="append",
        default=None,
        metavar=".EXT",
        help="File extensions to scan (default: .html .kida .txt .xml). Repeatable.",
    )

    p_readme = sub.add_parser(
        "readme",
        help="Generate a README from auto-detected project metadata",
    )
    p_readme.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(),
        help="Project root directory (default: current directory)",
    )
    p_readme.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write to file instead of stdout",
    )
    p_readme.add_argument(
        "--preset",
        choices=["default", "minimal", "library", "cli"],
        default=None,
        help="Built-in template preset (default: auto-detected from project type)",
    )
    p_readme.add_argument(
        "--template",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to a custom Kida template (overrides --preset)",
    )
    p_readme.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override detected values (value is parsed as JSON, falls back to string). Repeatable.",
    )
    p_readme.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Directory tree depth (default: 2)",
    )
    p_readme.add_argument(
        "--json",
        action="store_true",
        dest="dump_json",
        help="Dump auto-detected context as JSON instead of rendering",
    )

    p_components = sub.add_parser(
        "components",
        help="List all def components across templates",
    )
    p_components.add_argument(
        "template_dir",
        type=Path,
        help="Root directory passed to FileSystemLoader",
    )
    p_components.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON for machine consumption",
    )
    p_components.add_argument(
        "--filter",
        type=str,
        default=None,
        dest="filter_name",
        metavar="NAME",
        help="Filter components by name (case-insensitive substring match)",
    )

    p_manifest = sub.add_parser(
        "manifest",
        help="Render templates and output a capture manifest as JSON",
    )
    p_manifest.add_argument(
        "template_dir",
        type=Path,
        help="Root directory passed to FileSystemLoader",
    )
    p_manifest.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write manifest to FILE instead of stdout",
    )
    p_manifest.add_argument(
        "--data",
        type=Path,
        default=None,
        metavar="FILE",
        help="JSON file mapping template names to context dicts",
    )
    p_manifest.add_argument(
        "--search",
        action="store_true",
        help="Output a search manifest instead of a raw capture manifest",
    )

    p_diff = sub.add_parser(
        "diff",
        help="Semantic diff between two render manifests",
    )
    p_diff.add_argument(
        "old_manifest",
        type=Path,
        help="Path to the old manifest JSON file",
    )
    p_diff.add_argument(
        "new_manifest",
        type=Path,
        help="Path to the new manifest JSON file",
    )

    p_fmt = sub.add_parser(
        "fmt",
        help="Auto-format Kida template files",
    )
    p_fmt.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Files or directories to format",
    )
    p_fmt.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Spaces per indentation level (default: 2)",
    )
    p_fmt.add_argument(
        "--check",
        action="store_true",
        help="Check formatting without modifying files (exit 1 if changes needed)",
    )

    args = parser.parse_args(argv)
    if args.command == "check":
        return _cmd_check(
            args.template_dir,
            strict=args.strict,
            validate_calls=args.validate_calls,
            a11y=args.a11y,
            typed=args.typed,
        )
    if args.command == "render":
        return _cmd_render(
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
    if args.command == "extract":
        exts = args.ext or [".html", ".kida", ".txt", ".xml"]
        # Normalize: ensure each extension has a leading dot
        exts = [e if e.startswith(".") else f".{e}" for e in exts]
        return _cmd_extract(args.template_dir, output=args.output, extensions=exts)
    if args.command == "components":
        return _cmd_components(
            args.template_dir,
            json_output=args.json_output,
            filter_name=args.filter_name,
        )
    if args.command == "readme":
        return _cmd_readme(
            args.root,
            output=args.output,
            preset=args.preset,
            template=args.template,
            set_vars=args.set,
            depth=args.depth,
            dump_json=args.dump_json,
        )
    if args.command == "fmt":
        return _cmd_fmt(args.paths, indent=args.indent, check_only=args.check)
    if args.command == "manifest":
        return _cmd_manifest(
            args.template_dir,
            output=args.output,
            data_file=args.data,
            search=args.search,
        )
    if args.command == "diff":
        return _cmd_diff(args.old_manifest, args.new_manifest)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
