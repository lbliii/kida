# RFC: Template Regex (r-tag) and State Machine (s-tag) DSL

**Status**: Draft  
**Created**: 2026-01-11  
**Author**: Kida Contributors  
**Minimum Python**: 3.14 (t-strings)

---

## Executive Summary

Kida currently uses a manual lexer with multiple operating modes (DATA, BLOCK, VARIABLE, COMMENT). Transition logic is scattered across `if/elif` blocks and manual `str.find()` calls.

By leveraging **Python 3.14 t-strings**, we can "invent" two new tags that transform Kida's internals into a declarative, highly optimized state machine:

1.  **`r` tag (Template Regex)**: Safe, composable regex building with automatic group isolation.
2.  **`s` tag (State Machine)**: A DSL for defining lexer modes, token generation, and state transitions in a single literal.

---

## 1. The `r` Tag: Composable Regex

Building complex regex by string concatenation is error-prone. The `r` tag treats regex as a first-class template citizen.

**Current**:
```python
_NAME_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
_STRING_RE = re.compile(r"('([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\")")
_PATTERN = re.compile(_NAME_RE.pattern + "|" + _STRING_RE.pattern) # Risky!
```

**Proposed**:
```python
NAME = r"[a-zA-Z_][a-zA-Z0-9_]*"
STRING = r"('([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\")"

# Safe composition: automatic non-capturing groups
EXPRESSION = r"{NAME}|{STRING}"
```

**Implementation Detail**:
The `r` tag function wraps interpolated patterns in `(?:...)` and validates the resulting pattern at the moment of definition.

---

## 2. The `s` Tag: Stateful Lexer DSL

The `s` tag defines an entire Finite State Machine (FSM). It maps "Current State + Input Pattern" to "Yield Token + Next State".

**Proposed DSL Syntax**:
```python
LEXER_FSM = s"""
    [DATA] {
        {config.block_start}    => token=BLOCK_BEGIN,    mode=BLOCK
        {config.variable_start} => token=VARIABLE_BEGIN, mode=VARIABLE
        {config.comment_start}  => token=COMMENT_BEGIN,  mode=COMMENT
        # Lazy match data until next construct
        .+?(?={config.block_start}|{config.variable_start}|{config.comment_start}|$) => token=DATA
    }

    [BLOCK] {
        {config.block_end}      => token=BLOCK_END,      mode=DATA
        {NAME}                  => token=NAME
        {STRING}                => token=STRING
        {NUMBER}                => token=FLOAT if '.' in it else INTEGER
        \s+                     => skip
    }
"""
```

**Technical Benefits**:
1.  **Master Regex Compilation**: The `s` tag compiles each state into a single `re.compile()` call using named groups (e.g., `(?P<BLOCK_BEGIN_1>{config.block_start})|(?P<DATA_2>...)`).
2.  **Zero Dispatch Overhead**: Instead of checking 50 `if` statements, the lexer performs a single `regex.match()` per token.
3.  **Declarative Clarity**: Transitions are documented in the code structure itself.

---

## 3. Performance, Security & Architecture

### 3.1 Master Regex Performance
The `s` tag FSM achieves high performance by moving state logic from Python's interpreter into the C-level `re` engine:
- **C-level Branching**: Every transition in a state is compiled into one large alternation regex using named groups: `(?P<T1>pattern1)|(?P<T2>pattern2)`.
- **$O(1)$ Token Dispatch**: After a match, the engine uses `match.lastgroup` to identify the token type in a single hash lookup, bypassing $O(N)$ `if/elif` chains.
- **Zero-Copy Scanning**: The lexer uses `regex.match(source, pos)` which performs a direct scan at the current pointer without creating string slices or performing global searches.

### 3.2 ReDoS Safety (Validation Gate)
The `r` and `s` tags provide a security barrier that manual regex concatenation lacks:
- **Atomic Isolation**: Every interpolated sub-pattern in an `r` tag is automatically wrapped in a non-capturing group `(?:...)`. This prevents unexpected "group bleeding" and quantifier overlap.
- **Load-Time Audit**: Since tag functions run when the module is imported, the `r` tag can audit the final pattern for exponential backtracking risks (e.g., nested quantifiers like `(a+)+`) and raise a `DeveloperError` before the application starts.
- **State Search-Space Reduction**: By isolating patterns into discrete FSM states (modes), the potential for cross-pattern interference is minimized. A dangerous pattern in the `BLOCK` mode cannot be triggered by content in the `DATA` mode.

### 3.3 Strict Single-Pass Execution
The FSM architecture guarantees a linear $O(N)$ scan of the source text:
- **No Backtracking**: By using `match()` specifically at the `pos` pointer, the lexer refuses to skip characters. It either consumes a token and moves forward or fails immediately.
- **Deterministic Transitions**: Each rule in the `s` tag defines a fixed next state. There is no "trial and error" between modes.

---

## 4. Implementation Plan

### Phase 1: Regex Protocol (`kida.tstring.r`)
- [ ] Implement `r` tag that returns a `re.Pattern` wrapper.
- [ ] Add logic to detect and wrap sub-patterns to prevent group collision.

### Phase 2: FSM Engine (`kida.lexer.fsm`)
- [ ] Implement `s` tag parser that extracts states, patterns, and transitions.
- [ ] Generate optimized matching logic for the `Lexer` class.

### Phase 3: Lexer Refactor
- [ ] Port `Lexer.tokenize()` to use the `LEXER_FSM` definition.
- [ ] Benchmark against the current manual lexer.

---

## 5. Expected Performance Gain

| Operation | Current (Manual) | FSM (s-tag) | Gain |
|-----------|------------------|-------------|------|
| Mode Switch | `str.find()` + logic | `regex.match()` | ~2x faster |
| Token Dispatch | `if/elif` chain | `match.lastgroup` | ~3x faster |
| Safety | Manual Audit | Automated Gate | High |
| Pass Count | Multi-pass | **Single-pass** | N/A |

---

## 6. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Regex Complexity | Medium | Limit total patterns per state to stay within `re` engine limits. |
| Dynamic Delimiters | High | Since delimiters are configurable, the `s` tag must be able to re-compile or handle late-binding of patterns. |
| Memory Usage | Low | Compiled FSMs are cached at the class level. |

---

## 7. Success Criteria

- [ ] `r` tag successfully isolates and validates sub-patterns.
- [ ] `s` tag FSM generates a single master regex per state.
- [ ] Tokenization throughput increases by >50% in `benchmarks/`.
- [ ] No exponential backtracking detected in stress-test templates.
