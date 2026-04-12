# RFC: `{% yield %}` Directive for Slot Rendering in Nested Calls

**Status**: Implemented (Kida); Phase 2 (chirp-ui migration) in progress
**Created**: 2026-03-16
**Updated**: 2026-03-16 (rev 2 — implementation notes, expanded tests, migration gates)
**Related**: Nested slot passthrough (v0.2.7), Named slots (v0.2.2)
**Priority**: P1 (correctness — current workaround is fragile and non-obvious)
**Affects**: kida-templates, chirp-ui, downstream apps (dori)

---

## Executive Summary

Kida's `{% slot %}` tag has a context-dependent dual personality: inside
`{% def %}` it renders the caller's content (a `Slot` node); inside
`{% call %}` it defines content for the callee (a `SlotBlock` node). This
works fine in simple cases but becomes a correctness hazard when composite
macros need to forward their caller's slot content through nested calls.

The v0.2.7 empty-slot delegation mechanism was added to solve this, but it
only works when the child macro explicitly declares matching named slots.
When the child macro uses `{{ caller() }}` (the common generic pattern in
chirp-ui), the delegation causes **default-slot content leakage** — the
outer caller's default content (e.g. resource cards) appears inside inner
components (e.g. a selection bar).

This RFC proposes `{% yield %}` — a new directive that **always** produces
a `Slot` render node regardless of block context. It eliminates the
parsing ambiguity, removes the need for the `{% slot X %}{% slot X %}{% end %}`
double-nesting workaround, and makes slot forwarding explicit and safe.

| Change | Scope | Effort |
|--------|-------|--------|
| Parser: `yield` keyword dispatch | `parser/statements.py` (1 line) | Low |
| Parser: `_parse_yield()` method | `parser/blocks/functions.py` (~15 lines) | Low |
| Compiler: no changes (reuses `_compile_slot`) | — | None |
| Nodes: no changes (reuses `Slot`) | — | None |
| Lexer: no changes (`yield` tokenizes as `NAME`) | — | None |
| Analysis: no changes (`_visit_slot` handles `Slot`) | — | None |
| Tests: new test suite (5 classes, ~20 tests) + regression | `tests/test_yield_directive.py` | Medium |
| Tests: AST verification tests | `tests/test_yield_directive.py` | Low |
| Docs: functions reference update | `docs/` | Low |

**Zero runtime cost** — `{% yield X %}` compiles to the same Python AST
as `{% slot X %}` inside a `{% def %}`. The change is purely at parse time.

---

## Problem Statement

### The Two Meanings of `{% slot %}`

Inside `{% def %}`, `{% slot X %}` is a **render reference** — it outputs
the caller's content for slot `X`:

```html
{% def card(title) %}
  <div class="card">
    <h2>{{ title }}</h2>
    {% slot %}           ← renders caller's default content
    {% slot footer %}    ← renders caller's "footer" content
  </div>
{% end %}
```

Inside `{% call %}`, `{% slot X %}...{% end %}` is a **content definition**
— it provides content for the callee's slot `X`:

```html
{% call card("Hello") %}
  {% slot footer %}     ← defines "footer" content for card
    <p>Footer here</p>
  {% end %}
  <p>Body content</p>   ← goes to card's default slot
{% end %}
```

The parser disambiguates using the block stack (`_parse_slot`, line 450):

```python
if self._block_stack and self._block_stack[-1][0] == "call":
    return SlotBlock(...)   # content definition
return Slot(...)            # render reference
```

### Where This Breaks: Composite Macros

Real-world UI libraries compose macros. A composite like `resource_index`
wraps several child macros (`search_header`, `filter_bar`, `selection_bar`)
and needs to forward its own caller's named slots into those children.

The intended pattern:

```html
{% def resource_index(title, ...) %}
  {% call selection_bar(count=selected_count) %}
    {% slot selection %}{% end %}     ← INTENT: render my caller's "selection" slot here
  {% end %}                           ← ACTUAL: defines empty "selection" SlotBlock
{% end %}
```

Because `{% slot selection %}{% end %}` is inside a `{% call %}` block, the
parser produces a `SlotBlock` (content definition) instead of a `Slot`
(render reference). The developer intended to render the outer caller's
slot content as the inner call's body, but instead defined an empty named
slot for the inner call.

### The Delegation Mechanism (v0.2.7) and Its Limits

The v0.2.7 release added empty-slot delegation to address this:

```python
# compiler/statements/functions.py, _compile_call_block
if _slot_body_is_empty(slot_body):
    # if _outer_caller is not None:
    #     return _outer_caller(slot_name)
```

When a slot body inside `{% call %}` is empty, the compiled code delegates
to the outer caller with the same slot name. This works when:

1. The child macro declares **matching named slots** (e.g.
   `{% slot filter_controls %}` inside a `{% def filter_bar %}`)
2. The page provides content for those exact slot names

This is validated by `test_nested_empty_slot_passthrough_to_outer_caller`
which models a `filter_bar` that declares `{% slot filter_controls %}` and
`{% slot filter_actions %}` in its def body.

**However**, the delegation fails when the child macro is generic and uses
`{{ caller() }}` (the default slot) instead of named slots. This is the
common pattern in chirp-ui:

```html
{# chirp-ui's selection_bar — generic, uses caller() #}
{% def selection_bar(count=0, ...) %}
<div class="chirpui-selection-bar">
  <span>{{ count }} {{ label }}</span>
  <div class="chirpui-selection-bar__actions">{{ caller() }}</div>
</div>
{% end %}
```

When `resource_index` calls `selection_bar`:

```
{% call selection_bar(count=selected_count) %}
  {% slot selection %}{% end %}
{% end %}
```

The delegation produces this slot map:

| Slot | Body | Delegation |
|------|------|------------|
| `"selection"` | empty | → `_outer_caller("selection")` → tag badges |
| `"default"` | whitespace | → `_outer_caller("default")` → **resource cards** |

`selection_bar` calls `caller()` which resolves to `"default"` — and gets
the resource cards, not the tag badges. The tag badges are in `"selection"`
but `selection_bar` never asks for that slot. The resource cards leak into
the selection bar and appear duplicated on the page.

### The Double-Nesting Workaround

chirp-ui's `layout.html` already contains a workaround for this:

```html
{# layout.html section macro #}
{% call surface(variant=surface_variant) %}
  {% call section_header(title, subtitle, icon) %}
    {% slot actions %}{% slot actions %}{% end %}
  {% end %}
  {% slot %}{% slot %}{% end %}
{% end %}
```

`{% slot actions %}{% slot actions %}{% end %}` works because:
1. The outer `{% slot actions %}...{% end %}` → `SlotBlock` (inside call)
2. The inner `{% slot actions %}` → `Slot` render (inside slot block, not
   directly inside call — block stack top is `"slot"`, not `"call"`)

The inner `Slot` renders the outer caller's `"actions"` content, which
becomes the body of the outer `SlotBlock`, which is passed to the child.

This works but is:
- **Non-obvious** — looks like a typo or stutter
- **Fragile** — depends on block stack depth semantics
- **Verbose** — requires doubling every forwarded slot
- **Undocumented** — not referenced in any docs or changelog

### Impact

| Template | Slot-in-call sites | Status |
|----------|--------------------|--------|
| chirp-ui `resource_index.html` | 6 | Broken (dori override required) |
| chirp-ui `config_dashboard.html` | 4 | Uses double-nesting workaround |
| chirp-ui `layout.html` (`section`) | 2 | Uses double-nesting workaround |
| **Total** | **12** | |

---

## Proposed Solution: `{% yield %}`

### Syntax

```
{% yield %}              → render caller's default slot
{% yield name %}         → render caller's named slot
```

Self-closing (no `{% end %}`). No body. Works identically to `{% slot %}`
inside a `{% def %}`, but is **context-independent** — the parser always
produces a `Slot` node regardless of block stack state.

### Before and After

**Before** (resource_index.html — broken without workaround):

```html
{% def resource_index(title, ...) %}
  {% call selection_bar(count=selected_count) %}
    {% slot selection %}{% end %}
  {% end %}
{% end %}
```

**After** (with `{% yield %}`):

```html
{% def resource_index(title, ...) %}
  {% call selection_bar(count=selected_count) %}
    {% yield selection %}
  {% end %}
{% end %}
```

**Before** (layout.html — double-nesting workaround):

```html
{% call section_header(title, subtitle, icon) %}
  {% slot actions %}{% slot actions %}{% end %}
{% end %}
{% slot %}{% slot %}{% end %}
```

**After**:

```html
{% call section_header(title, subtitle, icon) %}
  {% yield actions %}
{% end %}
{% yield %}
```

### Semantics

`{% yield X %}` compiles to the same code as `{% slot X %}` inside a
`{% def %}`:

```python
if ctx.get("caller"):
    _append(ctx["caller"]("X"))
```

This means `{% yield X %}` renders the **enclosing def's** caller content
for slot `X`. When used inside a `{% call %}` block, the compiled code
appears inside a call-block slot function (`_caller_default` or similar).
That function does not create its own `ctx` — it inherits `ctx` from the
enclosing def via Python closure. So `ctx["caller"]` resolves to the
def's caller, not the inner call's caller. This is the same mechanism
used by `{{ caller("X") }}` in expression context.

**Scoping rule**: `{% yield %}` always refers to the **nearest enclosing
`{% def %}`'s caller**, regardless of how many `{% call %}` blocks it
is nested inside. This is lexical, not dynamic — it follows the source
structure, not the runtime call chain.

### `{% yield %}` vs `{{ caller("X") }}`

Both produce the same output. The difference is ergonomic:

| | `{% yield X %}` | `{{ caller("X") }}` |
|---|---|---|
| Reads as | "Render slot X here" | "Call the caller function with X" |
| Requires guard | No (compiles with `if ctx.get("caller")` guard) | Yes (crashes if no caller) |
| Matches `{% slot %}` | Symmetric verb pair | Different abstraction level |
| Template author mental model | Declarative slot forwarding | Imperative function call |

`{% yield %}` is the recommended form for templates. `{{ caller("X") }}`
remains available for dynamic or conditional slot access in expressions.

---

## Implementation Plan

### 1. Parser: Add `_parse_yield` method

`parser/blocks/functions.py`:

```python
def _parse_yield(self) -> Slot:
    """Parse {% yield %} or {% yield name %} — always a render reference.

    Unlike {% slot %}, which becomes a SlotBlock inside {% call %} blocks,
    {% yield %} always produces a Slot node. This makes it safe to use
    inside nested {% call %} blocks when forwarding the enclosing def's
    caller slots.
    """
    start = self._advance()  # consume 'yield'
    name = "default"
    if self._current.type == TokenType.NAME:
        name = self._advance().value
    self._expect(TokenType.BLOCK_END)
    return Slot(lineno=start.lineno, col_offset=start.col_offset, name=name)
```

### 2. Parser: Register keyword

`parser/statements.py` — add to `_BLOCK_PARSERS`:

```python
_BLOCK_PARSERS: dict[str, str] = {
    # ...
    "slot": "_parse_slot",
    "yield": "_parse_yield",
    # ...
}
```

### 3. No other changes required

- **Nodes**: `_parse_yield` returns `Slot`, which already exists.
- **Compiler**: `_compile_slot` handles `Slot` nodes via the dispatch
  table (`compiler/core.py:1166`). No changes.
- **Lexer**: `yield` tokenizes as `TokenType.NAME` like all block keywords.
- **Analysis**: `Slot` nodes are already handled by all analysis passes
  (`_visit_slot` in `dependencies.py:652` and `purity.py:694`).

### 4. Update `_is_slot_render` introspection (if present)

If any introspection/analysis code checks `isinstance(node, Slot)` to
identify render references, it automatically picks up yield-produced
`Slot` nodes with no changes needed.

---

## Implementation Notes

This section documents the non-obvious mechanics that make `{% yield %}`
work correctly inside `{% call %}` blocks. Implementors and reviewers
should understand these three interactions.

### How yield-produced `Slot` nodes flow through `_parse_call_body`

When `{% yield selection %}` appears inside a `{% call %}` block, the
parser calls `_parse_block()` → `_parse_yield()` → returns `Slot(name="selection")`.

Back in `_parse_call_body` (`parser/blocks/functions.py:393`), the result
is checked with `isinstance(result, SlotBlock)`. A `Slot` is **not** a
`SlotBlock`, so it falls through to the default branch:

```python
# _parse_call_body, line 414–422
if isinstance(result, SlotBlock):
    slots[result.name].extend(result.body)  # named slot definition
elif isinstance(result, list):
    slots["default"].extend(result)
else:
    slots["default"].append(result)          # ← Slot lands here
```

The `Slot` node becomes part of `slots["default"]` — the call block's
default slot body. This is correct: the yield's render output becomes
the content that the child macro receives when it calls `caller()`.

### Why the scoping works: closure over the def's `ctx`

The compiled call block slot function (`_caller_default`) does **not**
create its own `ctx`. It starts with `_make_callable_preamble()` (which
only sets up `buf`, `_append`, `_acc`) and then compiles child nodes
directly. When `_compile_slot` generates:

```python
if ctx.get("caller"):
    _append(ctx["caller"]("selection"))
```

The `ctx` reference resolves via Python closure to the **enclosing def's**
context. That context has `ctx["caller"]` set to the page-level caller
(via `if _caller: ctx['caller'] = _caller` in `_compile_def`, line 178).
So `ctx["caller"]("selection")` calls the page's caller with the named
slot — exactly the desired behavior.

This is the same mechanism that makes `{{ caller("X") }}` work inside
call blocks today. `{% yield %}` merely wraps it in a declarative syntax
with a built-in null guard.

### Why delegation doesn't interfere

The v0.2.7 delegation mechanism (`compiler/statements/functions.py:357`)
triggers when `_slot_body_is_empty(slot_body)` returns `True`. With
`{% yield %}`, the default slot body contains a `Slot` node — it is
**not** empty. The delegation code path is never reached.

This means yield and delegation are orthogonal mechanisms:

| Mechanism | Triggers when | Uses |
|-----------|--------------|------|
| Delegation | Slot body is empty/whitespace-only | `_outer_caller` parameter |
| Yield | `Slot` node in slot body | `ctx["caller"]` closure |

Both can coexist in the same template. `{% slot X %}{% end %}` (empty)
still delegates; `{% yield X %}` (non-empty Slot) renders explicitly.

### Interaction with `_def_caller_stack` and `_outer_caller_expr`

The compiler tracks caller scoping through two mechanisms:

- `_def_caller_stack`: Pushed when entering a `{% def %}` body (line 245).
  Used to determine the `_outer_caller` default parameter for call block
  slot functions.
- `_outer_caller_expr`: Set during call block body compilation (line 355).
  Used by the delegation code path.

`_compile_slot` uses **neither** of these — it only references
`ctx["caller"]` which resolves via closure. The yield directive is
therefore decoupled from the compiler's caller-tracking machinery.
This is a feature: it means `{% yield %}` works correctly regardless
of future changes to the delegation mechanism.

---

## Error Handling & Diagnostics

### Parse errors

`_parse_yield` should produce clear errors for malformed usage:

```python
# Missing block end
{% yield selection       → "Expected %}, got EOF"

# Expression instead of name
{% yield foo.bar %}      → works: NAME token is "foo", ".bar %}" triggers
                            "Expected %}, got '.'"
```

The error messages come from `_expect(TokenType.BLOCK_END)` and require
no special handling — the existing parser infrastructure covers these.

### Runtime behavior

| Scenario | Behavior |
|----------|----------|
| `{% yield %}` inside `{% def %}`, caller provides content | Renders content |
| `{% yield %}` inside `{% def %}`, no caller | Silent no-op (`ctx.get("caller")` → `None`) |
| `{% yield X %}`, caller doesn't define slot X | Empty string (`caller("X")` → `Markup("")`) |
| `{% yield %}` outside `{% def %}` (top-level) | Silent no-op (no `caller` in render context) |
| `{% yield %}` inside `{% call %}` inside `{% def %}` | Renders enclosing def's caller content |

All of these match existing `{% slot %}` behavior — no new failure modes.

### Suggested parse-time warning (future)

A future enhancement could emit a warning when `{% yield %}` appears
outside any `{% def %}` block, since it will always be a no-op. This
is out of scope for the initial implementation but worth tracking.

---

## Testing Plan

### New test file: `tests/test_yield_directive.py`

```python
class TestYieldBasic:
    """{% yield %} always produces a Slot render, even inside {% call %}."""

    def test_yield_in_def(self):
        """{% yield %} inside def renders caller's default content."""
        # {% def card() %}<div>{% yield %}</div>{% end %}
        # {% call card() %}Hello{% end %}
        # → <div>Hello</div>

    def test_yield_named_in_def(self):
        """{% yield name %} inside def renders caller's named slot."""
        # {% def card() %}<div>{% yield footer %}</div>{% end %}
        # {% call card() %}{% slot footer %}Footer{% end %}{% end %}
        # → <div>Footer</div>

    def test_yield_in_nested_call(self):
        """{% yield %} inside {% call %} renders outer def's caller content."""
        # {% def inner() %}<div>{{ caller() }}</div>{% end %}
        # {% def outer() %}{% call inner() %}{% yield %}{% end %}{% end %}
        # {% call outer() %}Content{% end %}
        # → <div>Content</div>

    def test_yield_named_in_nested_call(self):
        """{% yield name %} inside {% call %} renders outer def's named slot."""
        # resource_index pattern
        # {% def selection_bar() %}<bar>{{ caller() }}</bar>{% end %}
        # {% def index() %}
        #   {% call selection_bar() %}{% yield selection %}{% end %}
        # {% end %}
        # {% call index() %}
        #   {% slot selection %}Badges{% end %}
        #   Cards
        # {% end %}
        # → <bar>Badges</bar>  (not <bar>Cards</bar>)

    def test_yield_no_caller_is_silent(self):
        """{% yield %} without caller produces no output (not an error)."""

    def test_yield_default_without_name(self):
        """{% yield %} with no name yields default slot."""


class TestYieldScoping:
    """Verify that yield resolves to the nearest enclosing def's caller."""

    def test_yield_in_doubly_nested_call(self):
        """{% yield %} in inner call still resolves to the def's caller.

        {% def leaf() %}<leaf>{{ caller() }}</leaf>{% end %}
        {% def mid() %}<mid>{{ caller() }}</mid>{% end %}
        {% def outer() %}
          {% call mid() %}
            {% call leaf() %}
              {% yield %}
            {% end %}
          {% end %}
        {% end %}
        {% call outer() %}Content{% end %}
        → <mid><leaf>Content</leaf></mid>
        """

    def test_yield_outside_def_is_noop(self):
        """{% yield %} at template top level produces no output."""
        # {% yield %}<p>hello</p>
        # → <p>hello</p>

    def test_yield_named_slot_not_provided(self):
        """{% yield X %} when caller doesn't define slot X → empty string."""
        # {% def card() %}<div>{% yield sidebar %}</div>{% end %}
        # {% call card() %}Body{% end %}
        # → <div></div>


class TestYieldComposite:
    """End-to-end tests for composite macro slot forwarding."""

    def test_resource_index_pattern(self):
        """Full resource_index→selection_bar→yield chain."""

    def test_resource_index_filter_bar_pattern(self):
        """resource_index→filter_bar with multiple yields."""

    def test_yield_replaces_double_nesting_workaround(self):
        """{% yield X %} produces same output as {% slot X %}{% slot X %}{% end %}."""

    def test_yield_mixed_with_slot_definitions(self):
        """{% yield %} and {% slot X %}content{% end %} coexist in same call block."""
        # {% def inner() %}
        #   <h>{{ caller("header") }}</h>
        #   <b>{{ caller() }}</b>
        # {% end %}
        # {% def outer() %}
        #   {% call inner() %}
        #     {% slot header %}Static header{% end %}
        #     {% yield body %}
        #   {% end %}
        # {% end %}
        # {% call outer() %}{% slot body %}Dynamic{% end %}{% end %}
        # → <h>Static header</h><b>Dynamic</b>

    def test_yield_with_inline_content_in_call(self):
        """{% yield %} alongside plain text in the same call default slot."""
        # {% def inner() %}<div>{{ caller() }}</div>{% end %}
        # {% def outer() %}
        #   {% call inner() %}
        #     <prefix/>
        #     {% yield %}
        #     <suffix/>
        #   {% end %}
        # {% end %}
        # {% call outer() %}Middle{% end %}
        # → <div><prefix/>Middle<suffix/></div>

    def test_multiple_yields_in_same_call(self):
        """Multiple {% yield %} tags concatenate in order."""
        # {% def inner() %}<div>{{ caller() }}</div>{% end %}
        # {% def outer() %}
        #   {% call inner() %}
        #     {% yield header %}
        #     {% yield footer %}
        #   {% end %}
        # {% end %}
        # {% call outer() %}
        #   {% slot header %}H{% end %}
        #   {% slot footer %}F{% end %}
        # {% end %}
        # → <div>HF</div>

    def test_yield_cross_template_import(self):
        """Yield works when macros are imported from different templates."""

    def test_yield_three_level_nesting(self):
        """page → composite → wrapper → leaf with yield at each level."""

    def test_yield_does_not_trigger_delegation(self):
        """Call block with yield has non-empty default slot — delegation skipped.

        Verifies that _slot_body_is_empty returns False for a slot
        body containing a Slot node, so the delegation code path at
        compiler/statements/functions.py:357 is not reached.
        """

    def test_yield_and_delegation_coexist(self):
        """Same call block: one named slot delegates (empty), default uses yield.

        {% call inner() %}
          {% slot header %}{% end %}     ← empty → delegates to outer caller
          {% yield footer %}             ← yield → explicit render
        {% end %}
        """


class TestYieldParser:
    """Parser-level tests for AST node production."""

    def test_yield_produces_slot_node(self):
        """Parser returns Slot (not SlotBlock) regardless of block context."""
        # Parse {% yield %} inside a call block, verify isinstance(node, Slot)

    def test_yield_named_produces_slot_with_name(self):
        """{% yield foo %} → Slot(name="foo")."""

    def test_yield_default_produces_slot_default(self):
        """{% yield %} → Slot(name="default")."""

    def test_yield_parse_error_no_block_end(self):
        """{% yield foo produces a clear parse error."""

    def test_yield_in_call_body_lands_in_default_slot(self):
        """Yield Slot node ends up in CallBlock.slots["default"]."""
        # Parse the call block, verify slots dict structure
```

### Regression tests

Existing `test_nested_def_call_slot.py` tests must continue to pass.
The delegation mechanism for `{% slot %}` inside `{% call %}` is unchanged.

### AST verification tests

Beyond render output, the test suite should include parser-level assertions:

```python
def test_yield_ast_matches_slot_in_def(env):
    """{% yield X %} and {% slot X %} (inside def) produce identical Slot nodes."""
    from kida import Parser
    # Parse: {% def f() %}{% yield foo %}{% end %}
    # Parse: {% def f() %}{% slot foo %}{% end %}
    # Assert both produce Slot(name="foo") in the def body
```

This guards against accidental divergence if `_parse_slot` is later
refactored.

---

## Migration Plan

### Phase 1: kida-templates (this RFC)

1. Implement `{% yield %}` in parser
2. Add test suite (all classes in Testing Plan above)
3. Run full test suite — `poe test` must pass with zero regressions
4. Run `poe types` — no new type errors introduced
5. Update functions reference docs
6. Release as kida-templates 0.2.8 (additive, non-breaking)

**Validation gate**: All existing `test_nested_def_call_slot.py` tests
pass unchanged. New `test_yield_directive.py` passes. Zero regressions.

**Rollback**: Revert the two parser changes (dispatch entry + method).
No data migration, no schema changes, no runtime state to clean up.

### Phase 2: chirp-ui

1. Replace `{% slot X %}{% slot X %}{% end %}` workarounds with `{% yield X %}`
   in `layout.html` `section` macro (2 sites)
2. Replace slot-in-call patterns in `resource_index.html` with `{% yield %}`
   (6 sites)
3. Replace slot-in-call patterns in `config_dashboard.html` with `{% yield %}`
   (4 sites)
4. Remove redundant slot delegation dependency — yield is explicit
5. Bump minimum kida-templates dependency to `>=0.2.8`
6. Run chirp-ui's own test suite
7. Release as chirp-ui 0.1.7

**Validation gate**: For each template, compare rendered HTML output
before and after the yield migration. Use a snapshot test or manual
diff to confirm identical output (modulo whitespace).

**Migration checklist per file**:

```
For each slot-in-call site:
  1. Identify the current pattern:
     - Double-nesting: {% slot X %}{% slot X %}{% end %} → {% yield X %}
     - Empty delegation: {% slot X %}{% end %} → {% yield X %}
     - Workaround set: {% set _x = caller("X") %} → {% yield X %}
  2. Replace with {% yield X %}
  3. Verify: render the page, compare output
  4. Commit atomically per file
```

**Rollback**: Revert chirp-ui templates to use double-nesting workaround.
No kida changes needed (yield still works, just unused).

### Phase 3: dori (downstream)

1. Remove local override `pages/chirpui/resource_index.html`
2. Remove any `{% set _x = caller("X") %}` pre-resolution workarounds
3. Bump chirp-ui dependency to `>=0.1.7`
4. Verify skills, agents, and collections pages render correctly
5. Spot-check: selection bar shows tag badges (not resource cards),
   filter bar shows filter controls, layout sections forward actions

**Validation gate**: Visual inspection of the three affected page types
(skills index, agents index, collections index). Selection bar must show
slot content, not duplicated resource cards.

**Rollback**: Restore the local override file from git history. No
dependency downgrade needed (chirp-ui 0.1.7 is backward compatible).

---

## Alternatives Considered

### A. Fix the "default" slot delegation leak only

Suppress delegation of the `"default"` slot when the call block defines
other named slots. This prevents the resource-cards-in-selection-bar bug
without adding new syntax.

**Rejected**: Treats the symptom, not the cause. Template authors still
can't express "render my caller's slot here" inside a `{% call %}` without
the double-nesting workaround. The delegation heuristic is fragile — it
works for the current chirp-ui architecture but could break with future
macro patterns.

### B. Self-closing `{% slot X %}` (no `{% end %}`) as render reference inside `{% call %}`

Change the parser so that `{% slot X %}` without `{% end %}` inside
`{% call %}` produces a `Slot` (render), while `{% slot X %}...{% end %}`
produces a `SlotBlock` (definition).

**Rejected**: The difference between "has end tag" and "doesn't" is too
subtle. In templates with lots of `{% end %}` closers, it's easy to miss.
Also a breaking change — any existing `{% slot X %}{% end %}` (empty
SlotBlock) would silently change from definition to render semantics.

### C. `{% slot X from caller %}` extended syntax

Add a `from caller` modifier to `{% slot %}` that forces render semantics.

**Rejected**: Verbose for a frequent operation. The `from caller` clause
is redundant — there's only one caller in scope. Better to use a
different verb that's inherently unambiguous.

### D. Implicit slot forwarding (auto-forward unmatched slots)

When a `{% call %}` block doesn't define a slot that the child macro
renders, automatically forward from the outer caller.

**Rejected**: Magical behavior that's hard to debug and reason about.
Would require runtime introspection of which slots the callee renders.
Performance concern with deep nesting. Violates the principle of explicit
over implicit.

### E. Pre-resolution pattern only (no language change)

Document `{% set _x = caller("X") %}` before nested calls as the
canonical workaround. No kida changes needed.

**Rejected as sole solution**: Works but is ceremonial. Every forwarded
slot requires a set statement, and the variable names must be coordinated
between the set and the call block. This is the right interim fix (and is
deployed in dori today) but should not be the permanent answer.

---

## Backward Compatibility

- **Fully backward compatible**. `{% yield %}` is a new keyword that does
  not affect existing `{% slot %}` behavior.
- `{% slot %}` inside `{% call %}` continues to produce `SlotBlock`.
- `{% slot %}` inside `{% def %}` continues to produce `Slot`.
- The delegation mechanism is unchanged.
- No existing templates break.
- `yield` was not previously a reserved word in kida. Any existing template
  using `yield` as a variable name would need renaming, but this is
  extremely unlikely given that `yield` is a Python reserved word and
  template variables are typically domain names, not language keywords.

---

## Future Considerations

### Slot existence checking with `{% yield %}`

A future enhancement could allow `{% yield X %}` to accept a fallback:

```html
{% yield footer or %}<p>Default footer</p>{% end %}
```

This is out of scope for this RFC but the `Slot` node could be extended
with an optional fallback body. Implementation would require:

- A new `YieldWithFallback` node (or an optional `fallback` field on `Slot`)
- Parser changes to detect `or %}` after the name
- Compiler changes to emit a conditional: render caller slot if present,
  else render fallback body

### Deprecation of double-nesting pattern

Once `{% yield %}` is available, the `{% slot X %}{% slot X %}{% end %}`
pattern should be documented as deprecated in chirp-ui. A lint rule could
flag instances. Proposed timeline:

1. **0.2.8**: Ship `{% yield %}`, document as preferred
2. **0.3.0**: Emit deprecation warning for double-nesting in debug mode
3. **0.4.0**: Remove documentation of the workaround pattern

### Compile-time slot name validation

With explicit `{% yield X %}` in composite macros and `{% slot X %}` in
child macros, a future analysis pass could validate that yield names match
declared slots, catching typos at compile time. This requires cross-template
analysis (the callee's slot declarations may be in a different file),
making it a medium-effort enhancement. The `analysis/dependencies.py`
visitor already walks `Slot` nodes and could be extended to collect
yield-name → def-slot-name mappings.

### Keyword reservation and expression-level `yield`

`yield` is a Python reserved word used for generators. Kida currently
uses `yield` only at the **block statement level** (`{% yield %}`), and
the lexer tokenizes it as `NAME` — the same as all other block keywords.
This is safe because block keywords are only dispatched after a
`BLOCK_BEGIN` token (`{%`).

However, if Kida ever adds expression-level `yield` (e.g. generator
expressions in templates, or an `{% async %}` streaming model that uses
yield), the keyword would conflict. This is considered unlikely given
Kida's compilation model (templates compile to functions, not generators,
unless `_streaming=True` — and that uses Python-level `ast.Yield`,
not template-level syntax).

If the conflict ever arises, the resolution would be to use a different
token for the expression form (e.g. `yield_from` or `emit`) and keep
`{% yield %}` for slot rendering.

### Parse-time warning for yield outside def

`{% yield %}` at the template top level (outside any `{% def %}`) is
always a no-op since there is no `caller` in scope. A future parser
enhancement could emit a warning in this case. Implementation: check
`self._block_stack` for any `"def"` or `"region"` entry when parsing
yield; if none found, emit a diagnostic.
