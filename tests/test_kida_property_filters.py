"""Property-based tests for Kida built-in filters.

Uses hypothesis to verify filter composition invariants that must hold
for all inputs:

- Idempotence (trim of trim == trim)
- Length consistency (length filter matches Python len)
- Sort correctness (sort filter produces sorted output)
- Default absorption (defined value ignores default)
- Chain associativity (chained filters == sequential application)
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from kida import Environment

from .strategies import ascii_lowercase_text, sortable_int_list

_env = Environment()


def _render(template: str, **ctx: object) -> str:
    """Compile and render a one-shot template."""
    return _env.from_string(template).render(**ctx)


class TestFilterProperties:
    """Algebraic properties of built-in filters."""

    @given(s=st.text(min_size=0, max_size=100))
    @settings(max_examples=200)
    def test_trim_idempotence(self, s: str) -> None:
        """trim(trim(s)) == trim(s) -- trimming is idempotent."""
        once = _render("{{ s | trim }}", s=s)
        twice = _render("{{ s | trim | trim }}", s=s)
        assert once == twice

    @given(s=st.text(min_size=0, max_size=100))
    @settings(max_examples=200)
    def test_upper_idempotence(self, s: str) -> None:
        """upper(upper(s)) == upper(s) -- upper is idempotent."""
        once = _render("{{ s | upper }}", s=s)
        twice = _render("{{ s | upper | upper }}", s=s)
        assert once == twice

    @given(items=st.lists(st.integers(min_value=-100, max_value=100), max_size=20))
    @settings(max_examples=200)
    def test_length_consistency(self, items: list[int]) -> None:
        """length filter matches Python len()."""
        result = _render("{{ items | length }}", items=items)
        assert result == str(len(items))

    @given(items=sortable_int_list)
    @settings(max_examples=200)
    def test_sort_correctness(self, items: list[int]) -> None:
        """sort filter produces a sorted list."""
        result = _render(
            "{% for x in items | sort %}{{ x }},{% endfor %}",
            items=items,
        )
        if not items:
            assert result == ""
        else:
            values = [int(v) for v in result.rstrip(",").split(",")]
            assert values == sorted(items)

    @given(items=sortable_int_list)
    @settings(max_examples=200)
    def test_reverse_involution(self, items: list[int]) -> None:
        """reverse(reverse(items)) == items -- double reversal is identity."""
        original = _render(
            "{% for x in items %}{{ x }},{% endfor %}",
            items=items,
        )
        double_reversed = _render(
            "{% for x in items | reverse | reverse %}{{ x }},{% endfor %}",
            items=items,
        )
        assert original == double_reversed

    @given(x=st.integers(min_value=-10000, max_value=10000))
    @settings(max_examples=200)
    def test_default_absorption_when_defined(self, x: int) -> None:
        """default(fallback) returns the value when it is defined."""
        result = _render("{{ x | default('FALLBACK') }}", x=x)
        assert result == str(x)

    def test_default_activates_when_undefined(self) -> None:
        """default(fallback) returns the fallback when the value is undefined."""
        result = _render("{{ missing | default('FALLBACK') }}")
        assert result == "FALLBACK"

    @given(s=ascii_lowercase_text)
    @settings(max_examples=200)
    def test_title_preserves_words(self, s: str) -> None:
        """title filter preserves word count."""
        original_words = s.split()
        result = _render("{{ s | title }}", s=s)
        result_words = result.split()
        assert len(result_words) == len(original_words)

    @given(s=st.text(min_size=0, max_size=50))
    @settings(max_examples=200)
    def test_string_filter_idempotence(self, s: str) -> None:
        """string(string(s)) == string(s) -- already a string."""
        once = _render("{{ s | string }}", s=s)
        twice = _render("{{ s | string | string }}", s=s)
        assert once == twice

    @given(
        items=st.lists(
            st.integers(min_value=0, max_value=100),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=200)
    def test_first_last_in_list(self, items: list[int]) -> None:
        """first and last filters return endpoints of the list."""
        first = _render("{{ items | first }}", items=items)
        last = _render("{{ items | last }}", items=items)
        assert first == str(items[0])
        assert last == str(items[-1])
