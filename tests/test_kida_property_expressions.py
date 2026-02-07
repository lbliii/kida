"""Property-based tests for Kida expression evaluation.

Uses hypothesis to verify algebraic properties of the expression
evaluator that must hold for all values:

- Arithmetic identities (additive identity, multiplicative identity)
- Comparison symmetry (== is symmetric)
- Boolean tautologies (x or not x)
- Type coercion roundtrips (int -> string -> int)
- String case-conversion invariants
"""

from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from kida import Environment

from .strategies import ascii_lowercase_text, safe_integer

# Shared environment instance -- immutable, safe to reuse
_env = Environment()


def _render(template: str, **ctx: object) -> str:
    """Compile and render a one-shot template."""
    return _env.from_string(template).render(**ctx)


class TestExpressionProperties:
    """Algebraic properties of expression evaluation."""

    @given(x=safe_integer)
    @settings(max_examples=200)
    def test_additive_identity(self, x: int) -> None:
        """x + 0 == x for any integer."""
        result = _render("{{ x + 0 }}", x=x)
        assert result == str(x)

    @given(x=safe_integer)
    @settings(max_examples=200)
    def test_multiplicative_identity(self, x: int) -> None:
        """x * 1 == x for any integer."""
        result = _render("{{ x * 1 }}", x=x)
        assert result == str(x)

    @given(x=safe_integer)
    @settings(max_examples=200)
    def test_double_negation(self, x: int) -> None:
        """-(-x) == x for any integer."""
        # Use parenthesized sub-expressions
        result = _render("{{ -(-(x)) }}", x=x)
        assert result == str(x)

    @given(a=safe_integer, b=safe_integer)
    @settings(max_examples=200)
    def test_equality_symmetry(self, a: int, b: int) -> None:
        """(a == b) implies (b == a)."""
        r1 = _render("{{ a == b }}", a=a, b=b)
        r2 = _render("{{ b == a }}", a=a, b=b)
        assert r1 == r2

    @given(a=safe_integer, b=safe_integer)
    @settings(max_examples=200)
    def test_addition_commutativity(self, a: int, b: int) -> None:
        """a + b == b + a for any integers."""
        r1 = _render("{{ a + b }}", a=a, b=b)
        r2 = _render("{{ b + a }}", a=a, b=b)
        assert r1 == r2

    @given(x=st.booleans())
    @settings(max_examples=50)
    def test_boolean_tautology(self, x: bool) -> None:
        """x or not x is always True."""
        result = _render("{{ x or not x }}", x=x)
        assert result == "True"

    @given(x=st.integers(min_value=-9999, max_value=9999))
    @settings(max_examples=200)
    def test_int_string_roundtrip(self, x: int) -> None:
        """int(str(x)) == x -- type coercion roundtrip."""
        result = _render("{{ x | string | int }}", x=x)
        assert result == str(x)

    @given(s=ascii_lowercase_text)
    @settings(max_examples=200)
    def test_upper_lower_roundtrip(self, s: str) -> None:
        """upper then lower returns the original for ASCII lowercase."""
        result = _render("{{ s | upper | lower }}", s=s)
        assert result == s

    @given(x=safe_integer)
    @settings(max_examples=100)
    def test_zero_multiplication(self, x: int) -> None:
        """x * 0 == 0 for any integer."""
        result = _render("{{ x * 0 }}", x=x)
        assert result == "0"

    @given(a=safe_integer, b=st.integers(min_value=1, max_value=1000))
    @settings(max_examples=200)
    def test_division_consistency(self, a: int, b: int) -> None:
        """(a // b) * b + (a % b) == a (division algorithm)."""
        assume(b != 0)
        result = _render("{{ (a // b) * b + (a % b) }}", a=a, b=b)
        assert result == str(a)
