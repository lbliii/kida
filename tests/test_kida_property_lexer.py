"""Property-based tests for the Kida lexer.

Uses hypothesis to verify structural invariants that must hold for
*all* inputs, not just hand-picked examples:

- Plain text round-trips through tokenization unchanged
- Variable expressions produce balanced delimiter tokens
- Arbitrary input never causes an unhandled crash
- Well-formed fragments produce balanced delimiter pairs
"""

from __future__ import annotations

from hypothesis import given, settings

from kida._types import TokenType
from kida.environment.exceptions import TemplateSyntaxError
from kida.lexer import Lexer, LexerError, tokenize

from .strategies import (
    arbitrary_template_source,
    kida_variable,
    plain_text,
    template_fragment,
)

# Delimiter pairs for balance checking
_BEGIN_END_PAIRS = {
    TokenType.VARIABLE_BEGIN: TokenType.VARIABLE_END,
    TokenType.BLOCK_BEGIN: TokenType.BLOCK_END,
    TokenType.COMMENT_BEGIN: TokenType.COMMENT_END,
}


class TestLexerProperties:
    """Property-based lexer invariants."""

    @given(source=plain_text)
    @settings(max_examples=200)
    def test_plain_text_roundtrip(self, source: str) -> None:
        """Text without delimiters produces a single DATA token with the original content."""
        tokens = tokenize(source)
        # Filter out EOF
        data_tokens = [t for t in tokens if t.type == TokenType.DATA]
        reconstructed = "".join(t.value for t in data_tokens)
        assert reconstructed == source

    @given(source=kida_variable)
    @settings(max_examples=200)
    def test_variable_has_balanced_delimiters(self, source: str) -> None:
        """A {{ var }} expression produces VARIABLE_BEGIN and VARIABLE_END."""
        tokens = tokenize(source)
        types = [t.type for t in tokens]
        assert TokenType.VARIABLE_BEGIN in types
        assert TokenType.VARIABLE_END in types

    @given(source=arbitrary_template_source)
    @settings(max_examples=300)
    def test_no_unhandled_crash(self, source: str) -> None:
        """The lexer never raises an unexpected exception.

        It may raise TemplateSyntaxError or LexerError for invalid input,
        but must not raise TypeError, ValueError, IndexError, etc.
        """
        try:
            tokenize(source)
        except (TemplateSyntaxError, LexerError):
            pass  # Expected for malformed input

    @given(source=template_fragment)
    @settings(max_examples=200)
    def test_fragment_delimiter_balance(self, source: str) -> None:
        """Well-formed fragments produce balanced BEGIN/END delimiter pairs."""
        try:
            tokens = tokenize(source)
        except (TemplateSyntaxError, LexerError):
            return  # Fragment generation can occasionally produce edge cases

        types = [t.type for t in tokens]
        for begin, end in _BEGIN_END_PAIRS.items():
            assert types.count(begin) == types.count(end), (
                f"Unbalanced {begin.name}/{end.name}: "
                f"{types.count(begin)} vs {types.count(end)} in {source!r}"
            )

    @given(source=template_fragment)
    @settings(max_examples=200)
    def test_eof_always_last(self, source: str) -> None:
        """Token stream always ends with EOF."""
        try:
            tokens = tokenize(source)
        except (TemplateSyntaxError, LexerError):
            return
        assert tokens[-1].type == TokenType.EOF

    @given(source=kida_variable)
    @settings(max_examples=100)
    def test_variable_contains_name_token(self, source: str) -> None:
        """A {{ identifier }} expression contains at least one NAME token."""
        tokens = tokenize(source)
        types = [t.type for t in tokens]
        assert TokenType.NAME in types
