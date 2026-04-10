# Epic: Template Framework Composition Gaps

**Status**: Draft
**Created**: 2026-04-09
**Priority**: P1 (positioning — these are the gaps between "template engine" and "template framework")
**Affects**: kida core, downstream consumers

---

## Problem Statement

Kida has the composition primitives to position itself as a full template framework — named slots, provide/consume, explicit scoping, push/stack portals. But three gaps remain between what Kida offers and what modern component frameworks (Svelte, Vue, React) provide:

1. **No scoped slots** — a child component cannot expose per-iteration or per-item data to its slot consumer. Workaround: `provide`/`consume`, but it's indirect and verbose compared to Svelte's `let:item` or Vue's `#default="{ item }"`.

2. **No error boundaries** — if any nested component throws during render, the entire template fails. No way to degrade gracefully or render fallback content. Neither Jinja2 nor any Python template engine has this, but React's `<ErrorBoundary>` proved it matters for production robustness.

3. **No i18n** — no `{% trans %}` tag, no gettext integration, no message extraction. This is table stakes for any framework-level tool used internationally. Jinja2 ships an i18n extension; Django templates have `{% blocktrans %}`.

### Evidence

| Gap | Impact | Who hits it |
|-----|--------|-------------|
| Scoped slots | Forces `provide`/`consume` boilerplate for every list/table/iterator component | Component library authors |
| Error boundaries | Single bad variable crashes entire page render | Production apps with user-generated or external data |
| i18n | Must pre-translate all strings at application level | Any non-English deployment |

---

## Invariants

1. **Zero runtime dependencies stays zero** — all three features are pure Python, no new deps
2. **Existing templates never break** — all changes are additive syntax; no existing behavior changes
3. **Compile-time optimization still applies** — new constructs participate in constant folding and dead code elimination where applicable

---

## Sprint Overview

| Sprint | Title | Ships Independently? | Acceptance |
|--------|-------|---------------------|------------|
| 0 | Design & RFC | Yes (paper only) | Three RFCs with syntax proposals, compiler strategy, test plans |
| 1 | Scoped Slots | Yes | `{% slot items let:item %}` works in tests; caller exposes data to slot consumer |
| 2 | Error Boundaries | Yes | `{% try %}...{% fallback %}` catches render errors; streaming mode handled |
| 3 | i18n Foundation | Yes | `{% trans %}` / `ngettext` works with configurable gettext backend; message extraction CLI |

---

## Sprint 0: Design & RFC (Paper Only)

### Goal
Solve the hard design questions before writing code.

### Tasks

#### 0.1 — Scoped Slot Syntax Design

Two viable approaches:

**Option A: `let:` bindings on slot blocks (Svelte-style)**
```kida
{# Component definition #}
{% def data_list(items) %}
  <ul>
  {% for item in items %}
    {% slot row let:item=item, let:index=loop.index %}
      <li>{{ item }}</li>  {# default content #}
    {% end %}
  {% end %}
  </ul>
{% end %}

{# Call site #}
{% call data_list(users) %}
  {% slot row let:item, let:index %}
    <li class="{{ 'odd' if index is odd }}">{{ item.name }}</li>
  {% end %}
{% end %}
```

**Option B: Extend `caller()` with keyword arguments**
```kida
{# Component definition — calls caller with kwargs #}
{% def data_list(items) %}
  <ul>
  {% for item in items %}
    {{ caller(item=item, index=loop.index) }}
  {% end %}
  </ul>
{% end %}

{# Call site — slot body receives kwargs as locals #}
{% call data_list(users) with item, index %}
  <li class="{{ 'odd' if index is odd }}">{{ item.name }}</li>
{% end %}
```

**Decision criteria**:
- Option A is more explicit and self-documenting but adds parser complexity
- Option B reuses existing `caller()` machinery but requires new `with` clause on `{% call %}`
- Both need the slot function signature to accept `**kwargs` and merge into scope

**Recommendation**: Option A. The `let:` syntax makes data flow visible at both the def site (what's exposed) and the call site (what's consumed). This matches Kida's philosophy of explicit over implicit.

#### 0.2 — Error Boundary Semantics

Key design questions:

1. **Scope**: What exceptions are caught?
   - Recommendation: `TemplateRuntimeError` and subclasses only. `TemplateSyntaxError` is a compile-time error and should never be caught at render time. Python-level `TypeError`/`ValueError` from filters should be caught (they indicate bad data, not bad templates).

2. **Streaming**: `render_stream()` yields chunks progressively — can't un-yield on error.
   - Recommendation: Buffer the `{% try %}` body. If it completes, flush to output. If it throws, discard buffer and render fallback. This means try blocks opt out of streaming for their body (acceptable tradeoff — error boundaries are for risky subtrees, not entire pages).

3. **Error exposure**: Should the fallback body have access to the error?
   - Recommendation: Yes. `{{ error.message }}` and `{{ error.template }}` available in fallback scope via `{% set %}`.

4. **Nesting**: Try blocks inside try blocks.
   - Recommendation: Each try block is independent. Inner try catches first; if inner fallback also throws, outer try catches.

Proposed syntax:
```kida
{% try %}
  {{ render_user_widget(user) }}
{% fallback %}
  <div class="error">Widget unavailable</div>
{% end %}

{# With error access #}
{% try %}
  {{ dangerous_component() }}
{% fallback error %}
  <div class="error">Failed: {{ error.message }}</div>
{% end %}
```

#### 0.3 — i18n Architecture

Design questions:

1. **Backend**: Pluggable gettext-compatible interface or opinionated?
   - Recommendation: Pluggable. `env.install_translations(gettext_func, ngettext_func)`. Supports stdlib `gettext`, Babel, or custom backends.

2. **Extraction**: How to extract translatable strings?
   - Recommendation: AST visitor in `kida/analysis/` (follows existing pattern). CLI: `kida extract-messages templates/ > messages.pot`. Also provide a Babel extractor plugin for projects already using pybabel.

3. **Interpolation**: How do variables work inside trans blocks?
   - Recommendation: Named placeholders. `{% trans name=user.name %}Hello, {{ name }}!{% endtrans %}` extracts `"Hello, %(name)s!"` as the message ID.

4. **Pluralization**:
   ```kida
   {% trans count=items|length %}
     One item found.
   {% plural %}
     {{ count }} items found.
   {% endtrans %}
   ```
   Compiles to `ngettext("One item found.", "%(count)s items found.", count) % {"count": count}`.

5. **Compile-time**: Can trans blocks participate in optimization?
   - Yes — if the translation function is registered as pure and the message is a constant string, the lookup can be folded at compile time with static context.

### Acceptance Criteria (Sprint 0)
- [ ] Three RFC documents in `plan/` with syntax proposals, compiler strategy, node definitions, and test plans
- [ ] Each RFC reviewed and approved (or revised) before Sprint 1-3 begins
- [ ] No code changes

---

## Sprint 1: Scoped Slots

### Goal
Child components can expose data to slot consumers via `let:` bindings.

### Tasks

#### 1.1 — Parser: `let:` bindings on Slot nodes

**Files**: `src/kida/parser/blocks/functions.py`

- Extend `Slot` node: add `bindings: dict[str, Expr] | None` field (frozen dataclass)
- Extend `SlotBlock` node: add `params: list[str] | None` field
- Parse `let:name=expr` pairs after slot name in def bodies
- Parse `let:name` declarations in call-site slot blocks
- Validate: call-site `let:` names must be subset of def-site `let:` names (or allow all with `**`)

#### 1.2 — Compiler: slot functions accept and inject parameters

**Files**: `src/kida/compiler/statements/functions.py`

- Def-side: when compiling `Slot` with bindings, pass binding values as kwargs to `_caller(slot_name, **bindings)`
- Call-side: slot function signature gains parameters from `let:` declarations
- Inject `let:` params into slot body's scope stack
- Ensure `has_slot()` still works (no signature change needed — bindings are optional)

#### 1.3 — Tests

- Basic scoped slot: list component exposes `item` and `index`
- Named scoped slots: different slots expose different bindings
- Default content with scoped data: fallback slot body uses bindings
- Nested scoped slots: outer and inner components both expose bindings (no collision)
- Scoped slots with `provide`/`consume`: both mechanisms coexist
- Type checker: `let:` bindings recognized as defined variables in slot body

### Acceptance Criteria (Sprint 1)
- [ ] `{% slot row let:item=item, let:index=loop.index %}` compiles and renders
- [ ] Call-site `{% slot row let:item, let:index %}` receives values
- [ ] `rg 'let:' tests/` shows ≥10 test cases passing
- [ ] Existing slot tests unchanged and passing
- [ ] Documentation: `site/content/docs/syntax/components.md` updated

---

## Sprint 2: Error Boundaries

### Goal
Templates can catch rendering errors and render fallback content.

### Tasks

#### 2.1 — Parser: `{% try %}` block

**Files**: `src/kida/parser/blocks/` (new file: `error_handling.py`), `src/kida/parser/statements.py`

- New node: `Try(body, fallback, error_name: str | None)`
- Parse `{% try %}...{% fallback %}...{% end %}` and `{% try %}...{% fallback error %}...{% end %}`
- Register `try` keyword dispatch in statement parser

#### 2.2 — Compiler: try/except code generation

**Files**: `src/kida/compiler/statements/` (new file: `error_handling.py`), `src/kida/compiler/core.py`

- Generate Python `ast.Try` wrapping body compilation
- Catch `(TemplateRuntimeError, UndefinedError, TypeError, ValueError)`
- In except handler: if `error_name`, bind error to scope; compile fallback body
- **Streaming mode**: wrap try body in a sub-buffer (`_try_buf = []`); on success, extend main buffer; on error, discard and render fallback to main buffer
- Line tracking: save/restore `RenderContext.line` around try body

#### 2.3 — Tests

- Basic try/fallback: undefined variable caught, fallback rendered
- Error access: `{% fallback err %}` exposes `err.message`
- Nested try blocks: inner catches first
- Try in streaming mode: partial output not leaked
- Try with slots: error in slot content caught by surrounding try
- Try with include: error in included template caught
- No catch needed: try block with no error renders body normally
- Performance: try block adds no overhead when no error occurs (just a Python try/except frame)

### Acceptance Criteria (Sprint 2)
- [ ] `{% try %}{{ missing_var }}{% fallback %}safe{% end %}` renders `"safe"`
- [ ] `{% fallback err %}{{ err.message }}{% end %}` exposes error details
- [ ] `render_stream()` does not leak partial try-body content on error
- [ ] `rg 'try' tests/test_error_boundaries.py` shows ≥12 test cases
- [ ] Existing tests unchanged and passing

---

## Sprint 3: i18n Foundation

### Goal
Templates support translatable strings with a pluggable gettext backend.

### Tasks

#### 3.1 — Environment: translation backend

**Files**: `src/kida/environment/core.py`

- Add `install_translations(gettext, ngettext)` method
- Store as `env._gettext` and `env._ngettext`
- Inject into template globals as `_()` and `_n()`
- Default: identity function (returns input unchanged) — zero-config works

#### 3.2 — Parser: `{% trans %}` block

**Files**: `src/kida/parser/blocks/` (new file: `i18n.py`), `src/kida/parser/statements.py`

- New nodes: `Trans(singular, plural, variables, count_expr)`, `TransVar(name, expr)`
- Parse `{% trans [var=expr, ...] %}...{% endtrans %}`
- Parse `{% plural %}` inside trans blocks
- Parse `{{ _("literal") }}` as sugar for `Trans(singular="literal")`

#### 3.3 — Compiler: gettext calls

**Files**: `src/kida/compiler/statements/` (new file: `i18n.py`)

- Singular: `_gettext("message %(name)s") % {"name": name_value}`
- Plural: `_ngettext("%(count)s item", "%(count)s items", count) % {"count": count_value}`
- HTML mode: escape interpolated values after translation (translate raw, then escape vars)
- Register `_()` and `_n()` in compiler's known globals

#### 3.4 — Analysis: message extraction

**Files**: `src/kida/analysis/` (new file: `i18n.py`), `src/kida/cli/`

- `ExtractMessagesVisitor` walks AST, collects `(filename, lineno, singular, plural, context)`
- CLI command: `kida extract templates/ -o messages.pot`
- Output: standard PO template format
- Optional: Babel extractor plugin (`kida.babel:extract`)

#### 3.5 — Tests

- Simple translation: `{% trans %}Hello{% endtrans %}` calls gettext
- Variable interpolation: `{% trans name=user.name %}Hello, {{ name }}!{% endtrans %}`
- Pluralization: `{% trans count=n %}One{% plural %}{{ count }} items{% endtrans %}`
- Shorthand: `{{ _("Hello") }}` calls gettext
- HTML escaping: translated string with `<` is escaped; `Markup` passthrough works
- Message extraction: CLI produces valid `.pot` file
- No translations installed: identity function, templates render untranslated
- Compile-time: trans block with constant string and pure gettext folds at compile time

### Acceptance Criteria (Sprint 3)
- [ ] `{% trans %}Hello{% endtrans %}` renders translated string when gettext configured
- [ ] `kida extract templates/` produces valid `.pot` file
- [ ] Pluralization works with `ngettext`
- [ ] `rg 'trans' tests/test_i18n.py` shows ≥15 test cases
- [ ] Existing tests unchanged and passing
- [ ] Documentation: `site/content/docs/advanced/i18n.md` created

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Scoped slot syntax conflicts with existing `let:` usage | High | Low | `let:` is not valid Kida syntax today; no collision possible |
| Try blocks defeat streaming | Medium | Certain | By design — try bodies buffer. Document that try blocks are for risky subtrees, not full pages |
| i18n message extraction misses edge cases | Medium | Medium | Port Jinja2's battle-tested extraction patterns; test against real-world templates |
| Scope creep: i18n grows into full ICU/CLDR | High | Medium | Sprint 3 is foundation only — gettext/ngettext. ICU message format is a separate RFC |
| `caller()` kwargs in Option B confuses existing users | Medium | N/A | Chose Option A (`let:` syntax) to avoid this |

---

## Success Metrics

| Metric | Before | After Sprint 1 | After Sprint 3 |
|--------|--------|-----------------|-----------------|
| Component patterns requiring `provide`/`consume` workaround | All iterator components | Only non-slot patterns | Only non-slot patterns |
| Production render failures from bad data | Uncatchable | Catchable per-component | Catchable per-component |
| i18n support | Application-level only | Application-level only | Native `{% trans %}` + extraction |
| Feature parity with Svelte composition model | ~80% | ~95% (scoped slots) | ~95% |
| Framework positioning readiness | "Better Jinja2" | "Template framework" | "Template framework" |
