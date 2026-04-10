"""Babel extraction plugin for Kida templates.

Usage in ``babel.cfg``::

    [kida: templates/**.html]
    encoding = utf-8

Requires the ``babel`` package to be installed. Registration is via
the ``babel.extractors`` entry point in ``pyproject.toml``.
"""

from __future__ import annotations

from typing import IO, Any


def extract(
    fileobj: IO[bytes],
    keywords: list[str],
    comment_tags: list[str],
    options: dict[str, Any],
) -> Any:
    """Babel extraction method for Kida templates.

    Yields ``(lineno, function, message, comments)`` tuples compatible
    with the Babel extraction interface.
    """
    from kida import Environment
    from kida.analysis.i18n import ExtractMessagesVisitor

    encoding = options.get("encoding", "utf-8")
    source = fileobj.read().decode(encoding)
    name = getattr(fileobj, "name", "<template>")

    env = Environment()
    from kida.lexer import Lexer
    from kida.parser import Parser

    lexer = Lexer(source, env._lexer_config)
    tokens = list(lexer.tokenize())
    parser = Parser(tokens, name, None, source)
    ast = parser.parse()

    visitor = ExtractMessagesVisitor(filename=name)
    messages = visitor.extract(ast)

    for msg in messages:
        yield (msg.lineno, msg.function, msg.message, list(msg.comments))
