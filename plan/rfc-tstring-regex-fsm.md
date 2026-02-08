# RFC: Template Regex (r-tag) and Delimiter Detection Optimization

**Status**: ✅ Implemented (Phase 1 r-tag + Phase 2 delimiter detection; Phase 3 s-tag descoped)  
**Created**: 2026-01-11  
**Updated**: 2026-02-08  
**Author**: Kida Contributors  
**Minimum Python**: 3.14 (t-strings)
**Related**: `plan/rfc-tstring-dogfooding.md` (t-string adoption strategy)

---

## Executive Summary

**Phase 0 exploration completed.** Benchmarks reveal a more nuanced picture than initially hypothesized:

| Optimization | Expected | Actual | Verdict |
|--------------|----------|--------|---------|
| Delimiter detection (regex vs str.find) | 2x faster | **5x faster** | ✅ Clear win |
| Token dispatch (master regex vs current) | 3x faster | **0.8x (slower)** | ❌ Not beneficial |
| Overall lexer improvement | 15-30% | **~7%** | ⚠️ Modest |

**Revised Scope**: This RFC now focuses on:

1. **`r` tag (Template Regex)**: Safe, composable regex building — **proceed as planned**
2. **Delimiter detection optimization**: Replace `str.find()` x3 with single regex — **high value, low risk**
3. ~~**`s` tag (Full FSM)**~~: **Descoped** — Master regex is slower for token dispatch

The current lexer's character-by-character approach with O(1) operator lookup is already well-optimized for code tokenization.

---

## 0. Phase 0 Exploration Results

**Completed**: 2026-01-12

### 0.1 Delimiter Detection: Clear Win

The current `_find_next_construct()` calls `str.find()` three times per iteration:

```python
# Current: O(3n) string scans
for start in [config.variable_start, config.block_start, config.comment_start]:
    pos = self._source.find(start, self._pos)
```

**Benchmark results** (medium template, 10 constructs):

| Approach | Time | Speedup |
|----------|------|---------|
| `str.find()` x3 | 6.17µs | 1.0x |
| Single `regex.search()` | 1.34µs | **4.6x** |

For data-heavy templates (30 constructs, lots of static content):

| Approach | Time | Speedup |
|----------|------|---------|
| `str.find()` x3 | 75.03µs | 1.0x |
| Single `regex.search()` | 3.11µs | **24x** |

**Verdict**: ✅ Replace `_find_next_construct()` with compiled regex.

### 0.2 Token Dispatch: Current Approach Wins

The master regex approach (single alternation with named groups) was tested against the current individual-regex approach:

```python
# Master regex (proposed FSM approach)
MASTER = re.compile(r'(?P<NAME>...)|(?P<STRING>...)|(?P<INTEGER>...)|...')

# Current approach (individual patterns + dict lookup)
if c in OPERATORS:  # O(1) dict lookup
    ...
elif NAME_RE.match(source, pos):  # Specific regex
    ...
```

**Benchmark results** (1819 chars of code content, 530 tokens):

| Approach | Time | Speedup |
|----------|------|---------|
| Individual regex + dict | 121.53µs | 1.0x |
| Master regex | 145.72µs | **0.83x (slower)** |

**Why master regex is slower**: The master regex must attempt all alternatives on every match, even for simple single-character operators. The current approach uses O(1) dict lookup for operators first, then tries specific regex patterns only when needed.

**Verdict**: ❌ Do not replace token dispatch with master regex.

### 0.3 r-tag Composition: Zero Overhead

Tested whether wrapping patterns in non-capturing groups `(?:...)` adds overhead:

| Pattern Style | Time | Overhead |
|---------------|------|----------|
| Direct groups `(...)` | 31.06µs | baseline |
| Non-capturing `(?:...)` | 30.38µs | **-2.2%** (faster) |

**Verdict**: ✅ r-tag composition has no performance cost.

### 0.4 Overall Impact

Delimiter detection accounts for ~9% of total tokenization time on typical templates. Optimizing it yields:

- **Medium templates**: ~7% overall improvement
- **Data-heavy templates**: Larger improvement (delimiter detection dominates)
- **Construct-dense templates**: Minimal improvement (token dispatch dominates)

---

## 1. Current State Analysis

### 1.1 Lexer Architecture

The current lexer (`src/kida/lexer.py`) operates in 4 modes:

```python
class LexerMode(Enum):
    DATA = auto()      # Outside template constructs
    BLOCK = auto()     # Inside {% %}
    VARIABLE = auto()  # Inside {{ }}
    COMMENT = auto()   # Inside {# #}
```

Mode dispatch uses a simple 4-branch switch:

```python
while self._pos < len(self._source):
    if self._mode == LexerMode.DATA:
        yield from self._tokenize_data()
    elif self._mode == LexerMode.VARIABLE:
        yield from self._tokenize_code(...)
    elif self._mode == LexerMode.BLOCK:
        yield from self._tokenize_code(...)
    elif self._mode == LexerMode.COMMENT:
        yield from self._tokenize_comment()
```

### 1.2 Delimiter Detection

The `_find_next_construct()` method scans for the nearest delimiter using three `str.find()` calls:

```python
def _find_next_construct(self) -> tuple[str, int] | None:
    positions = []
    for name, start in [
        ("variable", self._config.variable_start),
        ("block", self._config.block_start),
        ("comment", self._config.comment_start),
    ]:
        pos = self._source.find(start, self._pos)
        if pos != -1:
            positions.append((name, pos))
    return min(positions, key=lambda x: x[1]) if positions else None
```

### 1.3 Existing Optimizations

The lexer already employs several optimizations:

- **Class-level compiled regex**: `_NAME_RE`, `_STRING_RE`, `_FLOAT_RE`, etc.
- **O(1) operator lookup**: `_OPERATORS_1CHAR`, `_OPERATORS_2CHAR`, `_OPERATORS_3CHAR` dicts
- **Single-pass scanning**: No backtracking; position advances monotonically
- **Generator-based**: Memory-efficient token yielding

### 1.4 Opportunity

The primary opportunity is **consolidation**: replacing scattered pattern definitions and find/match calls with a single declarative FSM that:

1. Compiles all patterns for a state into one master regex
2. Uses `match.lastgroup` for O(1) token type dispatch
3. Provides automatic ReDoS validation at definition time

---

## 2. The `r` Tag: Composable Regex

Building complex regex by string concatenation is error-prone. The `r` tag treats regex as a first-class template citizen.

### 2.1 Current Pattern

```python
_NAME_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
_STRING_RE = re.compile(r"('([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\")")

# Risky! Group indices can collide, quantifiers can interact
_PATTERN = re.compile(_NAME_RE.pattern + "|" + _STRING_RE.pattern)
```

### 2.2 Proposed Pattern

```python
from kida.tstring import r

NAME = r"[a-zA-Z_][a-zA-Z0-9_]*"
STRING = r"('([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\")"

# Safe composition: automatic non-capturing groups, validated at definition
EXPRESSION = r"{NAME}|{STRING}"  # Compiles to: (?:[a-zA-Z_]...)|(?:'...')
```

### 2.3 Implementation Detail

The `r` tag function:

1. Wraps each interpolated pattern in `(?:...)` to prevent group bleeding
2. Validates the final pattern for ReDoS risks (nested quantifiers like `(a+)+`)
3. Returns a `ComposablePattern` wrapper with `pattern` property and `compile()` method
4. Raises `PatternError` at definition time if validation fails

```python
def r(template: TemplateProtocol) -> ComposablePattern:
    """Compose regex patterns safely with automatic isolation."""
    parts = []
    for i, s in enumerate(template.strings):
        parts.append(s)
        if i < len(template.interpolations):
            sub = template.interpolations[i].value
            # Wrap in non-capturing group to isolate
            parts.append(f"(?:{sub})")

    pattern = "".join(parts)
    _validate_redos_safety(pattern)  # Raises if dangerous
    return ComposablePattern(pattern)
```

### 2.4 Standalone Value

The `r` tag is independently valuable even without the `s` tag:

- **Safer regex composition** in any Python code
- **ReDoS prevention** catches exponential backtracking at load time
- **No lexer changes required** — can be adopted incrementally

---

## 3. ~~The `s` Tag: Stateful Lexer DSL~~ (DESCOPED)

> **Status**: Descoped after Phase 0 benchmarks showed master regex is 0.83x slower than current approach.

### 3.1 Original Proposal

The `s` tag was proposed to define an entire FSM with master regex per state:

```python
# DESCOPED - Master regex is slower than current approach
LEXER_FSM = s"""
    [BLOCK] {
        {config.block_end}  => BLOCK_END, mode=DATA
        {NAME}              => NAME
        {STRING}            => STRING
        ...
    }
"""
```

### 3.2 Why It Doesn't Work

**Hypothesis**: A single master regex with named groups would be faster than multiple individual regex matches.

**Reality**: The current approach is more efficient because:

1. **O(1) operator lookup**: Single-character operators (`|`, `.`, `(`, `)`, etc.) use dict lookup, not regex
2. **Short-circuit evaluation**: Individual patterns stop at first match; master regex must attempt all alternatives
3. **Cache locality**: Small, focused patterns have better cache behavior

**Benchmark evidence**:

```
Master regex:     145.72µs (530 tokens)
Individual regex: 121.53µs (530 tokens)
Speedup: 0.83x (master regex is 17% SLOWER)
```

### 3.3 What Remains Valuable

The **DATA mode** portion of the s-tag concept remains valuable:

```python
# This part IS worth optimizing
DELIMITER_PATTERN = re.compile(
    f"({re.escape(config.variable_start)}|"
    f"{re.escape(config.block_start)}|"
    f"{re.escape(config.comment_start)})"
)
```

This is implemented as a simple optimization in `_find_next_construct()` without the full FSM machinery.

### 3.4 Future Consideration

If Python's `re` module gains support for DFA-based matching (like RE2), the master regex approach may become competitive. Monitor:
- [PEP 3132](https://peps.python.org/pep-3132/) - Extended iterable unpacking
- Potential `regex` module integration with linear-time guarantees

---

## 4. Performance Analysis (Validated)

### 4.1 Measured Results

| Aspect | Current | Optimized | Measured Improvement |
|--------|---------|-----------|---------------------|
| Delimiter search | 3× `str.find()` | Single `regex.search()` | **5x faster** (24x for data-heavy) |
| Token dispatch | Individual regex + dict | Master regex | **0.83x (slower)** — not adopted |
| r-tag composition | N/A | Non-capturing groups | **No overhead** |

### 4.2 Actual Gains

**Based on Phase 0 benchmarks**:

| Template Type | Delimiter % of Total | Expected Improvement |
|---------------|----------------------|---------------------|
| Medium (realistic) | ~9% | ~7% overall |
| Data-heavy (lots of static HTML) | ~20-30% | ~15-20% overall |
| Construct-dense (many {{ }}) | ~5% | ~4% overall |

### 4.3 Why Token Dispatch Optimization Fails

The current lexer uses a clever two-tier approach:

```python
# Tier 1: O(1) dict lookup for operators (fastest path)
if char in self._OPERATORS_1CHAR:
    return self._emit_delimiter(char, self._OPERATORS_1CHAR[char])

# Tier 2: Regex only when needed
if char.isalpha() or char == "_":
    return self._scan_name()
```

A master regex cannot replicate this because:
1. It must attempt all alternatives (O(k) where k = pattern count)
2. No short-circuit on first match
3. Higher overhead for the common case (single-char operators)

---

## 5. Implementation Plan (Revised)

### Phase 0: Baseline Benchmarks — ✅ COMPLETED

Benchmarks created in `benchmarks/test_benchmark_lexer.py`. Key findings:
- Delimiter detection: 5x improvement opportunity
- Token dispatch: Current approach is optimal
- r-tag composition: Zero overhead

### Phase 1: `r` Tag (Template Regex) — 2 days

- [ ] Implement `r` tag returning `ComposablePattern`
- [ ] Add non-capturing group wrapping for interpolations
- [ ] Implement ReDoS detection (flag nested quantifiers)
- [ ] Add unit tests for composition and validation
- [ ] Document in `site/content/docs/internals/tstring-r-tag.md`

```python
# kida/tstring/r.py
from __future__ import annotations
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from string.templatelib import Template

class ComposablePattern:
    """Safe, composable regex pattern with ReDoS validation."""

    def __init__(self, pattern: str):
        self._pattern = pattern
        self._compiled: re.Pattern | None = None
        _validate_redos_safety(pattern)

    @property
    def pattern(self) -> str:
        return self._pattern

    def compile(self, flags: int = 0) -> re.Pattern:
        if self._compiled is None:
            self._compiled = re.compile(self._pattern, flags)
        return self._compiled

def r(template: Template) -> ComposablePattern:
    """Compose regex patterns with automatic isolation."""
    parts = []
    for i, s in enumerate(template.strings):
        parts.append(s)
        if i < len(template.interpolations):
            sub = template.interpolations[i].value
            parts.append(f"(?:{sub})")  # Non-capturing group
    return ComposablePattern("".join(parts))
```

### Phase 2: Delimiter Detection Optimization — 1 day

- [ ] Add `_DELIMITER_PATTERN` class-level compiled regex
- [ ] Replace `_find_next_construct()` implementation
- [ ] Run full test suite
- [ ] Benchmark against Phase 0 baseline

```python
# Optimization in kida/lexer.py
class Lexer:
    # Class-level: compile once per config (via lru_cache)
    @staticmethod
    @lru_cache(maxsize=16)
    def _get_delimiter_pattern(config: LexerConfig) -> re.Pattern:
        return re.compile(
            f"({re.escape(config.variable_start)}|"
            f"{re.escape(config.block_start)}|"
            f"{re.escape(config.comment_start)})"
        )

    def _find_next_construct(self) -> tuple[str, int] | None:
        """Find next template construct using compiled regex."""
        pattern = self._get_delimiter_pattern(self._config)
        match = pattern.search(self._source, self._pos)
        if match is None:
            return None

        delimiter = match.group()
        if delimiter == self._config.variable_start:
            return ("variable", match.start())
        elif delimiter == self._config.block_start:
            return ("block", match.start())
        else:
            return ("comment", match.start())
```

### ~~Phase 3: FSM Engine~~ — CANCELLED

Master regex approach is slower than current token dispatch. Not implementing.

---

## 6. Risks and Mitigations (Updated)

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Minimal performance gain** | Low | Low | Phase 0 validated ~7% gain; acceptable |
| **Dynamic delimiter complexity** | Low | Low | `lru_cache(maxsize=16)` handles custom configs |
| **ReDoS false positives** | Low | Medium | Allow `# redos: ignore` pragma for vetted patterns |
| **Python 3.14 dependency** | Medium | Low | `r` tag can fall back to string-based composition on 3.13 |
| ~~Master regex slower~~ | ~~High~~ | ~~High~~ | ~~Descoped; not implementing s-tag~~ |

---

## 7. Success Criteria (Revised)

### Required (all must pass)

- [ ] `r` tag compiles patterns correctly with automatic group isolation
- [ ] `r` tag rejects known ReDoS patterns at definition time
- [ ] `_find_next_construct()` uses compiled regex instead of `str.find()` x3
- [ ] All existing `tests/test_lexer.py` tests pass
- [ ] No regression on construct-dense templates

### Desired (stretch goals)

- [ ] `_find_next_construct` is ≥3x faster (Phase 0 showed 5x possible)
- [ ] Overall tokenization improves by ≥5% on medium templates
- [ ] ReDoS validation catches ≥90% of known dangerous patterns

### Validation Commands

```bash
# Run lexer benchmarks
uv run pytest benchmarks/test_benchmark_lexer.py -v --benchmark-only

# Compare delimiter detection approaches
uv run pytest benchmarks/test_benchmark_lexer.py -k "alternatives" --benchmark-only

# Full test suite
uv run pytest tests/test_lexer.py tests/test_parser.py -v

# r-tag unit tests (after implementation)
uv run pytest tests/test_tstring_r.py -v
```

---

## 8. Example: Delimiter Detection Optimization

### Before (current)

```python
def _find_next_construct(self) -> tuple[str, int] | None:
    positions = []
    for name, start in [
        ("variable", self._config.variable_start),
        ("block", self._config.block_start),
        ("comment", self._config.comment_start),
    ]:
        pos = self._source.find(start, self._pos)  # O(n) scan
        if pos != -1:
            positions.append((name, pos))
    # 3 string scans per call!
    return min(positions, key=lambda x: x[1]) if positions else None
```

### After (optimized)

```python
# Compiled once per config (cached)
_DELIMITER_PATTERN = re.compile(r"(\{\{|\{%|\{#)")

def _find_next_construct(self) -> tuple[str, int] | None:
    match = self._delimiter_pattern.search(self._source, self._pos)
    if match is None:
        return None
    # Single regex scan finds nearest delimiter
    delimiter = match.group()
    name = {"{{": "variable", "{%": "block", "{#": "comment"}[delimiter]
    return (name, match.start())
```

### Performance Impact

| Template Type | Before | After | Improvement |
|---------------|--------|-------|-------------|
| Medium (10 constructs) | 6.17µs | 1.34µs | **4.6x** |
| Data-heavy (30 constructs) | 75.03µs | 3.11µs | **24x** |

---

## 9. Appendix: ReDoS Detection

The `r` tag validates patterns for exponential backtracking risks:

```python
REDOS_PATTERNS = [
    r"\(\w+\+\)\+",           # (a+)+
    r"\(\w+\*\)\+",           # (a*)+
    r"\(\w+\+\)\*",           # (a+)*
    r"\(\.\*\)\+",            # (.*)+
    r"\(\w+\|\w+\)\+\w+\1",   # (a|b)+...backreference
]

def _validate_redos_safety(pattern: str) -> None:
    """Raise PatternError if pattern contains known ReDoS risks."""
    for risk in REDOS_PATTERNS:
        if re.search(risk, pattern):
            raise PatternError(
                f"Pattern contains ReDoS risk: {risk}\n"
                f"Add '# redos: ignore' pragma if intentional."
            )
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-11 | Initial draft |
| 2026-01-11 | Added Phase 0 benchmarks, current state analysis, dynamic delimiter solution, token flow example, validation commands |
| 2026-01-12 | **Phase 0 exploration completed**: Delimiter detection shows 5x win; master regex for token dispatch shows 0.83x (slower). Descoped s-tag FSM. Revised RFC to focus on r-tag and delimiter detection only. |
