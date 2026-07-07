# RFC: Type-Safe Mixin Patterns via Hybrid Protocol + Inline Declarations

**Status**: Foundation implemented — remaining ty override debt tracked in GitHub issue #142

| Field | Value |
|-------|-------|
| **Created** | 2026-01-05 |
| **Updated** | 2026-02-08 |
| **Author** | Auto-generated |
| **Depends On** | rfc-type-suppression-reduction.md (Phase 3) |
| **Target** | Python 3.14+ |

---

> [!NOTE]
> `ParserCoreProtocol`, `CompilerCoreProtocol`, and inline `TYPE_CHECKING`
> declarations shipped. The original success gate targeted mypy, which Kida no
> longer uses. Current ty still needs scoped `unresolved-attribute = "warn"`
> overrides for parser, compiler, and analysis mixin/visitor boundaries; the
> remaining work is tracked in
> [GitHub issue #142](https://github.com/lbliii/kida/issues/142). The mypy
> commands and unchecked migration checklist below are historical, not an
> active implementation plan.

## Executive Summary

This RFC proposes converting Kida's parser and compiler mixins to type-safe implementations using a **hybrid approach**:

1. **Minimal Core Protocol**: Small protocol (~16 members) containing only host attributes and frequently-used cross-mixin methods
2. **Inline Type Declarations**: Each mixin declares its own requirements via `TYPE_CHECKING` blocks—self-documenting, no sync needed

This eliminates ~539 mypy errors while keeping protocol maintenance minimal.

**Key Outcome**: Remove all `[[tool.mypy.overrides]]` for parser/compiler modules.

**Prior Art**: `ExpressionParsingMixin` already uses inline TYPE_CHECKING declarations (lines 56-69). This RFC formalizes and extends this proven pattern to all mixins.

---

## Problem Statement

### Current State

The parser and compiler use cooperative multiple inheritance (mixins) to separate concerns:

```python
class Parser(
    TokenNavigationMixin,      # Token stream access
    BlockParsingMixin,         # Block parsing
    StatementParsingMixin,     # Statement parsing
    ExpressionParsingMixin,    # Expression parsing
):
    __slots__ = ("_tokens", "_pos", "_name", "_filename", "_source", "_autoescape", "_block_stack")
```

Each mixin accesses attributes defined in the host class or sibling mixins:

```python
class TokenNavigationMixin:
    """Mixin providing token stream navigation methods.

    Required Host Attributes:
        - _tokens: Sequence[Token]
        - _pos: int
        - _source: str | None
        - _filename: str | None
    """

    @property
    def _current(self) -> Token:
        # ERROR: "TokenNavigationMixin" has no attribute "_tokens" [attr-defined]
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return Token(TokenType.EOF, "", 0, 0)
```

### Type Errors Suppressed

Currently suppressing **12 error codes** across `kida.parser.*` and `kida.compiler.*`, masking **~539 individual errors**:

| Code | Count | Root Cause |
|------|-------|------------|
| `attr-defined` | ~500 | Mixin accesses host/sibling attributes |
| `override` | 1 | Property vs class variable conflict (see Known Issues) |
| `no-any-return` | ~13 | Dynamic dispatch (`getattr`) returns `Any` |
| `arg-type` | ~9 | AST node type variance |
| `type-arg` | ~1 | Missing generic type parameters |
| Other codes | ~15 | Various type issues |

**Total**: ~539 individual errors masked by 12 suppressed error codes.

**Verified**: `uv run mypy src/kida/parser src/kida/compiler --strict --config-file=""` (2026-01-05)

### Why This Matters

1. **No compile-time safety**: Interface drift between mixins and host is undetected
2. **IDE limitations**: No autocomplete or go-to-definition for cross-mixin calls
3. **Refactoring risk**: Renaming/removing attributes won't flag dependent mixins
4. **Documentation drift**: "Required Host Attributes" docstrings become stale

---

## Proposed Solution: Hybrid Approach

### Design Philosophy

Instead of one monolithic protocol with 45+ methods (high maintenance), use:

1. **Minimal Core Protocol**: Only what's needed for cross-mixin calls
2. **Inline Declarations**: Each mixin self-documents its requirements

This reduces protocol maintenance from ~75 signatures to ~16.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Parser Class                            │
│  (Provides all attributes and combines all mixin methods)       │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ structural typing verifies
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    ParserCoreProtocol                           │
│  (Small: host attrs + token nav + error handling)               │
│  ~16 members, rarely changes                                    │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ self: ParserCoreProtocol
                              │
┌──────────────┬──────────────┬──────────────┬───────────────────┐
│ TokenNav     │ Expression   │ Statement    │ Block Parsing     │
│ Mixin        │ Mixin        │ Mixin        │ Mixins            │
│              │              │              │                   │
│ (inline      │ (inline      │ (inline      │ (inline           │
│  decls for   │  decls for   │  decls for   │  decls for        │
│  own attrs)  │  own attrs)  │  own attrs)  │  own attrs)       │
└──────────────┴──────────────┴──────────────┴───────────────────┘
```

### Core Protocol (Minimal)

The protocol contains **only** what multiple mixins need to call:

```python
# kida/parser/_protocols.py
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from kida._types import Token, TokenType

if TYPE_CHECKING:
    from kida.parser.errors import ParseError


class ParserCoreProtocol(Protocol):
    """Minimal contract for cross-mixin dependencies.

    Contains ONLY:
    1. Host class attributes (defined in Parser.__init__)
    2. Token navigation methods (used by all parsing mixins)
    3. Error handling (used everywhere)

    Individual mixin methods are NOT included—mixins declare
    their own methods via inline TYPE_CHECKING declarations.
    """

    # ─────────────────────────────────────────────────────────────
    # Host Attributes (from Parser.__init__)
    # ─────────────────────────────────────────────────────────────
    _tokens: Sequence[Token]
    _pos: int
    _name: str | None
    _filename: str | None
    _source: str | None
    _autoescape: bool
    _block_stack: list[tuple[str, int, int]]

    # ─────────────────────────────────────────────────────────────
    # Token Navigation (from TokenNavigationMixin)
    # These are called by ALL other mixins, so they're in the protocol
    # ─────────────────────────────────────────────────────────────
    @property
    def _current(self) -> Token: ...
    def _peek(self, offset: int = 0) -> Token: ...
    def _advance(self) -> Token: ...
    def _expect(self, token_type: TokenType) -> Token: ...
    def _match(self, *types: TokenType) -> bool: ...
    def _error(
        self,
        message: str,
        token: Token | None = None,
        suggestion: str | None = None,
    ) -> ParseError: ...
    def _format_open_blocks(self) -> str: ...
```

**That's it.** ~16 members instead of ~75.

### Mixin Pattern (Inline Declarations)

Each mixin declares its own cross-mixin dependencies inline:

```python
# kida/parser/statements.py
from __future__ import annotations

from typing import TYPE_CHECKING

from kida._types import Token, TokenType

if TYPE_CHECKING:
    from kida.nodes import Data, Expr, Node, Output
    from kida.parser._protocols import ParserCoreProtocol


class StatementParsingMixin:
    """Mixin for parsing statements and template body."""

    # ─────────────────────────────────────────────────────────────
    # Cross-mixin dependencies (type-check only)
    # These are methods from OTHER mixins that this mixin calls
    # ─────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # From ExpressionParsingMixin
        def _parse_expression(self) -> Expr: ...

        # From BlockParsingMixin  
        def _parse_block_content(self) -> Node | list[Node] | None: ...
        def _push_block(self, block_type: str, lineno: int, col: int) -> None: ...
        def _pop_block(self, expected_type: str | None = None) -> tuple[str, int, int]: ...

    # ─────────────────────────────────────────────────────────────
    # Implementation (uses ParserCoreProtocol for host attrs)
    # ─────────────────────────────────────────────────────────────

    def _parse_body(
        self: ParserCoreProtocol,
        stop_on_continuation: bool = False,
    ) -> list[Node]:
        """Parse template body until end of input or block terminator."""
        body: list[Node] = []

        while not self._match(TokenType.EOF):  # ✅ from protocol
            token = self._current  # ✅ from protocol

            if token.type == TokenType.DATA:
                body.append(self._parse_data())
            elif token.type == TokenType.VARIABLE_BEGIN:
                body.append(self._parse_output())
            elif token.type == TokenType.BLOCK_BEGIN:
                result = self._parse_block_content()  # ✅ declared above
                # ... etc

        return body

    def _parse_output(self: ParserCoreProtocol) -> Output:
        """Parse {{ expression }} output."""
        self._expect(TokenType.VARIABLE_BEGIN)  # ✅ from protocol
        expr = self._parse_expression()  # ✅ declared above
        self._expect(TokenType.VARIABLE_END)  # ✅ from protocol
        return Output(lineno=expr.lineno, col_offset=expr.col_offset, expr=expr)
```

### Why This Works

1. **`self: ParserCoreProtocol`** gives access to host attrs + token navigation
2. **Inline `TYPE_CHECKING` declarations** tell mypy about sibling mixin methods
3. **No protocol sync needed** for mixin-specific methods—they're declared where used
4. **Self-documenting**: Each mixin shows exactly what it depends on

---

## Key Design Decisions

### 1. What Goes in the Core Protocol?

**Include** (called by 3+ mixins):
- Host class attributes (`_tokens`, `_pos`, etc.)
- Token navigation methods (`_current`, `_advance`, `_expect`, etc.)
- Error handling (`_error`)

**Exclude** (inline declarations instead):
- Expression parsing methods (`_parse_expression`, etc.)
- Statement parsing methods (`_parse_body`, etc.)
- Block parsing methods (`_parse_if`, `_parse_for`, etc.)

### 2. Protocol Location

```
kida/parser/_protocols.py   → ParserCoreProtocol
kida/compiler/_protocols.py → CompilerCoreProtocol
```

Protocols are in `TYPE_CHECKING`-imported files, zero runtime cost.

### 3. Inline Declaration Pattern

```python
class SomeMixin:
    if TYPE_CHECKING:
        # Declare methods from OTHER mixins that this one calls
        def _other_mixin_method(self) -> ReturnType: ...

    def _my_method(self: CoreProtocol) -> Result:
        # Can use:
        # - self._tokens, self._pos (from protocol)
        # - self._other_mixin_method() (from inline declaration)
        pass
```

---

## Known Issues to Resolve

### 1. Property vs Class Variable Conflict (`override` error)

**Problem**: `ExpressionParsingMixin` declares `_current: Token` as a class variable, but `TokenNavigationMixin` defines `_current` as a property. Mypy reports:

```
Cannot override writeable attribute "_current" in base "ExpressionParsingMixin"
with read-only property in base "TokenNavigationMixin"  [override]
```

**Resolution**: During Phase 1, remove the `_current: Token` declaration from `ExpressionParsingMixin`. The protocol's `_current` property provides the type information.

### 2. Existing Inline Pattern in ExpressionParsingMixin

**Current state**: `ExpressionParsingMixin` already uses inline TYPE_CHECKING declarations:

```python
# expressions.py:55-69 (current)
if TYPE_CHECKING:
    _current: Token  # ← REMOVE (causes override conflict)

    def _advance(self) -> Token: ...
    def _match(self, *types: TokenType) -> bool: ...
    def _expect(self, token_type: TokenType) -> Token: ...
    def _peek(self, offset: int = 0) -> Token: ...
    def _error(...) -> ParseError: ...
    def _parse_call_args(self) -> tuple[list[Expr], dict[str, Expr]]: ...
```

**Migration**: Convert to use `self: ParserCoreProtocol` annotation instead, keeping only non-protocol cross-mixin declarations (`_parse_call_args`).

---

## Implementation Plan

### Phase 0: Proof of Concept (Est. 30 min)

| Task | Files | Status |
|------|-------|--------|
| Create `ParserCoreProtocol` | `parser/_protocols.py` | 🔴 |
| Update `TokenNavigationMixin` | `parser/tokens.py` | 🔴 |
| Verify mypy passes | - | 🔴 |

**Success Gate**: `uv run mypy src/kida/parser/tokens.py --strict --config-file=""` passes.

### Phase 0.5: Validate Against Existing Pattern (Est. 30 min)

| Task | Files | Status |
|------|-------|--------|
| Test protocol with `ExpressionParsingMixin` | `parser/expressions.py` | 🔴 |
| Fix `_current` override conflict | `parser/expressions.py` | 🔴 |
| Verify hybrid approach works | - | 🔴 |

**Success Gate**: `ExpressionParsingMixin` compiles with protocol + remaining inline declarations.

**Rationale**: `ExpressionParsingMixin` already uses the inline pattern—test the protocol integration there first to validate the approach before converting other mixins.

### Phase 1: Parser Mixins (Est. 4-5 hours)

| Task | Files | Status |
|------|-------|--------|
| Update `StatementParsingMixin` | `parser/statements.py` | 🔴 |
| Update `ExpressionParsingMixin` | `parser/expressions.py` | 🔴 |
| Update `BlockStackMixin` | `parser/blocks/core.py` | 🔴 |
| Update all block parsing mixins | `parser/blocks/*.py` | 🔴 |
| Verify mypy passes for parser/ | - | 🔴 |

### Phase 2: Compiler Mixins (Est. 2-3 hours)

| Task | Files | Status |
|------|-------|--------|
| Create `CompilerCoreProtocol` | `compiler/_protocols.py` | 🔴 |
| Update all compiler mixins | `compiler/**/*.py` | 🔴 |
| Verify mypy passes for compiler/ | - | 🔴 |

### Phase 3: Cleanup (Est. 1 hour)

| Task | Files | Status |
|------|-------|--------|
| Remove pyproject.toml overrides | `pyproject.toml` | 🔴 |
| Update dependent RFCs | `plan/*.md` | 🔴 |
| Run full test suite | - | 🔴 |
| Verify remaining suppressions (see Non-Goals) | `pyproject.toml` | 🔴 |

**Total Estimated Time**: 8-10 hours

| Phase | Estimate | Notes |
|-------|----------|-------|
| Phase 0: POC | 30 min | Protocol creation + TokenNavigationMixin |
| Phase 0.5: Validate | 30 min | Test against existing ExpressionParsingMixin pattern |
| Phase 1: Parser | 4-5 hours | 6 mixin files, resolve override conflicts |
| Phase 2: Compiler | 2-3 hours | Similar pattern, fewer files |
| Phase 3: Cleanup | 1 hour | Remove suppressions, update docs, full test |

---

## Protocol Specifications

### ParserCoreProtocol

```python
class ParserCoreProtocol(Protocol):
    """Minimal cross-mixin contract for parser."""

    # Host Attributes
    _tokens: Sequence[Token]
    _pos: int
    _name: str | None
    _filename: str | None
    _source: str | None
    _autoescape: bool
    _block_stack: list[tuple[str, int, int]]

    # Token Navigation (used by all mixins)
    @property
    def _current(self) -> Token: ...
    def _peek(self, offset: int = 0) -> Token: ...
    def _advance(self) -> Token: ...
    def _expect(self, token_type: TokenType) -> Token: ...
    def _match(self, *types: TokenType) -> bool: ...
    def _error(
        self,
        message: str,
        token: Token | None = None,
        suggestion: str | None = None,
    ) -> ParseError: ...
    def _format_open_blocks(self) -> str: ...
```

### CompilerCoreProtocol

```python
class CompilerCoreProtocol(Protocol):
    """Minimal cross-mixin contract for compiler."""

    # Host Attributes
    _env: Environment
    _name: str | None
    _filename: str | None
    _locals: set[str]
    _blocks: dict[str, Any]
    _block_counter: int

    # Core compilation (used by all mixins)
    def _compile_expr(self, node: Any) -> ast.expr: ...
    def _compile_node(self, node: Any) -> list[ast.stmt]: ...

    # Operator utilities (used by expression compilation)
    def _get_binop(self, op: str) -> ast.operator: ...
    def _get_unaryop(self, op: str) -> ast.unaryop: ...
    def _get_cmpop(self, op: str) -> ast.cmpop: ...
```

---

## Example Transformations

### Before (Current)

```python
# kida/parser/statements.py
class StatementParsingMixin:
    """Mixin for parsing statements.

    Required Host Attributes:
        _tokens, _pos, _source, _filename, _autoescape, _block_stack

    Required Sibling Methods:
        _current, _advance, _expect, _match, _error (TokenNavigationMixin)
        _parse_expression (ExpressionParsingMixin)
        _parse_block_content, _push_block, _pop_block (BlockParsingMixin)
    """

    def _parse_body(self, stop_on_continuation: bool = False) -> list[Node]:
        body: list[Node] = []
        while not self._match(TokenType.EOF):  # ERROR: attr-defined
            token = self._current  # ERROR: attr-defined
            if token.type == TokenType.BLOCK_BEGIN:
                result = self._parse_block_content()  # ERROR: attr-defined
                # ...
        return body
```

### After (Hybrid Approach)

```python
# kida/parser/statements.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Node
    from kida.parser._protocols import ParserCoreProtocol


class StatementParsingMixin:
    """Mixin for parsing statements."""

    # Cross-mixin dependencies
    if TYPE_CHECKING:
        def _parse_expression(self) -> Expr: ...
        def _parse_block_content(self) -> Node | list[Node] | None: ...
        def _push_block(self, block_type: str, lineno: int, col: int) -> None: ...
        def _pop_block(self, expected_type: str | None = None) -> tuple[str, int, int]: ...

    def _parse_body(
        self: ParserCoreProtocol,  # ← Just the core protocol
        stop_on_continuation: bool = False,
    ) -> list[Node]:
        body: list[Node] = []
        while not self._match(TokenType.EOF):  # ✅ from core protocol
            token = self._current  # ✅ from core protocol
            if token.type == TokenType.BLOCK_BEGIN:
                result = self._parse_block_content()  # ✅ from inline declaration
                # ...
        return body
```

---

## Maintenance Burden Comparison

| Approach | Protocol Size | When Adding New Tag |
|----------|--------------|---------------------|
| **Monolithic Protocol** | ~75 methods | Add to protocol + implement |
| **Hybrid (this RFC)** | ~16 methods | Just implement (inline decl where needed) |

**Protocol changes only needed when**:
- Adding/changing host attributes (rare)
- Adding/changing token navigation methods (very rare)

**No protocol change needed when**:
- Adding new template tags (`{% cache %}`, `{% match %}`, etc.)
- Adding new expression operators
- Changing block parsing logic

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Inline declarations become stale | Low | Low | Mypy catches missing/wrong declarations |
| Core protocol becomes stale | Low | Medium | Only ~16 members; CI verifies Parser satisfies it |
| Circular imports | Low | High | All protocols in TYPE_CHECKING blocks |
| Performance regression | None | N/A | Protocols erased at runtime |
| Property/variable override conflicts | **Known** | Medium | Phase 0.5 validates; remove class var annotations |
| MRO complications | Low | Medium | Test thoroughly; Parser class order unchanged |

---

## Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| Suppressed error codes | 12 | 3 (non-mixin issues) |
| Individual errors masked | ~539 | ~25 (AST variance only) |
| Protocol members to maintain | 0 | ~16 (stable) |
| IDE autocomplete in mixins | ❌ | ✅ |
| Compile-time interface safety | ❌ | ✅ |
| Mixin dependency documentation | Docstrings (stale) | Inline declarations (verified) |

---

## Non-Goals

This RFC does **not** address:

1. **AST node type variance**: `arg-type` errors from `list[If]` vs `list[stmt]`
2. **Dynamic dispatch typing**: `no-any-return` from `getattr()` dispatch
3. **Compiler node type safety**: `Any` in `_compile_*` methods
4. **Generic type parameters**: `type-arg` error for `Callable` in `compiler/core.py`

**Expected remaining suppressions** after this RFC:

```toml
[[tool.mypy.overrides]]
module = ["kida.parser.*", "kida.compiler.*"]
disable_error_code = [
    "arg-type",       # AST node list variance (list[If] vs list[stmt])
    "no-any-return",  # Dynamic dispatch via getattr()
    "type-arg",       # Callable generic parameters
]
```

This reduces from 12 suppressed codes to 3, eliminating the mixin-related errors.

---

## Alternatives Considered

### A. Monolithic Protocol (Previous Version)

Single protocol with all ~75 method signatures.

**Rejected**: High maintenance burden. Every new template tag requires protocol update.

### B. No Protocol (Pure Inline)

Only inline declarations, no shared protocol.

**Rejected**: Too much duplication. Every mixin would redeclare `_tokens`, `_current`, `_advance`, etc. (16 members × N mixins = maintenance nightmare).

### C. Composition Over Inheritance

Replace mixins with composed helper classes.

**Rejected**: Major API change. Would break existing architecture.

### D. Accept Suppressions Permanently

Keep suppressions as "acceptable debt."

**Rejected**: 553 errors represent real refactoring risk.

---

## References

- [PEP 544 – Protocols: Structural subtyping](https://peps.python.org/pep-0544/)
- [mypy: Protocols and structural subtyping](https://mypy.readthedocs.io/en/stable/protocols.html)
- [Kida RFC: Type Suppression Reduction](rfc-type-suppression-reduction.md)

---

## Appendix A: Full Mixin Example (Leaf Mixin)

```python
# kida/parser/expressions.py
from __future__ import annotations

from typing import TYPE_CHECKING

from kida._types import Token, TokenType

if TYPE_CHECKING:
    from kida.nodes import Expr
    from kida.parser._protocols import ParserCoreProtocol


class ExpressionParsingMixin:
    """Mixin for parsing expressions.

    This is a "leaf" mixin—it only depends on the core protocol,
    not on other parsing mixins. No inline declarations needed.
    """

    # ─────────────────────────────────────────────────────────────
    # Cross-mixin dependencies
    # ─────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # Only non-protocol dependencies declared here
        # (ExpressionParsingMixin calls _parse_call_args from FunctionBlockParsingMixin)
        def _parse_call_args(self) -> tuple[list[Expr], dict[str, Expr]]: ...

    # NOTE: Do NOT declare _current, _advance, etc. here—they come from
    # the protocol via `self: ParserCoreProtocol` annotation. Declaring
    # them as class variables causes [override] errors with properties.

    def _parse_expression(self: ParserCoreProtocol) -> Expr:
        """Parse a full expression."""
        return self._parse_ternary()

    def _parse_ternary(self: ParserCoreProtocol) -> Expr:
        """Parse ternary: expr if condition else expr."""
        expr = self._parse_null_coalesce()

        if self._current.type == TokenType.NAME and self._current.value == "if":
            self._advance()  # ✅ from core protocol
            condition = self._parse_null_coalesce()
            self._expect_name("else")
            else_expr = self._parse_ternary()
            return CondExpr(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                test=condition,
                if_true=expr,
                if_false=else_expr,
            )

        return expr

    def _parse_primary(self: ParserCoreProtocol) -> Expr:
        """Parse primary expression (literals, names, grouped)."""
        token = self._current  # ✅ from core protocol

        if token.type == TokenType.INTEGER:
            self._advance()
            return Const(lineno=token.lineno, col_offset=token.col, value=int(token.value))

        if token.type == TokenType.NAME:
            self._advance()
            return Name(lineno=token.lineno, col_offset=token.col, id=token.value)

        if token.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()  # ✅ calls self (same mixin)
            self._expect(TokenType.RPAREN)  # ✅ from core protocol
            return expr

        raise self._error(f"Unexpected token: {token.value}")  # ✅ from core protocol

    # ... more expression parsing methods
```

## Appendix B: Migration Checklist Per Mixin

For each mixin file, follow this checklist:

- [ ] Add `from kida.parser._protocols import ParserCoreProtocol` in TYPE_CHECKING
- [ ] Remove any class-level attribute declarations that duplicate protocol members
- [ ] Add `self: ParserCoreProtocol` annotation to all public methods
- [ ] Add inline TYPE_CHECKING declarations for non-protocol cross-mixin calls
- [ ] Remove "Required Host Attributes" from docstring (now in protocol/inline)
- [ ] Run `uv run mypy <file> --strict --config-file=""` to verify
- [ ] Run tests: `uv run pytest tests/test_parser.py -x`

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-05 | Auto-generated | Initial draft |
| 2026-01-05 | Review | Corrected error counts; added Phase 0 POC |
| 2026-01-05 | Review | **Switched to hybrid approach**: minimal core protocol + inline declarations |
| 2026-01-05 | Review | Added Known Issues section (property/class var override conflict) |
| 2026-01-05 | Review | Added Phase 0.5 to validate against existing ExpressionParsingMixin pattern |
| 2026-01-05 | Review | Added `_format_open_blocks` to protocol; updated member count to ~16 |
| 2026-01-05 | Review | Updated time estimates (8-10 hours); added expected remaining suppressions |
| 2026-01-05 | Review | Added Appendix B: Migration Checklist Per Mixin |
