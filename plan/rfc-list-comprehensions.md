# RFC: List Comprehensions in Kida

**Status**: Proposal  
**Author**: —  
**Created**: 2025-03-05

---

## Summary

Add list comprehension support to Kida's expression language. This enables presentation transformations directly in templates (e.g. shaping data for select components) without pushing logic to Python handlers.

---

## Kida Philosophy (Evidence from Codebase)

### 1. AST-Native, Structured

- **Source**: `architecture.md`, `compiler/core.py`
- Compiles to Python AST directly, not source strings
- Structured code manipulation, compile-time optimization, precise error mapping

### 2. Modern Syntax, Jinja-Inspired

- **Source**: `comparison.md`, `migrate-from-jinja2.md`, `variables.md`
- "Jinja2-compatible syntax with extensions"
- Adds: unified `{% end %}`, pipeline `|>`, pattern matching `{% match %}`, null coalescing `??`, optional chaining `?.`
- Variables doc: "Full Python expressions are supported" — but currently excludes comprehensions

### 3. Presentation Logic in Templates

- **Source**: `variables.md` — globals include `range`, `dict`, `list`, `map`, `filter`
- Templates already support `map` and `filter` for transforming iterables
- `{% for x in items if x.visible %}` — inline if filter shows Kida allows presentation-level filtering in templates

### 4. Bounded Expressiveness

- **Source**: `comparison.md` — "Limitations: Jinja2-specific extensions may not be available"
- Kida is opinionated: not a drop-in Jinja2 replacement
- Design principles: AST-native, free-threading ready, zero dependencies

### 5. Design Principles (Architecture)

- **Source**: `architecture.md`
- AST-Native: No string manipulation
- Free-Threading Ready: Idempotent compilation, local render state
- Zero Dependencies

---

## Rationale for List Comprehensions

1. **Fits existing philosophy**: `map` and `filter` are already available; comprehensions are a more readable, inline alternative for the same use case.

2. **Presentation transformation**: The motivating example — `[{"value": s, "label": s | capitalize} for s in style_options]` — is shaping data for a component. That's presentation logic, not business logic.

3. **Bounded scope**: Support list comprehensions only. No dict/set comprehensions or generator expressions unless demand arises.

4. **Parser alignment**: The list literal parser already sees `[`, parses the first expression, then expects `]` or `,`. The change: after the first expression, if the next token is `for` (NAME), treat as comprehension instead of expecting `]` or `,`.

5. **Python AST mapping**: `ast.ListComp` maps cleanly — `elt` (expression), `generators` (list of `comprehension` with `target`, `iter`, `ifs`).

---

## Proposed Syntax

```kida
{# List comprehension — same as Python #}
{% set opts = [{"value": s, "label": s | capitalize} for s in style_options] %}

{# With optional if clause #}
{% set visible = [x for x in items if x.visible] %}

{# Multiple fors (nested loops) — optional for v1 #}
{% set pairs = [(a, b) for a in xs for b in ys] %}
```

**Scope for initial implementation**:
- Single `for ... in ...` clause (required)
- Optional `if` clause (single condition)
- No nested `for` clauses in v1 (can add later)

---

## Implementation Plan

### 1. Parser (`kida/parser/expressions.py`)

In `_parse_primary()`, when handling `TokenType.LBRACKET`:

**Current** (lines 726–737):
```python
if token.type == TokenType.LBRACKET:
    self._advance()
    items = []
    if not self._match(TokenType.RBRACKET):
        items.append(self._parse_expression())
        while self._match(TokenType.COMMA):
            self._advance()
            if self._match(TokenType.RBRACKET):
                break
            items.append(self._parse_expression())
    self._expect(TokenType.RBRACKET)
    return List(token.lineno, token.col_offset, tuple(items))
```

**Change**: After parsing the first expression, check for `for` before expecting `]` or `,`:

```python
if token.type == TokenType.LBRACKET:
    self._advance()
    if self._match(TokenType.RBRACKET):
        self._advance()
        return List(token.lineno, token.col_offset, ())

    elt = self._parse_expression()

    # List comprehension: [expr for x in iterable if cond]
    if self._current.type == TokenType.NAME and self._current.value == "for":
        return self._parse_list_comprehension(token, elt)

    # List literal
    items = [elt]
    while self._match(TokenType.COMMA):
        self._advance()
        if self._match(TokenType.RBRACKET):
            break
        items.append(self._parse_expression())
    self._expect(TokenType.RBRACKET)
    return List(token.lineno, token.col_offset, tuple(items))
```

Add `_parse_list_comprehension(self, start_token, elt: Expr) -> ListComp`:
- Consume `for`
- Parse target via `_parse_for_target()` (reuse from control_flow)
- Expect `in`, parse iterable
- Optional: if `if` follows, parse condition
- Expect `]`
- Return new `ListComp` node

### 2. AST Node (`kida/nodes/expressions.py`)

```python
@dataclass(frozen=True, slots=True)
class ListComp(Expr):
    """List comprehension: [expr for x in iterable if cond]"""

    elt: Expr
    target: Expr      # loop variable or tuple
    iter: Expr
    ifs: Sequence[Expr] = ()  # optional conditions
```

### 3. Compiler (`kida/compiler/expressions.py`)

Add handler for `ListComp` → `ast.ListComp`:

```python
if isinstance(node, ListComp):
    return ast.ListComp(
        elt=self._compile_expr(node.elt),
        generators=[
            ast.comprehension(
                target=self._compile_expr(node.target, store=True),
                iter=self._compile_expr(node.iter),
                ifs=[self._compile_expr(c) for c in node.ifs],
                is_async=False,
            )
        ],
    )
```

### 4. Exports and Type Unions

- Add `ListComp` to `kida.nodes` exports
- Add to `AnyExpr` union in `nodes/expressions.py`

---

## Error Handling

- **K-PAR-001**: If `for` is present but syntax is invalid (e.g. missing `in`), use existing error machinery with suggestion: "List comprehensions use: [expr for x in iterable] or [expr for x in iterable if condition]"

---

## Documentation

Add to `site/content/docs/syntax/variables.md`:

```markdown
## List Comprehensions

Transform iterables inline for presentation:

```kida
{% set opts = [{"value": s, "label": s | capitalize} for s in style_options] %}
{% set visible = [x for x in items if x.visible] %}
```

Use for presentation transformations (shaping data for components). For business logic, keep transformations in Python.
```

---

## Out of Scope (v1)

- Dict comprehensions `{k: v for k, v in items}`
- Set comprehensions `{x for x in items}`
- Generator expressions `(x for x in items)`
- Nested `for` clauses `[x for a in as_ for x in a]`
- Async comprehensions

---

## Tests

- `[x for x in items]` — basic
- `[x | upper for x in items]` — with filter
- `[{"v": x, "l": x | capitalize} for x in items]` — dict in elt
- `[x for x in items if x]` — with if
- `[]` — empty list (unchanged)
- `[a, b, c]` — list literal (unchanged)
- Error: `[x for x]` — missing `in`
- Error: `[x for x in]` — missing iterable

---

## Changelog Entry

```markdown
### Added
- List comprehensions in expressions: `[expr for x in iterable]` and `[expr for x in iterable if condition]`
```
