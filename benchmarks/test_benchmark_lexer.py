"""Lexer performance exploration for FSM RFC validation.

Run with:
    uv run pytest benchmarks/test_benchmark_lexer.py -v --benchmark-only

This benchmark establishes baselines before any FSM refactoring.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from kida._types import TokenType
from kida.lexer import Lexer, LexerConfig

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


# =============================================================================
# Test Templates
# =============================================================================

# Minimal: single variable
MINIMAL = "{{ name }}"

# Small: typical loop with variable
SMALL = """\
{% for item in items %}
  <li>{{ item.name | upper }}</li>
{% end %}
"""

# Medium: realistic page fragment
MEDIUM = """\
{% if user %}
  <div class="profile">
    <h1>{{ user.name | title }}</h1>
    <p>{{ user.bio | default("No bio") }}</p>
    {% for post in user.posts %}
      <article>
        <h2>{{ post.title }}</h2>
        <time>{{ post.date | date }}</time>
        {{ post.content }}
      </article>
    {% end %}
  </div>
{% else %}
  <p>Please log in.</p>
{% end %}
"""

# Large: repeated medium template
LARGE = MEDIUM * 20

# Data-heavy: lots of raw text between constructs
DATA_HEAVY = (
    """
This is a large block of static HTML content that doesn't contain any
template constructs. It simulates a real-world template where most of
the content is static HTML with occasional dynamic parts.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim
veniam, quis nostrud exercitation ullamco laboris.

{{ variable_1 }}

More static content here. The lexer needs to scan through all of this
to find the next template construct. This tests the efficiency of the
_find_next_construct method.

{{ variable_2 }}

Even more content. In a real template, you might have navigation HTML,
footer content, scripts, and other static elements.

{{ variable_3 }}
"""
    * 10
)

# Construct-dense: many template constructs, little data
CONSTRUCT_DENSE = "{{ a }}{{ b }}{{ c }}{% if x %}{{ d }}{% end %}" * 50


# =============================================================================
# Baseline Benchmarks
# =============================================================================


@pytest.mark.benchmark(group="lexer:full-tokenize")
@pytest.mark.parametrize(
    "template,name",
    [
        (MINIMAL, "minimal"),
        (SMALL, "small"),
        (MEDIUM, "medium"),
        (LARGE, "large"),
        (DATA_HEAVY, "data-heavy"),
        (CONSTRUCT_DENSE, "construct-dense"),
    ],
)
def test_lexer_tokenize_baseline(benchmark: BenchmarkFixture, template: str, name: str) -> None:
    """Baseline: Full tokenization throughput."""

    def run() -> list:
        lexer = Lexer(template)
        return list(lexer.tokenize())

    result = benchmark(run)
    token_count = len(result)
    # Calculate tokens per second from benchmark stats
    if hasattr(benchmark, "stats") and benchmark.stats:
        mean_time = benchmark.stats.stats.mean
        if mean_time > 0:
            tokens_per_sec = token_count / mean_time
            print(f"\n  {name}: {token_count} tokens, {tokens_per_sec:,.0f} tok/s")


# =============================================================================
# _find_next_construct Analysis
# =============================================================================


@pytest.mark.benchmark(group="lexer:find-construct")
def test_find_next_construct_isolated(benchmark: BenchmarkFixture) -> None:
    """Benchmark _find_next_construct in isolation."""
    template = DATA_HEAVY  # Worst case: lots of scanning

    def run() -> int:
        lexer = Lexer(template)
        count = 0
        while lexer._pos < len(template):
            result = lexer._find_next_construct()
            if result is None:
                break
            _, pos = result
            lexer._pos = pos + 2  # Skip past delimiter
            count += 1
        return count

    result = benchmark(run)
    print(f"\n  Found {result} constructs in {len(template)} chars")


# =============================================================================
# Alternative Approaches (Exploration)
# =============================================================================


@pytest.mark.benchmark(group="lexer:alternatives")
def test_alternative_find_with_regex(benchmark: BenchmarkFixture) -> None:
    """Test regex-based delimiter finding vs str.find()."""
    template = DATA_HEAVY
    config = LexerConfig()

    # Pre-compile the regex
    pattern = re.compile(
        f"({re.escape(config.variable_start)}|"
        f"{re.escape(config.block_start)}|"
        f"{re.escape(config.comment_start)})"
    )

    def run_regex() -> int:
        count = 0
        pos = 0
        while True:
            match = pattern.search(template, pos)
            if match is None:
                break
            count += 1
            pos = match.end()
        return count

    result = benchmark(run_regex)
    print(f"\n  Regex found {result} constructs")


@pytest.mark.benchmark(group="lexer:alternatives")
def test_alternative_find_with_str_find(benchmark: BenchmarkFixture) -> None:
    """Baseline: current str.find() approach."""
    template = DATA_HEAVY
    config = LexerConfig()

    def run_find() -> int:
        count = 0
        pos = 0
        while True:
            positions = []
            for start in [config.variable_start, config.block_start, config.comment_start]:
                p = template.find(start, pos)
                if p != -1:
                    positions.append(p)
            if not positions:
                break
            next_pos = min(positions)
            count += 1
            pos = next_pos + 2
        return count

    result = benchmark(run_find)
    print(f"\n  str.find() found {result} constructs")


# =============================================================================
# Master Regex Token Dispatch (FSM Prototype)
# =============================================================================


@pytest.mark.benchmark(group="lexer:fsm-prototype")
def test_master_regex_prototype(benchmark: BenchmarkFixture) -> None:
    """Prototype: single master regex for BLOCK/VARIABLE mode tokens."""
    # Simulate what the s-tag FSM would compile to
    master_pattern = re.compile(
        r"(?P<WHITESPACE>[ \t\n\r]+)|"
        r"(?P<NAME>[a-zA-Z_][a-zA-Z0-9_]*)|"
        r"(?P<STRING>'[^']*'|\"[^\"]*\")|"
        r"(?P<INTEGER>\d+)|"
        r"(?P<PIPE>\|)|"
        r"(?P<DOT>\.)|"
        r"(?P<LPAREN>\()|"
        r"(?P<RPAREN>\))|"
        r"(?P<COMMA>,)"
    )

    # Sample code content (inside {{ }} or {% %})
    code_samples = [
        "user.name | upper",
        "item.price * quantity | currency",
        "posts | selectattr('published') | first",
        "loop.index",
        "range(1, 10)",
    ]
    code_content = " ".join(code_samples * 20)

    def run_master_regex() -> int:
        tokens = []
        pos = 0
        while pos < len(code_content):
            match = master_pattern.match(code_content, pos)
            if match:
                if match.lastgroup != "WHITESPACE":
                    tokens.append((match.lastgroup, match.group()))
                pos = match.end()
            else:
                pos += 1  # Skip unknown char
        return len(tokens)

    result = benchmark(run_master_regex)
    print(f"\n  Master regex extracted {result} tokens from {len(code_content)} chars")


@pytest.mark.benchmark(group="lexer:fsm-prototype")
def test_current_code_tokenizer(benchmark: BenchmarkFixture) -> None:
    """Baseline: current _next_code_token approach."""
    # Same code content
    code_samples = [
        "user.name | upper",
        "item.price * quantity | currency",
        "posts | selectattr('published') | first",
        "loop.index",
        "range(1, 10)",
    ]
    code_content = " ".join(code_samples * 20)

    # Wrap in {{ }} to make it valid template
    template = "{{ " + code_content + " }}"

    def run_current() -> int:
        lexer = Lexer(template)
        tokens = [
            t
            for t in lexer.tokenize()
            if t.type not in (TokenType.VARIABLE_BEGIN, TokenType.VARIABLE_END, TokenType.EOF)
        ]
        return len(tokens)

    result = benchmark(run_current)
    print(f"\n  Current lexer extracted {result} tokens")


# =============================================================================
# r-tag Prototype
# =============================================================================


class ComposablePattern:
    """Prototype for r-tag result."""

    def __init__(self, pattern: str):
        self._pattern = pattern
        self._compiled: re.Pattern | None = None

    @property
    def pattern(self) -> str:
        return self._pattern

    def compile(self, flags: int = 0) -> re.Pattern:
        if self._compiled is None:
            self._compiled = re.compile(self._pattern, flags)
        return self._compiled

    def __or__(self, other: ComposablePattern) -> ComposablePattern:
        """Allow pattern1 | pattern2 composition."""
        return ComposablePattern(f"(?:{self._pattern})|(?:{other._pattern})")


def r_tag_prototype(*patterns: str) -> ComposablePattern:
    """Prototype r-tag: compose patterns with automatic grouping."""
    if len(patterns) == 1:
        return ComposablePattern(patterns[0])

    # Wrap each in non-capturing group and join with |
    wrapped = [f"(?:{p})" for p in patterns]
    return ComposablePattern("|".join(wrapped))


@pytest.mark.benchmark(group="lexer:r-tag")
def test_r_tag_composition(benchmark: BenchmarkFixture) -> None:
    """Test r-tag pattern composition overhead."""
    name_pat = r"[a-zA-Z_][a-zA-Z0-9_]*"
    string_pat = r"'[^']*'|\"[^\"]*\""
    integer_pat = r"\d+"
    float_pat = r"\d+\.\d+"

    def run():
        # Compose patterns
        expr = r_tag_prototype(name_pat, string_pat, integer_pat, float_pat)
        # Compile
        compiled = expr.compile()
        # Use it
        return compiled.match("variable_name")

    result = benchmark(run)
    print(f"\n  r-tag composed and matched: {result.group() if result else None}")


@pytest.mark.benchmark(group="lexer:r-tag")
def test_manual_composition(benchmark: BenchmarkFixture) -> None:
    """Baseline: manual pattern composition."""
    name_pat = r"[a-zA-Z_][a-zA-Z0-9_]*"
    string_pat = r"'[^']*'|\"[^\"]*\""
    integer_pat = r"\d+"
    float_pat = r"\d+\.\d+"

    def run():
        # Manual composition (current approach)
        pattern = f"({name_pat})|({string_pat})|({integer_pat})|({float_pat})"
        compiled = re.compile(pattern)
        return compiled.match("variable_name")

    result = benchmark(run)
    print(f"\n  Manual composed and matched: {result.group() if result else None}")
