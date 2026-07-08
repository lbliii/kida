"""Implementation of ``kida extract``."""

from __future__ import annotations

import contextlib
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING

from kida._cli.common import write_stderr

if TYPE_CHECKING:
    import argparse

    from kida.analysis.i18n import ExtractedMessage


def format_pot(messages: list[ExtractedMessage], *, template_dir: Path | None = None) -> str:
    """Format extracted messages as a PO template file."""
    from collections import OrderedDict
    from datetime import datetime

    lines = [
        "# SOME DESCRIPTIVE TITLE.",
        "# Copyright (C) YEAR THE PACKAGE'S COPYRIGHT HOLDER",
        "# This file is distributed under the same license as the PACKAGE package.",
        "# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.",
        "#",
        'msgid ""',
        'msgstr ""',
        f'"POT-Creation-Date: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M%z")}\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        "",
    ]
    locations: OrderedDict[str | tuple[str, str], list[str]] = OrderedDict()
    for message in messages:
        filename = message.filename
        if template_dir is not None:
            with contextlib.suppress(ValueError):
                filename = str(Path(filename).relative_to(template_dir))
        locations.setdefault(message.message, []).append(f"{filename}:{message.lineno}")

    for key, message_locations in locations.items():
        lines.extend(f"#: {location}" for location in message_locations)
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


def _pot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def execute(template_dir: Path, *, output: Path | None, extensions: list[str]) -> int:
    """Extract translatable messages from templates below one directory."""
    import sys

    from kida import Environment, FileSystemLoader
    from kida.analysis.i18n import ExtractMessagesVisitor
    from kida.lexer import Lexer
    from kida.parser import Parser

    root = template_dir.resolve()
    if not root.is_dir():
        write_stderr(f"kida extract: not a directory: {root}")
        return 2

    env = Environment(loader=FileSystemLoader(str(root)))
    all_messages: list[ExtractedMessage] = []
    for extension in extensions:
        for path in sorted(root.rglob(f"*{extension}")):
            relative = path.relative_to(root).as_posix()
            try:
                source = path.read_text(encoding="utf-8")
                tokens = list(Lexer(source, env._lexer_config).tokenize())
                parser = Parser(
                    tokens,
                    name=relative,
                    filename=str(path),
                    source=source,
                    autoescape=env.select_autoescape(relative),
                )
                visitor = ExtractMessagesVisitor(filename=relative)
                all_messages.extend(visitor.extract(parser.parse()))
            except Exception as exc:
                write_stderr(f"kida extract: {relative}: {exc}")

    pot_content = format_pot(all_messages, template_dir=root)
    unique_count = len({message.message for message in all_messages})
    if output is not None:
        output.write_text(pot_content, encoding="utf-8")
        write_stderr(f"Extracted {unique_count} unique message(s) to {output}")
    else:
        sys.stdout.write(pot_content)
    return 0


def run(args: argparse.Namespace) -> int:
    """Normalize extensions and adapt parsed arguments to extraction."""
    extensions = args.ext or [".html", ".kida", ".txt", ".xml"]
    normalized = [item if item.startswith(".") else f".{item}" for item in extensions]
    return execute(args.template_dir, output=args.output, extensions=normalized)
