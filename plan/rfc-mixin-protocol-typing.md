# RFC: Type-Safe Mixin Patterns via Protocol + Self

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Created** | 2026-01-05 |
| **Author** | Auto-generated |
| **Depends On** | rfc-type-suppression-reduction.md (Phase 3) |
| **Target** | Python 3.14+ |

---

## Executive Summary

This RFC proposes converting Kida's parser and compiler mixins from runtime-only patterns to fully type-safe implementations using `typing.Protocol` and `typing.Self`. This eliminates the remaining 12 mypy error code suppressions while preserving the clean separation of concerns the mixin architecture provides.

**Key Outcome**: Remove all `[[tool.mypy.overrides]]` for parser/compiler modules.

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

Currently suppressing **12 error codes** across `kida.parser.*` and `kida.compiler.*`:

| Code | Count | Root Cause |
|------|-------|------------|
| `attr-defined` | ~60 | Mixin accesses host/sibling attributes |
| `no-any-return` | ~10 | Dynamic dispatch (`getattr`) returns `Any` |
| `arg-type` | ~8 | AST node type variance (`list[If]` vs `list[stmt]`) |
| `return-value` | ~5 | List invariance issues |
| `assignment` | ~5 | AST node reassignment |
| `operator` | ~3 | List concatenation type issues |
| `no-untyped-def` | ~3 | Missing annotations on dynamic helpers |
| `no-redef` | ~2 | Overloaded method patterns |
| `call-arg` | ~2 | Constructor signature variance |
| `func-returns-value` | ~1 | Optional return handling |
| `override` | ~1 | Property vs attribute in mixins |
| `type-arg` | ~1 | Callable generic parameters |

**Total**: ~100 individual errors masked by suppressions.

### Why This Matters

1. **No compile-time safety**: Interface drift between mixins and host is undetected
2. **IDE limitations**: No autocomplete or go-to-definition for cross-mixin calls
3. **Refactoring risk**: Renaming/removing attributes won't flag dependent mixins
4. **Documentation drift**: "Required Host Attributes" docstrings can become stale

---

## Proposed Solution

### Protocol + Self Pattern

Define explicit protocols that capture the contract between mixins and their host class:

```python
# kida/parser/_protocols.py
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from kida._types import Token, TokenType

if TYPE_CHECKING:
    from kida.nodes import Expr, Node
    from kida.parser.errors import ParseError


class ParserProtocol(Protocol):
    """Contract for parser mixins.
    
    Defines all attributes and methods that mixins may access from the host
    class or sibling mixins. Mypy verifies the final Parser class satisfies
    this protocol structurally.
    """
    
    # === Host Attributes ===
    _tokens: Sequence[Token]
    _pos: int
    _name: str | None
    _filename: str | None
    _source: str | None
    _autoescape: bool
    _block_stack: list[tuple[str, int, int]]
    
    # === TokenNavigationMixin ===
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
    
    # === ExpressionParsingMixin ===
    def _parse_expression(self) -> Expr: ...
    def _parse_primary(self) -> Expr: ...
    
    # === StatementParsingMixin ===
    def _parse_body(self, stop_on_continuation: bool = False) -> list[Node]: ...
    def _parse_block_content(self) -> Node | list[Node] | None: ...
    
    # === BlockParsingMixin ===
    def _push_block(self, block_type: str, lineno: int, col: int) -> None: ...
    def _pop_block(self, expected_type: str | None = None) -> tuple[str, int, int]: ...
    def _format_open_blocks(self) -> str: ...
```

Then update mixin signatures to use `Self` bounded by the protocol:

```python
# kida/parser/tokens.py
from __future__ import annotations

from typing import TYPE_CHECKING

from kida._types import Token, TokenType

if TYPE_CHECKING:
    from kida.parser._protocols import ParserProtocol
    from kida.parser.errors import ParseError


class TokenNavigationMixin:
    """Mixin providing token stream navigation methods."""

    @property
    def _current(self: ParserProtocol) -> Token:
        """Get current token."""
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return Token(TokenType.EOF, "", 0, 0)

    def _peek(self: ParserProtocol, offset: int = 0) -> Token:
        """Peek at token at offset from current position."""
        pos = self._pos + offset
        if pos < len(self._tokens):
            return self._tokens[pos]
        return Token(TokenType.EOF, "", 0, 0)

    def _advance(self: ParserProtocol) -> Token:
        """Advance to next token and return current."""
        token = self._current
        self._pos += 1
        return token
    
    # ... etc
```

### Key Design Decisions

#### 1. Single Protocol per Domain

One protocol for parser mixins, one for compiler mixins. This keeps the contract cohesive and avoids protocol fragmentation.

```
ParserProtocol    → All parser mixins
CompilerProtocol  → All compiler mixins
```

#### 2. Protocol in TYPE_CHECKING Block

Protocols are only needed at type-check time, not runtime:

```python
if TYPE_CHECKING:
    from kida.parser._protocols import ParserProtocol
```

This avoids circular imports and keeps runtime overhead at zero.

#### 3. Self-Type Pattern

Using `self: ParserProtocol` on mixin methods tells mypy "this method will only be called on objects that satisfy ParserProtocol":

```python
def _advance(self: ParserProtocol) -> Token:
    # mypy knows self._pos exists and is int
    # mypy knows self._tokens exists and is Sequence[Token]
    token = self._current  # mypy knows this returns Token
    self._pos += 1
    return token
```

#### 4. Structural Typing

Python protocols are structural (duck-typed), not nominal. The `Parser` class doesn't need to explicitly inherit from `ParserProtocol`—mypy verifies compatibility structurally.

---

## Implementation Plan

### Phase 1: Parser Protocols (Est. 2 hours)

| Task | Files | Status |
|------|-------|--------|
| Create `ParserProtocol` | `parser/_protocols.py` | 🔴 |
| Update `TokenNavigationMixin` | `parser/tokens.py` | 🔴 |
| Update `StatementParsingMixin` | `parser/statements.py` | 🔴 |
| Update `ExpressionParsingMixin` | `parser/expressions.py` | 🔴 |
| Update `BlockParsingMixin` | `parser/blocks/*.py` | 🔴 |
| Verify mypy passes | - | 🔴 |

### Phase 2: Compiler Protocols (Est. 2 hours)

| Task | Files | Status |
|------|-------|--------|
| Create `CompilerProtocol` | `compiler/_protocols.py` | 🔴 |
| Update `OperatorUtilsMixin` | `compiler/utils.py` | 🔴 |
| Update `ExpressionCompilationMixin` | `compiler/expressions.py` | 🔴 |
| Update `StatementCompilationMixin` | `compiler/statements/*.py` | 🔴 |
| Verify mypy passes | - | 🔴 |

### Phase 3: Cleanup (Est. 30 min)

| Task | Files | Status |
|------|-------|--------|
| Remove pyproject.toml overrides | `pyproject.toml` | 🔴 |
| Update RFC status | `plan/rfc-type-suppression-reduction.md` | 🔴 |
| Run full test suite | - | 🔴 |

---

## Protocol Specifications

### ParserProtocol

```python
class ParserProtocol(Protocol):
    """Complete contract for parser mixins."""
    
    # ─────────────────────────────────────────────────────────────────────────
    # Host Class Attributes (defined in Parser.__init__)
    # ─────────────────────────────────────────────────────────────────────────
    _tokens: Sequence[Token]
    _pos: int
    _name: str | None
    _filename: str | None
    _source: str | None
    _autoescape: bool
    _block_stack: list[tuple[str, int, int]]
    
    # ─────────────────────────────────────────────────────────────────────────
    # TokenNavigationMixin Methods
    # ─────────────────────────────────────────────────────────────────────────
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
    
    # ─────────────────────────────────────────────────────────────────────────
    # ExpressionParsingMixin Methods
    # ─────────────────────────────────────────────────────────────────────────
    def _parse_expression(self) -> Expr: ...
    def _parse_ternary(self) -> Expr: ...
    def _parse_null_coalesce(self) -> Expr: ...
    def _parse_or(self) -> Expr: ...
    def _parse_and(self) -> Expr: ...
    def _parse_not(self) -> Expr: ...
    def _parse_comparison(self) -> Expr: ...
    def _parse_range(self) -> Expr: ...
    def _parse_concat(self) -> Expr: ...
    def _parse_additive(self) -> Expr: ...
    def _parse_multiplicative(self) -> Expr: ...
    def _parse_power(self) -> Expr: ...
    def _parse_unary(self) -> Expr: ...
    def _parse_postfix(self) -> Expr: ...
    def _parse_primary(self) -> Expr: ...
    def _parse_list(self) -> Expr: ...
    def _parse_dict(self) -> Expr: ...
    def _parse_filter_chain(self, expr: Expr) -> Expr: ...
    def _parse_test(self, expr: Expr) -> Expr: ...
    def _parse_arguments(self) -> tuple[list[Expr], dict[str, Expr]]: ...
    
    # ─────────────────────────────────────────────────────────────────────────
    # StatementParsingMixin Methods
    # ─────────────────────────────────────────────────────────────────────────
    def _parse_body(self, stop_on_continuation: bool = False) -> list[Node]: ...
    def _parse_data(self) -> Data: ...
    def _parse_output(self) -> Output: ...
    def _parse_block(self) -> Node | list[Node] | None: ...
    def _parse_block_content(self) -> Node | list[Node] | None: ...
    def _skip_comment(self) -> None: ...
    
    # ─────────────────────────────────────────────────────────────────────────
    # BlockParsingMixin Methods  
    # ─────────────────────────────────────────────────────────────────────────
    def _push_block(self, block_type: str, lineno: int, col: int) -> None: ...
    def _pop_block(self, expected_type: str | None = None) -> tuple[str, int, int]: ...
    def _peek_block(self) -> tuple[str, int, int] | None: ...
    def _format_open_blocks(self) -> str: ...
    def _consume_end_tag(self) -> None: ...
    def _get_eof_error_suggestion(self) -> str | None: ...
    
    # Block parsing methods (from blocks/*.py)
    def _parse_if(self) -> If: ...
    def _parse_unless(self) -> If: ...
    def _parse_for(self) -> For: ...
    def _parse_while(self) -> While: ...
    def _parse_set(self) -> Node | list[Node]: ...
    def _parse_let(self) -> Let: ...
    def _parse_export(self) -> Export: ...
    def _parse_block_tag(self) -> Block: ...
    def _parse_extends(self) -> Extends: ...
    def _parse_include(self) -> Include: ...
    def _parse_import(self) -> Import: ...
    def _parse_from_import(self) -> FromImport: ...
    def _parse_with(self) -> With: ...
    def _parse_do(self) -> Do: ...
    def _parse_raw(self) -> Raw: ...
    def _parse_def(self) -> Def: ...
    def _parse_call(self) -> CallBlock: ...
    def _parse_capture(self) -> Capture: ...
    def _parse_cache(self) -> Cache: ...
    def _parse_filter_block(self) -> FilterBlock: ...
    def _parse_slot(self) -> Slot: ...
    def _parse_match(self) -> Match: ...
    def _parse_spaceless(self) -> Spaceless: ...
    def _parse_embed(self) -> Embed: ...
    def _parse_break(self) -> Break: ...
    def _parse_continue(self) -> Continue: ...
```

### CompilerProtocol

```python
class CompilerProtocol(Protocol):
    """Complete contract for compiler mixins."""
    
    # ─────────────────────────────────────────────────────────────────────────
    # Host Class Attributes (defined in Compiler.__init__)
    # ─────────────────────────────────────────────────────────────────────────
    _env: Environment
    _name: str | None
    _filename: str | None
    _locals: set[str]
    _blocks: dict[str, Any]
    _block_counter: int
    
    # ─────────────────────────────────────────────────────────────────────────
    # OperatorUtilsMixin Methods
    # ─────────────────────────────────────────────────────────────────────────
    def _get_binop(self, op: str) -> ast.operator: ...
    def _get_unaryop(self, op: str) -> ast.unaryop: ...
    def _get_cmpop(self, op: str) -> ast.cmpop: ...
    
    # ─────────────────────────────────────────────────────────────────────────
    # ExpressionCompilationMixin Methods
    # ─────────────────────────────────────────────────────────────────────────
    def _compile_expr(self, node: Any) -> ast.expr: ...
    def _wrap_coerce_numeric(self, expr: ast.expr) -> ast.expr: ...
    def _is_potentially_string(self, node: Any) -> bool: ...
    def _get_filter_suggestion(self, name: str) -> str | None: ...
    def _get_test_suggestion(self, name: str) -> str | None: ...
    
    # ─────────────────────────────────────────────────────────────────────────
    # StatementCompilationMixin Methods
    # ─────────────────────────────────────────────────────────────────────────
    def _compile_node(self, node: Any) -> list[ast.stmt]: ...
    def _compile_data(self, node: Any) -> list[ast.stmt]: ...
    def _compile_output(self, node: Any) -> list[ast.stmt]: ...
    def _compile_if(self, node: Any) -> list[ast.stmt]: ...
    def _compile_for(self, node: Any) -> list[ast.stmt]: ...
    def _compile_while(self, node: Any) -> list[ast.stmt]: ...
    def _compile_match(self, node: Any) -> list[ast.stmt]: ...
    def _compile_set(self, node: Any) -> list[ast.stmt]: ...
    def _compile_let(self, node: Any) -> list[ast.stmt]: ...
    def _compile_export(self, node: Any) -> list[ast.stmt]: ...
    def _compile_import(self, node: Any) -> list[ast.stmt]: ...
    def _compile_include(self, node: Any) -> list[ast.stmt]: ...
    def _compile_block(self, node: Any) -> list[ast.stmt]: ...
    def _compile_def(self, node: Any) -> list[ast.stmt]: ...
    def _compile_call_block(self, node: Any) -> list[ast.stmt]: ...
    def _compile_slot(self, node: Any) -> list[ast.stmt]: ...
    def _compile_from_import(self, node: Any) -> list[ast.stmt]: ...
    def _compile_with(self, node: Any) -> list[ast.stmt]: ...
    def _compile_with_conditional(self, node: Any) -> list[ast.stmt]: ...
    def _compile_do(self, node: Any) -> list[ast.stmt]: ...
    def _compile_raw(self, node: Any) -> list[ast.stmt]: ...
    def _compile_capture(self, node: Any) -> list[ast.stmt]: ...
    def _compile_cache(self, node: Any) -> list[ast.stmt]: ...
    def _compile_filter_block(self, node: Any) -> list[ast.stmt]: ...
    def _compile_break(self, node: Any) -> list[ast.stmt]: ...
    def _compile_continue(self, node: Any) -> list[ast.stmt]: ...
    def _compile_spaceless(self, node: Any) -> list[ast.stmt]: ...
    def _compile_embed(self, node: Any) -> list[ast.stmt]: ...
```

---

## Migration Strategy

### Step-by-Step for Each Mixin

1. **Add protocol import** (TYPE_CHECKING only):
   ```python
   if TYPE_CHECKING:
       from kida.parser._protocols import ParserProtocol
   ```

2. **Update method signatures** with `self: ParserProtocol`:
   ```python
   def _advance(self: ParserProtocol) -> Token:
   ```

3. **Run mypy** on that file to verify
4. **Repeat** for next mixin

### Verification Commands

```bash
# Test single file
uv run mypy src/kida/parser/tokens.py --strict

# Test all parser files
uv run mypy src/kida/parser/ --strict

# Test full project (final verification)
uv run mypy src/kida/ --strict
```

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Protocol becomes stale | Medium | Medium | CI enforces mypy strict; protocol drift = build failure |
| Circular imports | Low | High | Protocol in `_protocols.py` with TYPE_CHECKING imports |
| Performance regression | None | N/A | Protocols are erased at runtime |
| Large diff size | Certain | Low | Mechanical changes; easy to review |

---

## Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| Suppressed error codes | 12 | 0 |
| Modules with overrides | 2 (`parser.*`, `compiler.*`) | 0 |
| IDE autocomplete in mixins | ❌ | ✅ |
| Compile-time interface safety | ❌ | ✅ |

---

## Alternatives Considered

### A. Composition Over Inheritance

Replace mixins with composed helper classes that receive explicit dependencies.

**Rejected**: Would require major API changes and increase verbosity (`self.nav.current` vs `self._current`).

### B. Abstract Base Classes

Define abstract methods that subclasses must implement.

**Rejected**: ABCs require explicit inheritance; protocols are structural and more flexible.

### C. Accept Suppressions Permanently

Keep the 12 error code suppressions as "acceptable technical debt."

**Rejected**: Misses opportunity for full type safety now that Python 3.14 supports all required features.

---

## References

- [PEP 544 – Protocols: Structural subtyping](https://peps.python.org/pep-0544/)
- [PEP 673 – Self Type](https://peps.python.org/pep-0673/)
- [mypy: Protocols and structural subtyping](https://mypy.readthedocs.io/en/stable/protocols.html)
- [Kida RFC: Type Suppression Reduction](rfc-type-suppression-reduction.md)

---

## Appendix: Example Transformation

### Before (Current)

```python
# kida/parser/tokens.py
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
        """Get current token."""
        if self._pos < len(self._tokens):  # ERROR: attr-defined
            return self._tokens[self._pos]  # ERROR: attr-defined
        return Token(TokenType.EOF, "", 0, 0)

    def _error(
        self,
        message: str,
        token: Token | None = None,
        suggestion: str | None = None,
    ) -> ParseError:
        from kida.parser.errors import ParseError

        full_message = message
        if hasattr(self, "_block_stack") and self._block_stack:  # ERROR: attr-defined
            full_message = f"{message}\n\n{self._format_open_blocks()}"  # ERROR: attr-defined

        return ParseError(
            message=full_message,
            token=token or self._current,
            source=self._source,  # ERROR: attr-defined
            filename=self._filename,  # ERROR: attr-defined
            suggestion=suggestion,
        )
```

### After (With Protocol)

```python
# kida/parser/tokens.py
from __future__ import annotations

from typing import TYPE_CHECKING

from kida._types import Token, TokenType

if TYPE_CHECKING:
    from kida.parser._protocols import ParserProtocol
    from kida.parser.errors import ParseError


class TokenNavigationMixin:
    """Mixin providing token stream navigation methods."""

    @property
    def _current(self: ParserProtocol) -> Token:
        """Get current token."""
        if self._pos < len(self._tokens):  # ✅ mypy knows _pos: int, _tokens: Sequence[Token]
            return self._tokens[self._pos]
        return Token(TokenType.EOF, "", 0, 0)

    def _error(
        self: ParserProtocol,
        message: str,
        token: Token | None = None,
        suggestion: str | None = None,
    ) -> ParseError:
        from kida.parser.errors import ParseError

        full_message = message
        if self._block_stack:  # ✅ mypy knows _block_stack exists
            full_message = f"{message}\n\n{self._format_open_blocks()}"  # ✅ method in protocol

        return ParseError(
            message=full_message,
            token=token or self._current,
            source=self._source,  # ✅ mypy knows _source: str | None
            filename=self._filename,  # ✅ mypy knows _filename: str | None
            suggestion=suggestion,
        )
```

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-05 | Auto-generated | Initial draft |

