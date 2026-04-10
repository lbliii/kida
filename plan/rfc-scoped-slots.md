# RFC: `{% slot %}` Scoped Bindings — `let:` Syntax for Data-Exposing Slots

**Status**: Draft
**Created**: 2026-04-09
**Updated**: 2026-04-09
**Related**: Named slots (v0.2.2), `{% yield %}` directive (RFC), `provide`/`consume` render context (v0.3.4)
**Priority**: P1 (composition — closes the gap between "template engine" and "template framework")
**Affects**: kida-templates, chirp-ui, downstream component libraries
**Parent**: [epic-template-framework-gaps.md](epic-template-framework-gaps.md) (Sprint 1)

---

## Executive Summary

Kida's slots currently only pass content **down** — a parent provides slot
content to a child component via `{% call %}` / `{% slot %}`. The child
component has no mechanism to expose data **up** to the slot consumer. This
means a list component that iterates rows cannot hand each `row` to the
caller's slot template without resorting to `provide`/`consume` — a verbose,
indirect workaround that obscures the data flow.

Scoped slots solve this by allowing the def-side `{% slot %}` to declare
`let:` bindings (name=expression pairs) that are passed as arguments to the
caller's slot function. The call-site `{% slot %}` declares matching `let:`
parameters that become local variables inside the slot body. This is
equivalent to Svelte's `let:` directive or Vue's scoped slots (`#default="{ item }"`).

| Change | Scope | Effort |
|--------|-------|--------|
| Nodes: `Slot.bindings`, `SlotBlock.params` | `nodes/functions.py` (~6 lines) | Low |
| Parser: `let:` binding parsing | `parser/blocks/functions.py` (~40 lines) | Medium |
| Compiler: kwargs in `_caller()` call + params in slot fns | `compiler/statements/functions.py` (~30 lines) | Medium |
| Tests: new test suite (3 classes, >=10 tests) | `tests/test_scoped_slots.py` | Medium |
| Docs: components reference update | `docs/` | Low |

**Fully backward compatible** — `let:` is new syntax; existing slots
without `let:` work exactly as before. No new node types needed.

---

## Motivation

### The Problem: Child Cannot Expose Data to Slot Consumer

Consider a reusable data table component:

```kida
{% def data_table(rows, columns) %}
  <table>
    <thead>
      <tr>{% for col in columns %}<th>{{ col.label }}</th>{% end %}</tr>
    </thead>
    <tbody>
    {% for row in rows %}
      <tr>
        {% slot row_content %}
          {# Default: render all columns #}
          {% for col in columns %}
            <td>{{ row[col.key] }}</td>
          {% end %}
        {% end %}
      </tr>
    {% end %}
    </tbody>
  </table>
{% end %}
```

The caller wants to customize how each row renders, but `row` is a loop
variable inside the def body — it is not accessible from the call site:

```kida
{% call data_table(users, user_columns) %}
  {% slot row_content %}
    {# PROBLEM: `row` is not in scope here — it lives inside data_table's for loop #}
    <td>{{ row.name }}</td>
    <td><a href="{{ row.profile_url }}">Profile</a></td>
  {% end %}
{% end %}
```

This fails because `row` is undefined in the caller's scope. The slot
body is compiled as a function (`_caller_row_content`) that closes over
the **call site's** context, not the **def body's** context.

### Current Workaround: `provide`/`consume`

The only way to pass data from inside a def body to a slot consumer today
is through the render context mechanism:

```kida
{# Def side — verbose, indirect #}
{% def data_table(rows, columns) %}
  <table>
    <tbody>
    {% for row in rows %}
      {% provide table_row=row, table_index=loop.index %}
        <tr>{% slot row_content %}<td>{{ row }}</td>{% end %}</tr>
      {% end %}
    {% end %}
    </tbody>
  </table>
{% end %}

{# Call site — must know the provide keys #}
{% call data_table(users, user_columns) %}
  {% slot row_content %}
    {% consume table_row as row %}
    {% consume table_index as index %}
    <td>{{ row.name }}</td>
    <td>{{ index }}</td>
  {% end %}
{% end %}
```

This works but has significant drawbacks:

1. **Verbose** — two extra tags (`provide` + `consume`) per binding
2. **Indirect** — data flows through the render context, not through the
   slot's function signature. The connection between `provide table_row`
   and `consume table_row` is string-based and invisible to tooling.
3. **No validation** — typos in provide/consume keys fail silently at
   runtime (undefined variable)
4. **Violates encapsulation** — `provide`/`consume` was designed for
   cross-cutting concerns (theme, locale), not for per-slot data contracts

### How Other Frameworks Solve This

**Svelte** — `let:` directive:
```svelte
<!-- Component definition -->
<ul>
  {#each items as item, index}
    <slot {item} {index}>
      <li>{item}</li>
    </slot>
  {/each}
</ul>

<!-- Usage -->
<List {items} let:item let:index>
  <li class:odd={index % 2}>{item.name}</li>
</List>
```

**Vue** — Scoped slots:
```vue
<!-- Component definition -->
<ul>
  <li v-for="(item, index) in items">
    <slot :item="item" :index="index">{{ item }}</slot>
  </li>
</ul>

<!-- Usage -->
<List :items="items">
  <template #default="{ item, index }">
    <li :class="{ odd: index % 2 }">{{ item.name }}</li>
  </template>
</List>
```

Both use the slot's function call boundary to pass data. Kida's slot
mechanism already compiles slots to Python functions — we just need to
add parameters.

---

## Proposed Solution: `let:` Bindings (Option A — Recommended)

### Syntax

**Def-side** — declare what data the slot exposes:

```kida
{% def data_list(items) %}
  <ul>
  {% for item in items %}
    {% slot row let:item=item, let:index=loop.index %}
      <li>{{ item }}</li>
    {% end %}
  {% end %}
  </ul>
{% end %}
```

The `{% slot row let:item=item, let:index=loop.index %}` declares that
slot `row` exposes two bindings: `item` (bound to the loop variable
`item`) and `index` (bound to `loop.index`). The body between `{% slot %}`
and `{% end %}` is the default content, used when the caller does not
provide a `row` slot.

Note: inside a `{% def %}` body, `{% slot name %}...{% end %}` with a body
is a **new** capability introduced by scoped slots. Currently, `{% slot %}`
inside `{% def %}` is self-closing (no body, no `{% end %}`). Scoped slots
extend this: when `let:` bindings are present, the slot **requires** a body
(the default content) and an `{% end %}` tag. Without `let:`, the existing
self-closing behavior is preserved.

**Call-site** — declare what bindings to receive:

```kida
{% call data_list(users) %}
  {% slot row let:item, let:index %}
    <li class="{{ 'odd' if index is odd }}">{{ item.name }}</li>
  {% end %}
{% end %}
```

The `{% slot row let:item, let:index %}` declares that this slot body
expects to receive `item` and `index` as local variables. These are
injected into the slot function's scope when the def-side calls
`_caller("row", item=item_value, index=index_value)`.

### Semantics

1. **Def-side `{% slot name let:x=expr %}`**: When the slot is rendered,
   the compiled code calls `_caller("name", x=compiled_expr)` instead of
   `_caller("name")`. The binding expressions are evaluated in the def
   body's scope (they have access to loop variables, local lets, etc.).

2. **Call-site `{% slot name let:x %}`**: The slot function gains a
   parameter `x` which is injected as a local variable in the slot body.
   The compiled slot function signature changes from `_caller_row(_scope_stack)`
   to `_caller_row(_scope_stack, *, item=None, index=None)`.

3. **Default content**: When the caller does not provide a `row` slot,
   the def-side default body renders. The def-side binding expressions
   are still evaluated and available as locals in the default body
   (they are the `let:name=expr` values).

4. **Missing bindings**: If the call-site declares `let:item` but the
   def-side does not expose `item`, the parameter defaults to `None`.
   A parse-time warning is emitted if the call-site requests bindings
   not exposed by the def (requires cross-template analysis; deferred
   to a future enhancement — see Future Considerations).

### Before and After

**Before** (with `provide`/`consume` workaround):

```kida
{% def user_list(users) %}
  <ul>
  {% for user in users %}
    {% provide list_item=user, list_index=loop.index %}
      <li>{% slot item %}<span>{{ user.name }}</span>{% end %}</li>
    {% end %}
  {% end %}
  </ul>
{% end %}

{% call user_list(all_users) %}
  {% slot item %}
    {% consume list_item as user %}
    {% consume list_index as i %}
    <span class="{{ 'alt' if i is odd }}">{{ user.name }} ({{ user.email }})</span>
  {% end %}
{% end %}
```

**After** (with `let:` scoped slots):

```kida
{% def user_list(users) %}
  <ul>
  {% for user in users %}
    {% slot item let:user=user, let:index=loop.index %}
      <li><span>{{ user.name }}</span></li>
    {% end %}
  {% end %}
  </ul>
{% end %}

{% call user_list(all_users) %}
  {% slot item let:user, let:index %}
    <li><span class="{{ 'alt' if index is odd }}">{{ user.name }} ({{ user.email }})</span></li>
  {% end %}
{% end %}
```

---

## Rejected Alternative: Option B — Extend `caller()` kwargs

This approach would use the existing `caller()` call mechanism with
keyword arguments, and a new `with` clause on `{% call %}`:

```kida
{# Def side — caller() gains kwargs #}
{% def data_list(items) %}
  <ul>
  {% for item in items %}
    {{ caller(item=item, index=loop.index) }}
  {% end %}
  </ul>
{% end %}

{# Call site — `with` clause declares received params #}
{% call data_list(users) with item, index %}
  <li class="{{ 'odd' if index is odd }}">{{ item.name }}</li>
{% end %}
```

**Rationale for rejection**:

1. **Only works with the default slot** — `caller()` does not naturally
   support named slot kwargs. To pass different bindings to different
   named slots, you would need `caller("row", item=item)` — at which
   point the call site has no clean way to declare which slot receives
   which params.

2. **`with` clause overloads meaning** — `with` is commonly associated
   with context managers in Python. Using it for parameter declaration
   on `{% call %}` is confusing.

3. **Invisible data contract** — The def-side `{{ caller(item=item) }}`
   is an expression call, not a declarative slot. You cannot look at the
   def body and see "this slot exposes `item`" without reading every
   `caller()` call. With `let:`, the binding is declared on the
   `{% slot %}` tag itself.

4. **No default content** — `{{ caller(...) }}` is an expression; it
   has no block body for default content. The `let:` approach naturally
   supports `{% slot name let:x=expr %}default{% end %}`.

---

## Implementation Plan

### 1. Node Changes (`nodes/functions.py`)

The `Slot` node (line 68) gains an optional `bindings` field. The
`SlotBlock` node (line 76) gains an optional `params` field.

**`Slot`** — def-side slot placeholder:

```python
@final
@dataclass(frozen=True, slots=True)
class Slot(Node):
    """Slot placeholder inside {% def %}: {% slot %} or {% slot name %}

    When bindings are present, the slot exposes data to the caller via
    let: syntax. The body (if present) is default content rendered when
    the caller does not provide this slot.
    """

    name: str = "default"
    bindings: tuple[tuple[str, Expr], ...] | None = None
    body: tuple[Node, ...] | None = None
```

`bindings` is a tuple of `(name, expression)` pairs. Using a tuple of
tuples (not dict) preserves declaration order and is hashable for the
frozen dataclass. `body` holds the default content nodes when the slot
has `let:` bindings.

**`SlotBlock`** — call-site slot content:

```python
@final
@dataclass(frozen=True, slots=True)
class SlotBlock(Node):
    """Named slot content inside {% call %}: {% slot name %}...{% end %}"""

    name: str
    body: Sequence[Node]
    params: tuple[str, ...] | None = None
```

`params` is the tuple of `let:` parameter names declared at the call
site. These become keyword-only parameters in the compiled slot function.

No new node types are needed. The existing `Slot` and `SlotBlock` are
extended with optional fields that default to `None`, preserving backward
compatibility with all existing code that constructs or inspects these nodes.

### 2. Parser Changes (`parser/blocks/functions.py`)

#### `_parse_slot` (line 435)

The method currently handles two contexts: inside `{% call %}` it produces
a `SlotBlock`, inside `{% def %}` it produces a self-closing `Slot`. The
scoped slots change extends both paths.

**After parsing the slot name (line 446), check for `let:` bindings**:

```python
def _parse_slot(self) -> Slot | SlotBlock:
    start = self._advance()  # consume 'slot'

    # Optional slot name
    name = "default"
    if self._current.type == TokenType.NAME and self._current.value != "let":
        name = self._advance().value

    # Parse let: bindings (both def-side and call-side)
    let_bindings: list[tuple[str, Expr | None]] = []
    while (
        self._current.type == TokenType.NAME
        and self._current.value == "let"
    ):
        # Peek ahead for the colon: "let" ":" "name"
        # The lexer tokenizes "let:name" as NAME("let") COLON NAME("name")
        # or "let:name=expr" as NAME("let") COLON NAME("name") ASSIGN expr
        if not self._match_next(TokenType.COLON):
            break
        self._advance()  # consume 'let'
        self._advance()  # consume ':'
        if self._current.type != TokenType.NAME:
            raise self._error(
                "Expected binding name after 'let:'",
                suggestion="Syntax: let:name=expr (def) or let:name (call)",
            )
        binding_name = self._advance().value

        # Check for =expr (def-side binding)
        binding_expr: Expr | None = None
        if self._match(TokenType.ASSIGN):
            self._advance()  # consume '='
            binding_expr = self._parse_expression()

        let_bindings.append((binding_name, binding_expr))

        # Optional comma between let: bindings
        if self._match(TokenType.COMMA):
            self._advance()

    self._expect(TokenType.BLOCK_END)

    # Inside call block: parse as SlotBlock with params
    if self._block_stack and self._block_stack[-1][0] == "call":
        self._push_block("slot", start)
        body = self._parse_body()
        self._consume_end_tag("slot")
        params = tuple(b[0] for b in let_bindings) if let_bindings else None
        return SlotBlock(
            lineno=start.lineno,
            col_offset=start.col_offset,
            name=name,
            body=tuple(body),
            params=params,
        )

    # Inside def: if let: bindings present, parse body + end tag
    if let_bindings:
        bindings = tuple((b[0], b[1]) for b in let_bindings)
        # Validate: def-side bindings must have expressions
        for bname, bexpr in bindings:
            if bexpr is None:
                raise self._error(
                    f"Def-side let:{bname} requires an expression: let:{bname}=expr",
                    suggestion=f"Use let:{bname}={bname} to expose the variable '{bname}'",
                )
        self._push_block("slot", start)
        body = self._parse_body()
        self._consume_end_tag("slot")
        return Slot(
            lineno=start.lineno,
            col_offset=start.col_offset,
            name=name,
            bindings=tuple((b[0], b[1]) for b in bindings),  # type: ignore[misc]
            body=tuple(body),
        )

    # No let: bindings — existing self-closing behavior
    return Slot(
        lineno=start.lineno,
        col_offset=start.col_offset,
        name=name,
    )
```

Key parsing decisions:

- **`let:` is not a reserved word** — it is recognized contextually after
  a slot name. The parser checks for `NAME("let")` followed by `COLON`.
  This cannot conflict with existing syntax because `let` after a slot
  name would currently be a parse error (`Expected %}`).

- **Def-side vs call-side disambiguation** — def-side requires `let:name=expr`
  (expression is mandatory); call-side uses `let:name` (no expression).
  The parser validates this after determining the context from `_block_stack`.

- **Comma separation** — `let:item=item, let:index=loop.index` uses commas
  between bindings. The comma is optional (whitespace separation also works)
  to match Kida's generally permissive token style.

#### `_parse_yield` (line 469)

No changes needed. `{% yield %}` does not support `let:` bindings because
yield is a render reference (renders the caller's content), not a slot
declaration. Scoped data flows through `{% slot %}`, not `{% yield %}`.

### 3. Compiler Changes (`compiler/statements/functions.py`)

#### `_compile_slot` (line 834) — Def-side slot rendering

Currently, `_compile_slot` generates:

```python
if ctx.get("caller"):
    _append(ctx["caller"]("slot_name"))
```

With scoped bindings, this becomes:

```python
if ctx.get("caller"):
    _append(ctx["caller"]("slot_name", item=_compiled_item_expr, index=_compiled_index_expr))
else:
    # Render default body with bindings as locals
    ...
```

The updated method:

```python
def _compile_slot(self, node: Slot) -> list[ast.stmt]:
    slot_name = node.name

    # Compile binding kwargs (if any)
    binding_keywords: list[ast.keyword] = []
    if node.bindings:
        for bname, bexpr in node.bindings:
            binding_keywords.append(
                ast.keyword(arg=bname, value=self._compile_expr(bexpr))
            )

    # Build _caller(slot_name, **bindings) call
    caller_call = ast.Call(
        func=ast.Subscript(
            value=ast.Name(id="ctx", ctx=ast.Load()),
            slice=ast.Constant(value="caller"),
            ctx=ast.Load(),
        ),
        args=[ast.Constant(value=slot_name)],
        keywords=binding_keywords,
    )

    caller_branch = [
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="_append", ctx=ast.Load()),
                args=[caller_call],
                keywords=[],
            ),
        )
    ]

    # If slot has a default body, compile it as the else branch
    else_branch: list[ast.stmt] = []
    if node.body:
        # Inject let: bindings as local variables for default body
        if node.bindings:
            for bname, bexpr in node.bindings:
                else_branch.append(
                    ast.Assign(
                        targets=[ast.Name(id=bname, ctx=ast.Store())],
                        value=self._compile_expr(bexpr),
                    )
                )
        for child in node.body:
            else_branch.extend(self._compile_node(child))

    return [
        ast.If(
            test=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="ctx", ctx=ast.Load()),
                    attr="get",
                    ctx=ast.Load(),
                ),
                args=[ast.Constant(value="caller")],
                keywords=[],
            ),
            body=caller_branch,
            orelse=else_branch,
        )
    ]
```

#### `_compile_call_block` (line 385) — Call-site slot functions

The slot function currently has the signature:

```python
def _caller_row(_scope_stack, _outer_caller=_def_caller):
    buf = []
    ...
    return _Markup(''.join(buf))
```

With `let:` params, it becomes:

```python
def _caller_row(_scope_stack, _outer_caller=_def_caller, *, item=None, index=None):
    buf = []
    item = item  # inject into local scope (already a parameter)
    index = index
    ...
    return _Markup(''.join(buf))
```

The change is in the slot function construction loop (lines 396-482).
After building `slot_args` and before appending the `FunctionDef`, add
keyword-only args from `SlotBlock.params`:

```python
# Inside the for slot_name, slot_body loop:
slot_kwonlyargs: list[ast.arg] = []
slot_kw_defaults: list[ast.expr | None] = []

# If this is a SlotBlock with params, find the original node
# (We need to look up the SlotBlock node to get params)
# The params come from the SlotBlock node parsed from the call body.
# We pass them through the slots dict by storing them on the CallBlock.
if hasattr(node, '_slot_params') and slot_name in node._slot_params:
    for param_name in node._slot_params[slot_name]:
        slot_kwonlyargs.append(ast.arg(arg=param_name))
        slot_kw_defaults.append(ast.Constant(value=None))
```

However, since `CallBlock.slots` is `dict[str, Sequence[Node]]` and
we need the params separately, the cleaner approach is to change
`CallBlock` to carry slot params:

**Revised `CallBlock` node** (`nodes/functions.py`, line 84):

```python
@final
@dataclass(frozen=True, slots=True)
class CallBlock(Node):
    """Call function with slot content: {% call name(args) %}...{% end %}"""

    call: Expr
    slots: dict[str, Sequence[Node]]
    args: Sequence[Expr] = ()
    slot_params: dict[str, tuple[str, ...]] | None = None

    @property
    def body(self) -> Sequence[Node]:
        """Backward-compat: default slot content."""
        return self.slots.get("default", ())
```

The parser's `_parse_call_body` collects `SlotBlock.params` into a
separate dict that gets passed to `CallBlock.slot_params`.

In the compiler, the slot function definition adds keyword-only args:

```python
# Build kwonly args for let: params
slot_kwonlyargs: list[ast.arg] = []
slot_kw_defaults: list[ast.expr | None] = []
if node.slot_params and slot_name in node.slot_params:
    for param_name in node.slot_params[slot_name]:
        slot_kwonlyargs.append(ast.arg(arg=param_name))
        slot_kw_defaults.append(ast.Constant(value=None))

stmts.append(
    ast.FunctionDef(
        name=fn_name,
        args=ast.arguments(
            posonlyargs=[],
            args=slot_args,
            vararg=None,
            kwonlyargs=slot_kwonlyargs,
            kw_defaults=slot_kw_defaults,
            kwarg=None,
            defaults=slot_defaults,
        ),
        body=caller_body,
        decorator_list=[],
        returns=None,
    )
)
```

#### `_caller_wrapper` — Forward kwargs through the dispatch layer

The current `_caller_wrapper` (line 529) dispatches `_caller(slot)` to
`_caller_slots[slot](_scope_stack)`. With scoped bindings, the wrapper
must forward `**kwargs`:

```python
# Updated wrapper signature: _caller_wrapper(slot="default", _scope_stack=..., **kwargs)
def _caller_wrapper(slot="default", _scope_stack=_scope_stack, **_let_kwargs):
    _f = _caller_slots.get(slot)
    return _f(_scope_stack, **_let_kwargs) if _f else _Markup("")
```

And the lambda that creates `_caller_with_scope`:

```python
# Updated lambda: forward **kwargs
_caller_with_scope = lambda slot="default", **_kw: _caller_wrapper(slot, _scope_stack, **_kw)
```

The compiled AST changes are:

1. Add `**_let_kwargs` to `_caller_wrapper`'s argument list (add
   `kwarg=ast.arg(arg="_let_kwargs")` to the `ast.arguments`)
2. Add `keywords=[ast.keyword(arg=None, value=ast.Name(id="_let_kwargs"))]`
   to the `_f(_scope_stack)` call (kwargs spread)
3. Add `kwarg=ast.arg(arg="_kw")` to the lambda's arguments and
   `keywords=[ast.keyword(arg=None, value=ast.Name(id="_kw"))]` to the
   inner `_caller_wrapper(slot, _scope_stack)` call

### 4. Parser Update for `_parse_call` / `_parse_call_body`

`_parse_call_body` (line 394) currently collects `SlotBlock` nodes into
the slots dict. It must also collect `SlotBlock.params` into a separate
params dict to pass to `CallBlock`:

```python
def _parse_call_body(self) -> tuple[dict[str, Sequence[Node]], dict[str, tuple[str, ...]]]:
    slots: dict[str, list[Node]] = {"default": []}
    slot_params: dict[str, tuple[str, ...]] = {}

    while self._current.type != TokenType.EOF:
        # ... existing loop body ...
        if isinstance(result, SlotBlock):
            name = result.name
            if name not in slots:
                slots[name] = []
            slots[name].extend(result.body)
            if result.params:
                slot_params[name] = result.params
        # ... rest unchanged ...

    return (
        {k: tuple(v) for k, v in slots.items()},
        slot_params if slot_params else None,
    )
```

And `_parse_call` (line 361) passes both through:

```python
slots, slot_params = self._parse_call_body()
return CallBlock(
    lineno=start.lineno,
    col_offset=start.col_offset,
    call=call_expr,
    slots=slots,
    slot_params=slot_params,
)
```

Alternatively, to minimize signature changes, `_parse_call_body` can
return a single dict and `_parse_call` can extract params from the
`SlotBlock` nodes before they are flattened. The implementation should
choose whichever approach is cleaner.

---

## Implementation Notes

### How `let:` kwargs flow through the caller dispatch chain

The complete data flow for a scoped slot call:

1. **Def body** — `{% slot row let:item=item, let:index=loop.index %}`
   compiles to:
   ```python
   if ctx.get("caller"):
       _append(ctx["caller"]("row", item=item, index=loop_index))
   ```

2. **`ctx["caller"]`** is `_caller_with_scope`, the lambda generated
   by `_compile_call_block`. It captures `_scope_stack` and forwards
   to `_caller_wrapper`:
   ```python
   _caller_with_scope = lambda slot="default", **_kw: _caller_wrapper(slot, _scope_stack, **_kw)
   ```

3. **`_caller_wrapper`** looks up the slot function and forwards kwargs:
   ```python
   def _caller_wrapper(slot="default", _scope_stack=_scope_stack, **_let_kwargs):
       _f = _caller_slots.get(slot)
       return _f(_scope_stack, **_let_kwargs) if _f else _Markup("")
   ```

4. **`_caller_row`** receives the kwargs as keyword-only parameters:
   ```python
   def _caller_row(_scope_stack, _outer_caller=_def_caller, *, item=None, index=None):
       buf = []
       _append = buf.append
       # item and index are now in scope as local variables
       # ... compile slot body ...
       return _Markup(''.join(buf))
   ```

The kwargs travel through three function calls but are never stored in
any intermediate data structure. Python's `**kwargs` forwarding is
efficient (dict pointer, no copy for small dicts).

### Interaction with the delegation mechanism

The delegation mechanism (line 410 in `_compile_call_block`) triggers
when `_slot_body_is_empty(slot_body)` returns `True`. A scoped slot's
call-site body is never empty (it contains the custom render template),
so delegation is not triggered. The two mechanisms are orthogonal.

If a call-site declares `let:` params but provides an empty body:

```kida
{% slot row let:item %}{% end %}
```

The body is whitespace-only, so `_slot_body_is_empty` returns `True`
and delegation fires. The `let:` params are ignored (the delegation
calls `_outer_caller("row")` without kwargs). This is correct: an empty
scoped slot body means "I don't want to customize this slot; let the
outer component handle it."

### Interaction with `{% yield %}`

`{% yield %}` always produces a `Slot` node with no bindings and no body.
It is a pure render reference — it renders whatever the enclosing def's
caller provides. Scoped bindings do not apply to yield because yield does
not declare a data contract; it simply forwards.

If a component uses `{% yield row %}` inside a nested `{% call %}`, the
yield renders the outer caller's `row` slot content. Any `let:` bindings
that the outer caller's `row` slot function expects will receive `None`
(the defaults) because yield does not forward kwargs. This is the correct
behavior: yield is for content forwarding, not data forwarding.

### Interaction with `provide`/`consume`

Scoped slots and `provide`/`consume` can coexist. A component could use
`let:` for its primary data contract and `provide` for cross-cutting
context:

```kida
{% def data_table(rows, columns, theme="light") %}
  {% provide table_theme=theme %}
    {% for row in rows %}
      {% slot row let:row=row, let:index=loop.index %}
        <tr>{{ row }}</tr>
      {% end %}
    {% end %}
  {% end %}
{% end %}
```

The call site receives `row` and `index` via `let:`, and can also
`consume table_theme` if needed. No interference between the mechanisms.

### Default content and binding scope

When no caller provides a slot, the def-side default body renders. The
`let:` binding expressions are evaluated and injected as locals:

```python
# Compiled: {% slot row let:item=item, let:index=loop.index %}<li>{{ item }}</li>{% end %}
if ctx.get("caller"):
    _append(ctx["caller"]("row", item=item, index=loop_index))
else:
    # Default body — bindings become locals
    _let_item = item
    _let_index = loop_index
    _append("<li>")
    _append(_e(_s(_let_item)))
    _append("</li>")
```

The binding expressions (`item`, `loop.index`) are in scope because the
default body executes inside the def body's Python scope. The variable
names are the `let:` names, matching what the call-site would receive.

---

## Backward Compatibility

- **Fully backward compatible**. `let:` is new syntax on `{% slot %}`;
  slots without `let:` work exactly as before.
- The `Slot` and `SlotBlock` node changes add optional fields with
  `None` defaults. All existing code that constructs or pattern-matches
  these nodes continues to work.
- The `CallBlock` node gains an optional `slot_params` field with a
  `None` default. The `body` property is unchanged.
- The `_caller_wrapper` gains `**_let_kwargs` which is backward
  compatible — existing callers pass no kwargs, so `_let_kwargs` is
  an empty dict.
- `let` is not a reserved word. It is only recognized contextually
  after a slot name when followed by `:`. Any existing template using
  `let` as a variable name is unaffected.

---

## Files Modified

| File | Change | Lines Affected |
|------|--------|----------------|
| `src/kida/nodes/functions.py` | Add `bindings` and `body` fields to `Slot`; add `params` field to `SlotBlock`; add `slot_params` field to `CallBlock` | Lines 68-96 |
| `src/kida/parser/blocks/functions.py` | Extend `_parse_slot` to parse `let:` bindings; update `_parse_call_body` to collect slot params; update `_parse_call` to pass `slot_params` | Lines 394-467 |
| `src/kida/compiler/statements/functions.py` | Extend `_compile_slot` to pass binding kwargs; extend `_compile_call_block` to add kwonly args to slot functions; update `_caller_wrapper` to forward kwargs | Lines 385-608, 834-873 |
| `tests/test_scoped_slots.py` | New test file | New file |

---

## Testing Plan

### New test file: `tests/test_scoped_slots.py`

```python
class TestScopedSlotBasic:
    """Core scoped slot functionality — single binding, rendering, defaults."""

    def test_single_binding(self):
        """Slot exposes one variable to caller via let:."""
        # {% def items(data) %}
        #   {% for x in data %}
        #     {% slot item let:value=x %}{{ x }}{% end %}
        #   {% end %}
        # {% end %}
        # {% call items(["a", "b"]) %}
        #   {% slot item let:value %}[{{ value }}]{% end %}
        # {% end %}
        # -> [a][b]

    def test_multiple_bindings(self):
        """Slot exposes multiple variables via let:."""
        # {% def list(items) %}
        #   {% for item in items %}
        #     {% slot row let:item=item, let:index=loop.index %}
        #       {{ item }}
        #     {% end %}
        #   {% end %}
        # {% end %}
        # {% call list(["x", "y"]) %}
        #   {% slot row let:item, let:index %}{{ index }}:{{ item }}{% end %}
        # {% end %}
        # -> 0:x1:y

    def test_default_content_with_bindings(self):
        """When caller does not provide slot, default body uses bindings."""
        # {% def items(data) %}
        #   {% for x in data %}
        #     {% slot item let:value=x %}<b>{{ value }}</b>{% end %}
        #   {% end %}
        # {% end %}
        # {{ items(["a", "b"]) }}  {# no call block — uses default #}
        # -> <b>a</b><b>b</b>

    def test_named_scoped_slots(self):
        """Different named slots expose different bindings."""
        # {% def table(rows, cols) %}
        #   {% for row in rows %}
        #     {% slot row_start let:row=row %}{% end %}
        #     {% for col in cols %}
        #       {% slot cell let:row=row, let:col=col %}
        #         {{ row[col] }}
        #       {% end %}
        #     {% end %}
        #     {% slot row_end let:row=row %}{% end %}
        #   {% end %}
        # {% end %}
        # {% call table(data, ["name", "age"]) %}
        #   {% slot cell let:row, let:col %}
        #     <td class="{{ col }}">{{ row[col] }}</td>
        #   {% end %}
        # {% end %}


class TestScopedSlotNesting:
    """Nested components with scoped slots — no variable collision."""

    def test_nested_scoped_slots_no_collision(self):
        """Outer and inner components both expose let:item — no collision."""
        # {% def outer(items) %}
        #   {% for item in items %}
        #     {% slot outer_item let:item=item %}{{ item }}{% end %}
        #   {% end %}
        # {% end %}
        # {% def inner(items) %}
        #   {% for item in items %}
        #     {% slot inner_item let:item=item %}{{ item }}{% end %}
        #   {% end %}
        # {% end %}
        # Verify that inner's let:item does not shadow outer's let:item
        # when both are used in the same page.

    def test_scoped_slot_inside_scoped_slot(self):
        """Scoped slot body contains a call to another scoped-slot component."""
        # {% call outer_list(groups) %}
        #   {% slot group let:group %}
        #     {% call inner_list(group.items) %}
        #       {% slot item let:item %}
        #         {{ group.name }}: {{ item.name }}
        #       {% end %}
        #     {% end %}
        #   {% end %}
        # {% end %}
        # Verifies that `group` from outer scope and `item` from inner
        # scope are both accessible.

    def test_scoped_slot_with_provide_consume(self):
        """let: bindings and provide/consume coexist without interference."""
        # {% def themed_list(items) %}
        #   {% provide theme="dark" %}
        #     {% for item in items %}
        #       {% slot row let:item=item %}{{ item }}{% end %}
        #     {% end %}
        #   {% end %}
        # {% end %}
        # {% call themed_list(data) %}
        #   {% slot row let:item %}
        #     {% consume theme as t %}
        #     <div class="{{ t }}">{{ item }}</div>
        #   {% end %}
        # {% end %}


class TestScopedSlotEdgeCases:
    """Edge cases, error handling, and compatibility."""

    def test_call_site_binding_not_exposed_defaults_to_none(self):
        """Call-site declares let:x but def-side does not expose x — x is None."""
        # {% def simple() %}{% slot body %}default{% end %}{% end %}
        # {% call simple() %}
        #   {% slot body let:x %}{{ x }}{% end %}
        # {% end %}
        # -> None

    def test_scoped_slot_with_yield_forwarding(self):
        """{% yield %} inside a call block does not forward let: kwargs."""
        # Composite macro uses yield to forward slot; scoped bindings
        # are only available to the direct call-site, not through yield.
        # {% def inner() %}
        #   {% slot content let:value="hello" %}default{% end %}
        # {% end %}
        # {% def outer() %}
        #   {% call inner() %}{% yield content %}{% end %}
        # {% end %}
        # {% call outer() %}
        #   {% slot content let:value %}{{ value }}{% end %}
        # {% end %}

    def test_streaming_mode_with_scoped_slots(self):
        """Scoped slots render correctly in streaming mode."""
        # env.render_stream() with a scoped-slot template produces
        # the same output as env.render().

    def test_type_checker_recognizes_let_bindings(self):
        """let: parameters are recognized as defined variables in analysis."""
        # Verify that the analysis pass (purity.py, dependencies.py)
        # does not flag let: params as undefined variables in the
        # slot body.

    def test_def_side_binding_requires_expression(self):
        """Parse error when def-side let: has no expression."""
        # {% def f() %}{% slot x let:item %}{% end %}{% end %}
        # -> ParseError: "Def-side let:item requires an expression"
```

### Regression tests

All existing tests in `test_nested_def_call_slot.py` must continue to
pass. The `_caller_wrapper` signature change (adding `**_let_kwargs`) is
backward compatible — no existing call passes kwargs. Verify with:

```
poe test -- tests/test_nested_def_call_slot.py -v
```

### AST verification tests

```python
def test_scoped_slot_ast_caller_receives_kwargs(env):
    """Compiled slot with bindings passes kwargs to _caller() call."""
    # Parse and compile: {% def f(x) %}{% slot item let:val=x %}{% end %}{% end %}
    # Inspect the AST: the _caller() call should have keyword(arg="val", ...)

def test_scoped_slot_ast_slot_fn_has_kwonly_params(env):
    """Call-site slot function has keyword-only params from let: declarations."""
    # Parse and compile: {% call f() %}{% slot item let:val %}...{% end %}{% end %}
    # Inspect _caller_item FunctionDef: kwonlyargs should include ast.arg(arg="val")
```

---

## Future Considerations

### Cross-template binding validation

A future analysis pass could validate that call-site `let:` names match
the def-side `let:` names. This requires cross-template analysis (the
def may be in a different file). The `analysis/dependencies.py` visitor
already walks `Slot` nodes (the `_visit_slot` method) and could be
extended to collect binding names per slot, then cross-reference with
`SlotBlock.params` in call sites.

### Shorthand `let:item` (implied `let:item=item`)

When the binding name matches the expression, `let:item=item` is
redundant. A future shorthand could allow `let:item` on the def side
to mean `let:item=item`:

```kida
{% slot row let:item, let:index=loop.index %}
```

Here `let:item` is shorthand for `let:item=item`. This would require
the parser to distinguish def-side shorthand from call-site declaration
(both use `let:name` without `=`). Disambiguation could use block stack
context (already available). Deferred to avoid overloading the initial
syntax.

### Typed scoped slot bindings

Combined with Kida's existing type annotation support on `{% def %}`
parameters, a future enhancement could allow type annotations on `let:`
bindings:

```kida
{% slot row let:item: User = item, let:index: int = loop.index %}
```

This would enable the type checker to validate that the call-site uses
`item` as a `User` instance. Deferred — the type annotation parser
(`_parse_type_annotation`, line 68) would need to be invoked in the
`let:` binding context.

### Deprecation of `provide`/`consume` for slot data

Once scoped slots are available, `provide`/`consume` should be reserved
for its intended purpose: cross-cutting concerns (themes, locale, auth
context). Component libraries that use `provide`/`consume` to pass
per-iteration data to slots should migrate to `let:`. A lint rule could
flag `provide` tags that appear immediately inside `{% for %}` loops
within `{% def %}` bodies, suggesting scoped slots instead.
