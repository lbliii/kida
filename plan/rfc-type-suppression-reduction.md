# RFC: Type Suppression Reduction

**Status**: Phase 1 Complete  
**Created**: 2026-01-04  
**Updated**: 2026-01-04  
**Depends On**: `rfc-type-checking-strategy.md` (Implemented)

---

## Summary

Incrementally reduce mypy error code suppressions from 38 to 9 (76% reduction). This RFC provides specific fixes for each module, ordered by complexity. Work is optional and can be done incrementally.

---

## Current State

After migrating from Pyright to mypy (see `rfc-type-checking-strategy.md`), the codebase passes type checking with per-module suppressions:

```bash
$ uv run mypy src/kida --show-error-codes
Success: no issues found in 51 source files
```

| Module | Codes Suppressed | Target | Status |
|--------|-----------------|--------|--------|
| `kida` | ~~1~~ 0 | 0 | ✅ Done |
| `kida.bytecode_cache` | ~~1~~ 0 | 0 | ✅ Done |
| `kida.analysis.*` | ~~2~~ 0 | 0 | ✅ Done |
| `kida.template` | 4 | 1 | 🟡 Medium |
| `kida.environment.*` | 6 | 2 | 🟡 Medium |
| `kida.parser.*` | 12 | 3 | 🔴 Major |
| `kida.compiler.*` | 12 | 3 | 🔴 Major |

**Total**: ~~38~~ 34 → 9 codes (Phase 1: -4 codes)

---

## Phase 1: Quick Wins (1-2 hours)

### 1.1 Fix `kida` Module (1 code → 0)

**Problem**: Conditional import with fallback assignment

```python
# src/kida/__init__.py:92-96
try:
    from kida.tstring import k
except ImportError:
    k = None  # assignment error: incompatible types
```

**Context**: `k` is a function `Callable[[string.templatelib.Template], str]` (see `tstring.py:14`).

**Fix**: Declare the type before the try/except block

```python
from collections.abc import Callable

# Declare type before conditional import
k: Callable[..., str] | None

try:
    from kida.tstring import k
except ImportError:
    k = None
```

**Verification**:
```bash
# Remove override from pyproject.toml:
# [[tool.mypy.overrides]]
# module = ["kida"]
# disable_error_code = ["assignment"]

uv run mypy src/kida/__init__.py --show-error-codes
```

---

### 1.2 Fix `kida.bytecode_cache` (1 code → 0)

**Problem**: `marshal.load()` returns `Any`

```python
# src/kida/bytecode_cache.py:119-120
try:
    with open(path, "rb") as f:
        return marshal.load(f)  # no-any-return
```

**Fix**: Add explicit cast

```python
from typing import cast
from types import CodeType

try:
    with open(path, "rb") as f:
        return cast(CodeType, marshal.load(f))
```

**Verification**:
```bash
# Remove override from pyproject.toml
uv run mypy src/kida/bytecode_cache.py --show-error-codes
```

---

### 1.3 Fix `kida.analysis.*` (2 codes → 0)

**Problem**: Dynamic type checks using `type(node).__name__` instead of `isinstance()`

```python
# src/kida/analysis/analyzer.py:97-98
if type(extends_expr).__name__ == "Const":
    extends = extends_expr.value  # attr-defined: "object" has no attribute "value"
```

**Pattern appears at**:
- `analyzer.py:97-98, 102-105, 154, 259-263`
- Similar patterns in `dependencies.py`, `purity.py`

**Fix**: Import and use actual node types (circular import verified safe)

```bash
# Verified: no circular import
$ python -c "from kida.nodes import Const; from kida.analysis.analyzer import BlockAnalyzer; print('OK')"
OK
```

```python
# src/kida/analysis/analyzer.py
# Move from TYPE_CHECKING to runtime import
from kida.nodes import Block, Const, Extends, Template

# Replace type name checks with isinstance
if isinstance(extends_expr, Const):
    extends = extends_expr.value

for node in ast.body:
    if isinstance(node, Extends):
        extends_expr = node.template
        if isinstance(extends_expr, Const):
            extends = extends_expr.value
        break
```

**Full list of replacements**:

| Location | Before | After |
|----------|--------|-------|
| `analyzer.py:97` | `type(extends_expr).__name__ == "Const"` | `isinstance(extends_expr, Const)` |
| `analyzer.py:102` | `type(node).__name__ == "Extends"` | `isinstance(node, Extends)` |
| `analyzer.py:104` | `type(extends_expr).__name__ == "Const"` | `isinstance(extends_expr, Const)` |
| `analyzer.py:154` | `type(node).__name__ == "Block"` | `isinstance(node, Block)` |
| `analyzer.py:259` | `type(node).__name__ == "Data"` | `isinstance(node, Data)` |
| `analyzer.py:261` | `type(node).__name__ == "Output"` | `isinstance(node, Output)` |

**Additional imports needed**:
```python
from kida.nodes import Block, Const, Data, Extends, Output, Template
```

**Verification**:
```bash
# Remove override from pyproject.toml
uv run mypy src/kida/analysis/ --show-error-codes
uv run pytest tests/test_analysis*.py -x  # Verify no runtime regressions
```

---

## Phase 2: Medium Effort (4-6 hours)

### 2.1 Fix `kida.template` (4 codes → 1)

**Current suppressions**: `type-arg`, `no-any-return`, `no-untyped-def`, `assignment`

| Code | Location | Fix |
|------|----------|-----|
| `type-arg` | `dict[str, Any]` patterns | Use `TypedDict` for known shapes |
| `no-any-return` | `_namespace.get()` | Add return type annotations |
| `no-untyped-def` | Helper functions | Add type annotations |
| `assignment` | `_metadata_cache` | Use `Optional` or `None` union |

**Specific fixes**:

1. **Type the namespace dict**:
```python
# Before
namespace: dict[str, Any] = {...}

# After (create TypedDict for common keys)
class TemplateNamespace(TypedDict, total=False):
    render: Callable[..., str]
    __builtins__: dict[str, object]
    # ... other known keys
```

2. **Type `_metadata_cache`**:
```python
# Before
self._metadata_cache: Any = None

# After
from kida.analysis.metadata import TemplateMetadata
self._metadata_cache: TemplateMetadata | None = None
```

3. **Add return types to nested functions**:
```python
# Before
def _include(template_name, context, ignore_missing=False, *, blocks=None):

# After
def _include(
    template_name: str, 
    context: dict[str, Any], 
    ignore_missing: bool = False, 
    *, 
    blocks: dict[str, Any] | None = None
) -> str:
```

**Target**: Reduce to 1 code (`type-arg` for truly dynamic dicts)

---

### 2.2 Fix `kida.environment.*` (6 codes → 2)

**Current suppressions**: `type-arg`, `no-any-return`, `return-value`, `arg-type`, `no-untyped-def`, `union-attr`

| Code | Typical Cause | Fix |
|------|---------------|-----|
| `type-arg` | `Callable[..., Any]` | Define function protocols |
| `no-any-return` | Dynamic filter dispatch | Use `@overload` or return `object` |
| `return-value` | List covariance | Use `Sequence` return types |
| `arg-type` | Context dict variations | Use `Mapping` for inputs |
| `no-untyped-def` | Missing annotations | Add annotations |
| `union-attr` | Optional access | Add null checks |

**Target**: Reduce to 2 codes (`type-arg` for filter/test signatures, `no-any-return` for dynamic dispatch)

---

## Phase 3: Major Effort (Future)

### 3.1 Parser & Compiler Mixin Patterns (12 codes each → 3)

The parser and compiler use cooperative multiple inheritance:

```python
class Parser(
    TokenNavigationMixin,      # Defines _current, _advance, _expect
    BlockParsingMixin,         # Uses _current, _advance
    StatementParsingMixin,     # Uses _current, _advance
    ExpressionParsingMixin,    # Uses _current, _advance
):
    pass
```

**Options**:

#### Option A: Protocol for Host Class Requirements

```python
from typing import Protocol

class ParserProtocol(Protocol):
    """Requirements that mixins expect from the host class."""
    _current: Token
    def _advance(self) -> Token: ...
    def _expect(self, tt: TokenType) -> Token: ...
    def _match(self, *types: TokenType) -> bool: ...

class StatementParsingMixin:
    # Type stub declares mixin implements protocol when combined
    _current: Token  # Declare expected attrs
    
    def _parse_if(self: ParserProtocol) -> If:
        # Now mypy knows self has _current, _advance, etc.
        ...
```

#### Option B: Generic Self Type (Python 3.11+)

```python
from typing import Self

class StatementParsingMixin:
    def _parse_if(self: Self) -> If:
        # Use TYPE_CHECKING block to define expected interface
        ...
```

#### Option C: Accept Remaining Suppressions (Recommended)

Keep 3 codes for genuine mixin patterns that can't be expressed:
- `attr-defined` — Mixin attribute access
- `no-any-return` — Dynamic parser dispatch
- `override` — Property/attribute conflicts

**Recommendation**: Option C for now. The mixin pattern works correctly at runtime, and adding Protocols would add significant boilerplate without runtime benefit. Revisit if mypy gains better mixin support.

---

## Implementation Plan

### Order of Implementation

```yaml
Phase 1 (Quick Wins) - 1-2 hours:
  - [x] 1.1: kida/__init__.py — Callable type annotation for k
  - [x] 1.2: bytecode_cache.py — cast(CodeType, marshal.load(f))
  - [x] 1.3: analysis/*.py — isinstance checks (6 replacements)
  - [x] 1.4: analysis/purity.py — cast for dynamic handler dispatch
  
Phase 2 (Medium) - 4-6 hours:
  - [ ] 2.1: template.py — TypedDict, function annotations
  - [ ] 2.2: environment/*.py — Callable protocols, Sequence returns

Phase 3 (Future) - Optional:
  - [ ] 3.1: parser/ — Evaluate Protocol adoption if needed
  - [ ] 3.2: compiler/ — Evaluate Protocol adoption if needed
```

### Verification Process

After each fix:

1. **Remove the override** from `pyproject.toml`
2. **Run mypy** on the specific module:
   ```bash
   uv run mypy src/kida/MODULE.py --show-error-codes
   ```
3. **Run full check**:
   ```bash
   uv run mypy src/kida --show-error-codes
   ```
4. **Run tests** to ensure no runtime regressions:
   ```bash
   uv run pytest tests/ -x
   ```
5. **If any phase fails**, re-add the override and document the issue

### Rollback Procedure

If a fix introduces regressions:

1. Revert the code change
2. Re-add the suppression to `pyproject.toml`
3. Document the specific error in the RFC for future reference
4. Continue with remaining fixes

---

## Success Criteria

| Metric | Before | After Phase 1 | After Phase 2 | Final Target |
|--------|--------|--------------|---------------|--------------|
| **Total Codes** | 38 | 34 | 25 | 9 |
| **Modules with Overrides** | 6 | 4 | 2 | 2 |
| **CI Status** | ✅ | ✅ | ✅ | ✅ |
| **Test Pass Rate** | 100% | 100% | 100% | 100% |

---

## Appendix A: Current pyproject.toml Overrides

```toml
# Parser & Compiler (12 codes each)
[[tool.mypy.overrides]]
module = ["kida.parser.*", "kida.compiler.*"]
disable_error_code = [
    "attr-defined", "no-any-return", "arg-type", "return-value",
    "assignment", "operator", "no-untyped-def", "no-redef",
    "call-arg", "func-returns-value", "override", "type-arg",
]

# Environment (6 codes)
[[tool.mypy.overrides]]
module = ["kida.environment.*"]
disable_error_code = [
    "type-arg", "no-any-return", "return-value", 
    "arg-type", "no-untyped-def", "union-attr",
]

# Template (4 codes)
[[tool.mypy.overrides]]
module = ["kida.template"]
disable_error_code = [
    "type-arg", "no-any-return", "no-untyped-def", "assignment",
]

# Analysis (2 codes)
[[tool.mypy.overrides]]
module = ["kida.analysis.*"]
disable_error_code = ["attr-defined", "no-any-return"]

# Bytecode cache (1 code)
[[tool.mypy.overrides]]
module = ["kida.bytecode_cache"]
disable_error_code = ["no-any-return"]

# Top-level init (1 code)
[[tool.mypy.overrides]]
module = ["kida"]
disable_error_code = ["assignment"]
```

---

## Appendix B: Node Types for Analysis Module

The following node types are used in `kida.analysis.analyzer` and need runtime imports:

| Node Type | Used At | Purpose |
|-----------|---------|---------|
| `Block` | Line 154 | Identify block nodes |
| `Const` | Lines 97, 104 | Check constant expressions |
| `Data` | Line 259 | Check raw text nodes |
| `Extends` | Line 102 | Identify extends statements |
| `Output` | Line 261 | Check expression output |
| `Template` | Type hints | Root AST node |

All are defined in `kida/nodes.py` with no external dependencies — safe for runtime import.

---

## References

- `plan/rfc-type-checking-strategy.md` — Original migration RFC
- [mypy: Protocols and structural subtyping](https://mypy.readthedocs.io/en/stable/protocols.html)
- [PEP 544: Protocols](https://peps.python.org/pep-0544/)
