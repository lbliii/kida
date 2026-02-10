# RFC: Typed Parameters for `{% def %}`

**Status**: Draft  
**Created**: 2026-02-10  
**Updated**: 2026-02-10  
**Related**: Gap Analysis — Kida/Chirp Strategic Plan  
**Priority**: P1 (foundational — unlocks contract validation and component library)

---

## Executive Summary

Kida's `{% def %}` supports positional args, defaults, `*args`, and `**kwargs` —
but parameters are untyped strings. A mistyped parameter name, a missing required
arg, or a wrong-type value all fail at render time. Meanwhile, Kida already
compiles to Python AST and already has the `TemplateContext` node for top-level
type declarations.

This RFC extends `{% def %}` to support optional type annotations on parameters.
The compiler propagates annotations into generated function signatures. A new
analysis pass validates `{% call %}` sites at compile time.

| Change | Scope | Effort |
|--------|-------|--------|
| Parser: annotation syntax in `{% def %}` | `parser/blocks/functions.py` | Medium |
| AST: typed params in `Def` node | `nodes.py` | Low |
| Compiler: annotations in generated functions | `compiler/statements/functions.py` | Medium |
| Analysis: call-site validation | `analysis/` (new pass) | Medium |

**No runtime cost** — all validation happens during compilation. Annotations are
optional — existing untyped `{% def %}` templates continue to work unchanged.

---

## Problem Statement

### Current State

`{% def %}` parameters are stored as bare strings in the `Def` node
(`src/kida/nodes.py:416-451`):

```python
@dataclass(frozen=True, slots=True)
class Def(Node):
    name: str
    args: Sequence[str]          # Just names — no types
    body: Sequence[Node]
    defaults: Sequence[Expr]
    vararg: str | None
    kwarg: str | None
```

The parser (`src/kida/parser/blocks/functions.py:60-152`) extracts parameter
names and default expressions, but has no syntax for annotations.

The compiler (`src/kida/compiler/statements/functions.py:40-268`) generates
Python `ast.arg` nodes with `arg.annotation = None`.

### What Breaks Today

```html
{# Define a card component #}
{% def card(title, items, footer=None) %}
    <div class="card">
        <h3>{{ title }}</h3>
        {% for item in items %}<p>{{ item }}</p>{% end %}
        {% if footer %}<footer>{{ footer }}</footer>{% end %}
    </div>
{% end %}

{# Typo in parameter name — fails at render time #}
{% call card(titl="oops", items=data) %}{% end %}

{# Missing required arg — fails at render time #}
{% call card(items=data) %}{% end %}
```

Both errors produce a runtime `TypeError` or `UndefinedError` when the template
is rendered — not when it is compiled. In production, this means the error is
discovered by a user, not by the developer or CI pipeline.

### What Ludic Gets Right

Ludic catches structural errors at type-check time via `TypeVarTuple` and
`TypedDict`. A component like `Component[str, CardAttrs]` enforces child types
and attribute types through Python's type system.

Kida cannot replicate this exactly (templates are not Python source), but it
*can* validate call sites at compile time — because the compiler already has
the full AST of both the definition and all call sites within the same template
or include tree.

---

## Proposed Design

### Syntax

Type annotations follow Python syntax after the parameter name:

```html
{% def card(title: str, items: list, footer: str | None = None) %}
    ...
{% end %}
```

Annotations are optional per-parameter. A `{% def %}` can mix typed and untyped
params:

```html
{% def mixed(name: str, options, count: int = 0) %}
    ...
{% end %}
```

Supported annotation syntax:

| Syntax | Meaning |
|--------|---------|
| `x: str` | Simple type |
| `x: int` | Simple type |
| `x: list` | Generic without params |
| `x: str \| None` | Union (PEP 604 style) |
| `x: MyModel` | Resolved from context at compile time |

Annotations are **documentation and validation hints**, not enforced at runtime.
The template engine does not import Python types or perform `isinstance` checks.
The value of annotations is:

1. **Compile-time call-site validation** — wrong parameter names caught immediately
2. **IDE support** — annotations flow into generated Python, enabling autocomplete
3. **Contract validation** — Chirp's `app.check()` can cross-reference form fields
   with typed parameters (see Gap 6 RFC)

### AST Changes

Extend the `Def` node to carry annotations:

```python
@dataclass(frozen=True, slots=True)
class DefParam(Node):
    """A single parameter in a {% def %} with optional type annotation."""
    name: str
    annotation: str | None = None   # Raw annotation text, e.g. "str | None"

@dataclass(frozen=True, slots=True)
class Def(Node):
    name: str
    params: Sequence[DefParam]      # Replaces args: Sequence[str]
    body: Sequence[Node]
    defaults: Sequence[Expr]
    vararg: str | None
    kwarg: str | None
```

The `DefParam` stores the raw annotation string. The compiler can optionally
parse it into a Python AST annotation node, but the primary consumer is the
analysis pass which works with string matching.

### Parser Changes

In `src/kida/parser/blocks/functions.py:86-134`, extend parameter parsing to
look for `: <type>` after the parameter name:

```
param := NAME [ ':' type_expr ] [ '=' default_expr ]
type_expr := NAME [ '|' NAME ]* [ '[' type_expr [ ',' type_expr ]* ']' ]
```

The type expression parser is deliberately simple — it handles `str`, `int`,
`list`, `str | None`, and `dict[str, int]` but not arbitrary Python expressions.
This keeps the template language clean while covering the practical cases.

### Compiler Changes

In `src/kida/compiler/statements/functions.py:40-268`, when building
`ast.arguments`:

```python
# Current (line 62):
args=[ast.arg(arg=name) for name in node.args]

# Proposed:
args=[
    ast.arg(
        arg=param.name,
        annotation=_parse_annotation(param.annotation) if param.annotation else None,
    )
    for param in node.params
]
```

The `_parse_annotation()` helper converts the annotation string to a Python AST
node using `ast.parse(annotation, mode='eval').body`. This is safe because
annotations are parsed from template source, not user input.

### Analysis Pass: Call-Site Validation

A new analysis pass validates `{% call %}` sites against `{% def %}` signatures.

**What it checks:**

1. **Unknown parameters**: `{% call card(titl="x") %}` — `titl` is not a param
2. **Missing required parameters**: `{% call card(items=data) %}` — `title` missing
3. **Duplicate parameters**: `{% call card(title="a", title="b") %}`

**What it does NOT check:**

1. Type compatibility (would require runtime type info)
2. Cross-template calls (only within the same compilation unit)
3. Dynamic calls (`{% call variable_name(...) %}`)

**Implementation**: Add a `validate_calls()` method to `BlockAnalyzer`
(`src/kida/analysis/analyzer.py`) that:

1. Collects all `Def` nodes and their parameter signatures
2. Walks the AST for `CallBlock` nodes
3. Matches call arguments against the definition's signature
4. Reports `CompilationWarning` for mismatches

This runs during `Environment.compile()` when strict mode is enabled, or on
demand via `Environment.analyze()`.

---

## Migration

### Backward Compatibility

Fully backward-compatible. The annotation syntax is optional — `{% def card(title) %}`
continues to work exactly as before. The `Def` node change from `args: Sequence[str]`
to `params: Sequence[DefParam]` requires a minor update to any code that reads
`Def.args` directly:

```python
# Before:
for name in def_node.args: ...

# After:
for param in def_node.params: ...
name = param.name
```

### Deprecation

`Def.args` can be preserved as a computed property for one release cycle:

```python
@property
def args(self) -> Sequence[str]:
    return tuple(p.name for p in self.params)
```

---

## Testing Strategy

1. **Parser tests**: Verify annotations are parsed correctly for all supported
   syntax variants (simple, union, generic, mixed typed/untyped)
2. **Compiler tests**: Verify generated Python functions have correct annotations
3. **Analysis tests**: Verify call-site validation catches unknown params,
   missing required params, and duplicate params
4. **Backward compat tests**: Verify all existing untyped `{% def %}` templates
   compile and render identically
5. **Round-trip tests**: Verify AST → compile → render preserves behavior

---

## Future Considerations

1. **Cross-template validation**: When `{% from "components/card.html" import card %}`,
   validate calls against the imported definition. Requires inter-template analysis.
2. **Type narrowing**: `{% if item is string %}` could narrow the type within the
   block for analysis purposes.
3. **IDE integration**: LSP server could provide autocomplete for typed parameters.
4. **Chirp contract integration**: `app.check()` could validate that route context
   variables match `{% template %}` declarations (see Gap 6 RFC).
