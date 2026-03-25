"""Core parser implementation for Kida.

Combines all parsing mixins into a unified Parser class that transforms
a token stream into an immutable Kida AST (Template node).

Design:
The Parser uses mixin inheritance to separate concerns while maintaining
a single entry point. Each mixin handles one aspect of the grammar:

- `TokenNavigationMixin`: Token stream access, lookahead, expect/match
- `BlockParsingMixin`: Template structure (block, extends, include, def)
- `StatementParsingMixin`: Control flow (if, for, while), variables (set, let)
- `ExpressionParsingMixin`: Expressions, operators, filters, tests

Block Stack:
Uses a stack-based approach for unified `{% end %}` syntax. When any block
is opened, it's pushed onto the stack. `{% end %}` always closes the
innermost open block, like Go templates.

Thread-Safety:
Parser instances are single-use and not thread-safe. Create one parser
per template compilation. The resulting AST is immutable and thread-safe.

"""

from __future__ import annotations

from collections.abc import Sequence

from kida._types import Token, TokenType
from kida.nodes import Template, TemplateContext
from kida.parser.blocks import BlockParsingMixin
from kida.parser.expressions import ExpressionParsingMixin
from kida.parser.statements import StatementParsingMixin
from kida.parser.tokens import TokenNavigationMixin


class Parser(
    TokenNavigationMixin,
    BlockParsingMixin,
    StatementParsingMixin,
    ExpressionParsingMixin,
):
    """Recursive descent parser transforming tokens into Kida AST.

    The Parser consumes a token stream and produces an immutable Template node
    representing the complete AST. All parsing state is instance-local, so
    parsers are single-use (create one per template).

    Block Stack Architecture:
        Uses a stack to track open blocks, enabling Kida's unified `{% end %}`
        syntax. When `{% end %}` is encountered, it closes the innermost block:

            ```jinja
            {% if condition %}
                {% for item in items %}
                    {{ item }}
                {% end %}  {# closes for #}
            {% end %}  {# closes if #}
            ```

        The stack stores `(block_type, lineno, col)` tuples for error reporting.

    Attributes:
        _tokens: Sequence of Token objects from lexer
        _pos: Current position in token stream
        _name: Template name for error messages
        _filename: Source file path for error messages
        _source: Original source text for error context
        _autoescape: Whether to auto-escape output expressions
        _block_stack: Stack of open blocks for `{% end %}` matching

    Error Handling:
        Parse errors include source snippets with caret pointing to the error,
        plus contextual suggestions for common mistakes:

            ```
            ParseError: Unclosed 'for' block - missing closing tag
              --> template.html:3:0
               |
             3 | {% for item in items %}
               | ^
            Suggestion: Add '{% end %}' or '{% endfor %}' to close the block
            ```

    Example:
            >>> from kida.lexer import tokenize
            >>> tokens = tokenize("{% if x %}{{ x }}{% end %}")
            >>> parser = Parser(tokens, name="test.html")
            >>> ast = parser.parse()
            >>> ast.body[0]  # If node
        If(lineno=1, col_offset=0, test=Name(...), body=(...))

    """

    __slots__ = (
        "_autoescape",
        "_block_stack",
        "_end_keywords",
        "_extension_end_keywords",
        "_extension_tags",
        "_filename",
        "_name",
        "_pos",
        "_source",
        "_tokens",
        "_unified_end_closures",
    )

    def __init__(
        self,
        tokens: Sequence[Token],
        name: str | None = None,
        filename: str | None = None,
        source: str | None = None,
        autoescape: bool = True,
        extension_tags: dict | None = None,
    ):
        self._tokens = tokens
        self._pos = 0
        self._name = name
        self._filename = filename
        self._source = source
        self._autoescape = autoescape
        self._block_stack: list[tuple[str, int, int]] = []  # (block_type, lineno, col)
        # Populated when ``{% end %}`` closes a block (not ``{% endif %}`` / ``{% endcall %}``).
        self._unified_end_closures: list[tuple[int, int, str]] = []
        # Extension tag handlers: {tag_name: Extension instance}
        self._extension_tags: dict = extension_tags or {}
        # Instance-level end keywords (starts from class attribute, may be extended)
        self._end_keywords: frozenset[str] = self._END_KEYWORDS
        self._extension_end_keywords: frozenset[str] = frozenset()
        # Merge extension end keywords so _parse_body sees them
        if extension_tags:
            ext_end_kw: set[str] = set()
            for ext in extension_tags.values():
                ext_end_kw.update(ext.end_keywords)
            if ext_end_kw:
                self._end_keywords = self._end_keywords | ext_end_kw
                self._extension_end_keywords = frozenset(ext_end_kw)

    def parse(self) -> Template:
        """Parse tokens into Template AST."""
        body = self._parse_body()

        # Verify all blocks were closed
        if self._block_stack:
            # Report the first unclosed block
            block_type, lineno, _col = self._block_stack[0]
            raise self._error(
                f"Unclosed '{block_type}' block - missing closing tag",
                suggestion=f"Add '{{% end %}}' or '{{% end{block_type} %}}' to close the block opened at line {lineno}",
            )

        # Check for orphan end tags (end tags without matching opening block)
        # _parse_body() stops when it sees an end keyword, but if there are no
        # open blocks, that's an orphan end tag
        if self._current.type == TokenType.BLOCK_BEGIN:
            next_tok = self._peek(1)
            if next_tok.type == TokenType.NAME and next_tok.value in self._end_keywords:
                raise self._error(
                    f"Unexpected '{{% {next_tok.value} %}}' - no open block to close",
                    suggestion="Remove this tag or add a matching opening tag",
                )
            # Also check for orphan continuation keywords
            if next_tok.type == TokenType.NAME and next_tok.value in self._CONTINUATION_KEYWORDS:
                raise self._error(
                    f"Unexpected '{{% {next_tok.value} %}}' - not inside a matching block",
                    suggestion=f"'{next_tok.value}' can only appear inside an 'if' or 'for' block",
                )

        # Extract TemplateContext declaration if present
        context_type = None
        for node in body:
            if isinstance(node, TemplateContext):
                context_type = node
                break

        # Filter TemplateContext from body (it's metadata, not output)
        if context_type is not None:
            body = [n for n in body if not isinstance(n, TemplateContext)]

        return Template(
            lineno=1,
            col_offset=0,
            body=tuple(body),
            extends=None,
            context_type=context_type,
        )
