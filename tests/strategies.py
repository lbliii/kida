"""Shared hypothesis strategies for Kida property-based testing.

Provides reusable strategies that generate structurally valid template
inputs at three abstraction levels:

- **Lexer**: Template fragments with valid delimiter patterns
- **Expressions**: Valid expression strings and their expected evaluation context
- **Filters**: Filter names and chains drawn from the built-in registry

These are building blocks -- individual test modules compose them into
property-specific strategies.
"""

from __future__ import annotations

from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Lexer strategies
# ---------------------------------------------------------------------------

# Plain text that does NOT contain kida delimiters (no { or })
# Used to test the DATA-token roundtrip invariant.
plain_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),  # no surrogates
        blacklist_characters="{}\x00",
    ),
    min_size=1,
    max_size=200,
)

# Valid kida variable expressions: {{ identifier }}
_identifier = st.from_regex(r"[a-z_][a-z0-9_]{0,12}", fullmatch=True)
kida_variable = _identifier.map(lambda name: f"{{{{ {name} }}}}")

# Valid kida comments: {# text #}
_comment_body = st.from_regex(r"[a-zA-Z0-9_ ]{0,30}", fullmatch=True)
kida_comment = _comment_body.map(lambda body: f"{{# {body} #}}")

# Template fragments: plain text interleaved with variables and comments
template_fragment = st.lists(
    st.one_of(
        plain_text.filter(lambda s: "{{" not in s and "{%" not in s and "{#" not in s),
        kida_variable,
        kida_comment,
    ),
    min_size=1,
    max_size=5,
).map("".join)

# Arbitrary bytes that might stress the lexer (fuzz-like)
arbitrary_template_source = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=300,
)

# ---------------------------------------------------------------------------
# Expression strategies
# ---------------------------------------------------------------------------

# Identifiers safe to use as variable names (avoid kida keywords)
safe_identifier = st.sampled_from(
    [
        "x",
        "y",
        "z",
        "a",
        "b",
        "val",
        "item",
        "count",
        "name",
        "data",
        "foo",
        "bar",
        "num",
        "text",
        "flag",
        "total",
        "score",
        "idx",
    ]
)

# Integer values in a safe range for arithmetic tests
safe_integer = st.integers(min_value=-10_000, max_value=10_000)

# ASCII-only lowercase strings for case-conversion roundtrips
ascii_lowercase_text = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",), whitelist_characters=" "),
    min_size=0,
    max_size=50,
).filter(lambda s: s.isascii())

# ---------------------------------------------------------------------------
# Filter strategies
# ---------------------------------------------------------------------------

# Filters that are safe to apply to strings without arguments
string_safe_filters = st.sampled_from(
    [
        "upper",
        "lower",
        "trim",
        "title",
        "capitalize",
        "string",
    ]
)

# Filters safe for lists
list_safe_filters = st.sampled_from(
    [
        "length",
        "first",
        "last",
        "reverse",
        "list",
    ]
)

# Build a filter chain of 1-4 string-safe filters
string_filter_chain = st.lists(
    string_safe_filters,
    min_size=1,
    max_size=4,
).map(" | ".join)

# Sortable integer lists (no None, no mixed types)
sortable_int_list = st.lists(
    st.integers(min_value=-1000, max_value=1000),
    min_size=0,
    max_size=30,
)
