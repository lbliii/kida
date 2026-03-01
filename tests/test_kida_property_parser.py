"""Property-based tests for the Kida parser.

Verifies that parse(tokenize(source)) either produces valid AST or raises
a clean, expected error — never crashes with unhandled exceptions.
"""

from __future__ import annotations

import contextlib

from hypothesis import given, settings

from kida.environment.exceptions import TemplateSyntaxError
from kida.lexer import LexerError, tokenize
from kida.parser import ParseError, Parser

from .strategies import arbitrary_template_source, parser_fuzz_source


class TestParserProperties:
    """Property-based parser invariants."""

    @given(source=arbitrary_template_source)
    @settings(max_examples=300)
    def test_parse_tokenize_never_crashes(self, source: str) -> None:
        """parse(tokenize(source)) never raises unhandled exception.

        May raise TemplateSyntaxError, ParseError, or LexerError.
        Must not raise TypeError, ValueError, IndexError, RecursionError, etc.
        """
        with contextlib.suppress(TemplateSyntaxError, LexerError):
            tokens = tokenize(source)
            parser = Parser(tokens, name="<property-test>", source=source)
            with contextlib.suppress(ParseError):
                parser.parse()

    @given(source=parser_fuzz_source)
    @settings(max_examples=200)
    def test_parser_fuzz_no_unhandled(self, source: str) -> None:
        """Larger fuzz: parse(tokenize(source)) never crashes."""
        with contextlib.suppress(TemplateSyntaxError, LexerError):
            tokens = tokenize(source)
            parser = Parser(tokens, name="<fuzz>", source=source)
            with contextlib.suppress(ParseError):
                parser.parse()
