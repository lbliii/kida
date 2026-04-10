# RFC: `{% try %}` / `{% fallback %}` — Error Boundaries for Template Rendering

**Status**: Draft
**Created**: 2026-04-09
**Updated**: 2026-04-09
**Related**: Epic: Template Framework Gaps (Sprint 2), RenderContext line tracking, exception hierarchy
**Priority**: P1 (production robustness — broken widget takes down entire page)
**Affects**: kida-templates, downstream apps rendering user-generated or external data

---

## Executive Summary

Templates currently have no way to catch rendering errors. A single undefined
variable or bad filter call crashes the entire page. Error boundaries let
components degrade gracefully by catching errors and rendering fallback content.

This RFC proposes `{% try %}` / `{% fallback %}` — a new block pair that wraps
a risky template subtree with a Python `try`/`except`. If the body renders
successfully, its output is flushed to the main buffer. If it throws, the
output is discarded and the fallback body is rendered instead. An optional
identifier on `{% fallback %}` exposes the caught error to the fallback scope.

| Change | Scope | Effort |
|--------|-------|--------|
| Node: `Try` dataclass | `nodes/control_flow.py` (~8 lines) | Low |
| Parser: `_parse_try()` method | `parser/blocks/error_handling.py` (new, ~50 lines) | Low |
| Parser: register `try` keyword | `parser/statements.py` (1 line) | Low |
| Compiler: `_compile_try()` method | `compiler/statements/error_handling.py` (new, ~120 lines) | Medium |
| Compiler: register `Try` in dispatch | `compiler/core.py` (1 line) | Low |
| Tests: error boundary test suite | `tests/test_error_boundaries.py` (12+ tests) | Medium |

**Zero overhead when no error occurs** — the generated code is a standard
Python `try`/`except` block. The only cost is a list allocation for the
sub-buffer, which is negligible for the small subtrees error boundaries are
designed to protect.

---

## Motivation

### Production apps render untrusted data

Real-world templates render user-generated content, API responses, and
external data that may be incomplete or malformed. A missing field on one
widget should not crash the entire page.

### A broken widget shouldn't take down the whole page

Today, if `{{ user.profile.avatar_url }}` throws an `UndefinedError` because
`profile` is `None`, the entire `render()` call fails. The application sees a
500 error. There is no way to express "try to render this, but show a
placeholder if it fails."

### React's ErrorBoundary proved this pattern matters

React introduced `<ErrorBoundary>` in v16 to catch JavaScript errors in
component trees and display fallback UI. This pattern has become standard
in frontend frameworks. Server-side template engines have not adopted it —
neither Jinja2, Django templates, Mako, nor any Python template engine offers
error boundaries.

### Kida's positioning as a template framework demands this

The epic "Template Framework Composition Gaps" identifies error boundaries as
one of three gaps between Kida and modern component frameworks (alongside
scoped slots and i18n). Closing this gap advances Kida from "better Jinja2"
to "template framework."

---

## Proposed Syntax

### Basic error boundary

```kida
{% try %}
  {{ render_user_widget(user) }}
{% fallback %}
  <div class="error">Widget unavailable</div>
{% end %}
```

### With error access

```kida
{% try %}
  {{ dangerous_component() }}
{% fallback error %}
  <div class="error">Failed: {{ error.message }}</div>
{% end %}
```

The optional identifier after `{% fallback %}` binds the caught exception to a
dict with the following keys:

| Key | Type | Value |
|-----|------|-------|
| `message` | `str` | `str(exception)` |
| `type` | `str` | `type(exception).__name__` (e.g. `"UndefinedError"`) |
| `template` | `str \| None` | `exception.template_name` or `exception.template` if available |
| `line` | `int \| None` | `exception.lineno` if available |

### Semantics

- **Body**: Rendered into a sub-buffer. On success, flushed to main output.
  On exception, discarded entirely.
- **Fallback**: Rendered into the main buffer only when the body throws.
  Streams normally (no buffering needed).
- **Nesting**: Each `{% try %}` is independent. Inner try catches first. If
  the inner fallback also throws, the outer try catches that.
- **No error**: Body renders normally. Fallback body is never compiled into
  the execution path (it is compiled into the except handler).

---

## Node Definition

New node in `src/kida/nodes/control_flow.py` (after `Continue`, line 80):

```python
@final
@dataclass(frozen=True, slots=True)
class Try(Node):
    """Error boundary: {% try %}...{% fallback [error] %}...{% end %}

    Catches rendering errors in body and renders fallback content instead.
    If error_name is set, the caught exception is bound as a dict in the
    fallback scope with keys: message, type, template, line.
    """

    body: tuple[Node, ...]
    fallback: tuple[Node, ...]
    error_name: str | None = None
```

The node must also be re-exported from `src/kida/nodes/__init__.py`:

```python
from kida.nodes.control_flow import (
    AsyncFor, Break, Continue, For, If, Match, Try, While,
)
```

---

## Parser Changes

### New file: `src/kida/parser/blocks/error_handling.py`

```python
"""Error boundary block parsing for Kida parser.

Provides mixin for parsing {% try %}...{% fallback %}...{% end %} blocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida._types import TokenType
from kida.nodes.control_flow import Try

if TYPE_CHECKING:
    from kida._types import Token
    from kida.nodes import Node
    from kida.parser.errors import ParseError

from kida.parser.blocks.core import BlockStackMixin


class ErrorHandlingBlockParsingMixin(BlockStackMixin):
    """Mixin for parsing error boundary blocks."""

    if TYPE_CHECKING:
        _tokens: list[Token]
        _pos: int
        _block_stack: list[tuple[str, int, int]]

        @property
        def _current(self) -> Token: ...
        def _advance(self) -> Token: ...
        def _expect(self, token_type: TokenType) -> Token: ...
        def _error(self, message: str, token: Token | None = None, **kw: object) -> ParseError: ...
        def _parse_body(self, stop_on_continuation: bool = False) -> list[Node]: ...

    def _parse_try(self) -> Try:
        """Parse {% try %}...{% fallback [name] %}...{% end %}.

        Grammar:
            try_block := '{% try %}' body '{% fallback' [NAME] '%}' body '{% end %}'
        """
        start = self._advance()  # consume 'try'
        self._push_block("try", start)
        self._expect(TokenType.BLOCK_END)

        # Parse try body until {% fallback %}
        body = self._parse_body(stop_on_continuation=True)

        # Expect 'fallback' continuation keyword
        if self._current.type != TokenType.NAME or self._current.value != "fallback":
            raise self._error(
                "Expected {% fallback %} inside {% try %} block",
                suggestion="Add a {% fallback %} section to handle errors",
            )
        self._advance()  # consume 'fallback'

        # Optional error name binding
        error_name: str | None = None
        if self._current.type == TokenType.NAME:
            error_name = self._advance().value

        self._expect(TokenType.BLOCK_END)

        # Parse fallback body until {% end %}
        fallback = self._parse_body()

        self._pop_block("try")

        return Try(
            lineno=start.lineno,
            col_offset=start.col_offset,
            body=tuple(body),
            fallback=tuple(fallback),
            error_name=error_name,
        )
```

### Register keyword in `src/kida/parser/statements.py`

Add to `_BLOCK_PARSERS` dict (line 31), in the "Advanced features" section
alongside `match` and `spaceless`:

```python
"try": "_parse_try",
```

Add `"fallback"` to `_CONTINUATION_KEYWORDS` (line 79):

```python
_CONTINUATION_KEYWORDS: frozenset[str] = frozenset(
    {"elif", "else", "empty", "case", "fallback"}
)
```

### Register mixin in `src/kida/parser/blocks/__init__.py`

Import `ErrorHandlingBlockParsingMixin` and add it to the parser's MRO, in the
same pattern as `ControlFlowBlockParsingMixin`.

---

## Compiler Changes

### New file: `src/kida/compiler/statements/error_handling.py`

```python
"""Error boundary compilation for Kida compiler.

Compiles {% try %}...{% fallback %}...{% end %} to Python try/except
with sub-buffer management for streaming safety.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Node
    from kida.nodes.control_flow import Try


class ErrorHandlingMixin:
    """Mixin for compiling error boundary statements."""

    if TYPE_CHECKING:
        _streaming: bool
        _block_counter: int

        def _compile_node(self, node: Node) -> list[ast.stmt]: ...
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...
        def _wrap_with_scope(
            self, body_stmts: list[ast.stmt], source_nodes: object = None
        ) -> list[ast.stmt]: ...
        def _make_line_marker(self, lineno: int) -> ast.stmt: ...

    def _compile_try(self, node: Try) -> list[ast.stmt]:
        """Compile {% try %}...{% fallback %}...{% end %} error boundary.

        Generated code (StringBuilder mode):

            _try_buf_N = []
            _try_append_N = _try_buf_N.append
            _saved_line_N = _rc.line
            try:
                # body compiled with _try_append_N instead of _append
                _append(''.join(_try_buf_N))  # success: flush to main buffer
            except (TemplateRuntimeError, UndefinedError, TypeError, ValueError) as _err_N:
                _rc.line = _saved_line_N  # restore line tracking
                # if error_name: bind error dict to scope
                # fallback body compiled with normal _append
            del _try_buf_N, _try_append_N

        The sub-buffer is critical for streaming mode: if the body fails
        partway through, we must not have already yielded partial output.
        By buffering the try body, we can discard it atomically on error.

        Generated code (streaming mode):

            Same pattern — try body uses _try_append_N (list buffer),
            NOT yield. On success: for _chunk in _try_buf_N: yield _chunk.
            On error: discard buffer, render fallback with yield.
        """
        self._block_counter += 1
        counter = self._block_counter
        buf_name = f"_try_buf_{counter}"
        append_name = f"_try_append_{counter}"
        saved_line = f"_saved_line_{counter}"
        err_name = f"_err_{counter}"

        stmts: list[ast.stmt] = []

        # _try_buf_N = []
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=buf_name, ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            )
        )

        # _try_append_N = _try_buf_N.append
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=append_name, ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id=buf_name, ctx=ast.Load()),
                    attr="append",
                    ctx=ast.Load(),
                ),
            )
        )

        # _saved_line_N = _rc.line
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=saved_line, ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id="_rc", ctx=ast.Load()),
                    attr="line",
                    ctx=ast.Load(),
                ),
            )
        )

        # --- Try body ---
        # Temporarily swap _append to _try_append_N so all output goes to sub-buffer.
        # The approach: compile body normally, then do a textual rewrite of
        # _append references. Instead, we use the same pattern as _compile_cache:
        # rebind _append before the try body, restore after.

        try_body: list[ast.stmt] = []

        # _orig_append_N = _append
        orig_append = f"_orig_append_{counter}"
        try_body.append(
            ast.Assign(
                targets=[ast.Name(id=orig_append, ctx=ast.Store())],
                value=ast.Name(id="_append", ctx=ast.Load()),
            )
        )
        # _append = _try_append_N
        try_body.append(
            ast.Assign(
                targets=[ast.Name(id="_append", ctx=ast.Store())],
                value=ast.Name(id=append_name, ctx=ast.Load()),
            )
        )

        # Compile body nodes
        for child in node.body:
            try_body.extend(self._compile_node(child))

        # _append = _orig_append_N  (restore before flush)
        try_body.append(
            ast.Assign(
                targets=[ast.Name(id="_append", ctx=ast.Store())],
                value=ast.Name(id=orig_append, ctx=ast.Load()),
            )
        )

        # Flush sub-buffer to main output on success
        if self._streaming:
            # for _chunk in _try_buf_N: yield _chunk
            try_body.append(
                ast.For(
                    target=ast.Name(id="_chunk", ctx=ast.Store()),
                    iter=ast.Name(id=buf_name, ctx=ast.Load()),
                    body=[ast.Expr(value=ast.Yield(value=ast.Name(id="_chunk", ctx=ast.Load())))],
                    orelse=[],
                )
            )
        else:
            # _append(''.join(_try_buf_N))
            try_body.append(
                ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id=orig_append, ctx=ast.Load()),
                        args=[
                            ast.Call(
                                func=ast.Attribute(
                                    value=ast.Constant(value=""),
                                    attr="join",
                                    ctx=ast.Load(),
                                ),
                                args=[ast.Name(id=buf_name, ctx=ast.Load())],
                                keywords=[],
                            )
                        ],
                        keywords=[],
                    )
                )
            )

        # --- Except handler ---
        except_body: list[ast.stmt] = []

        # _append = _orig_append_N  (restore in except path too)
        except_body.append(
            ast.Assign(
                targets=[ast.Name(id="_append", ctx=ast.Store())],
                value=ast.Name(id=orig_append, ctx=ast.Load()),
            )
        )

        # _rc.line = _saved_line_N  (restore line tracking)
        except_body.append(
            ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="_rc", ctx=ast.Load()),
                        attr="line",
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id=saved_line, ctx=ast.Load()),
            )
        )

        # If error_name is set, bind error dict to scope
        if node.error_name:
            # error_name = {"message": str(_err_N), "type": type(_err_N).__name__,
            #               "template": getattr(_err_N, "template_name",
            #                           getattr(_err_N, "template", None)),
            #               "line": getattr(_err_N, "lineno", None)}
            error_dict = ast.Dict(
                keys=[
                    ast.Constant(value="message"),
                    ast.Constant(value="type"),
                    ast.Constant(value="template"),
                    ast.Constant(value="line"),
                ],
                values=[
                    # str(_err_N)
                    ast.Call(
                        func=ast.Name(id="str", ctx=ast.Load()),
                        args=[ast.Name(id=err_name, ctx=ast.Load())],
                        keywords=[],
                    ),
                    # type(_err_N).__name__
                    ast.Attribute(
                        value=ast.Call(
                            func=ast.Name(id="type", ctx=ast.Load()),
                            args=[ast.Name(id=err_name, ctx=ast.Load())],
                            keywords=[],
                        ),
                        attr="__name__",
                        ctx=ast.Load(),
                    ),
                    # getattr(_err_N, "template_name", getattr(_err_N, "template", None))
                    ast.Call(
                        func=ast.Name(id="getattr", ctx=ast.Load()),
                        args=[
                            ast.Name(id=err_name, ctx=ast.Load()),
                            ast.Constant(value="template_name"),
                            ast.Call(
                                func=ast.Name(id="getattr", ctx=ast.Load()),
                                args=[
                                    ast.Name(id=err_name, ctx=ast.Load()),
                                    ast.Constant(value="template"),
                                    ast.Constant(value=None),
                                ],
                                keywords=[],
                            ),
                        ],
                        keywords=[],
                    ),
                    # getattr(_err_N, "lineno", None)
                    ast.Call(
                        func=ast.Name(id="getattr", ctx=ast.Load()),
                        args=[
                            ast.Name(id=err_name, ctx=ast.Load()),
                            ast.Constant(value="lineno"),
                            ast.Constant(value=None),
                        ],
                        keywords=[],
                    ),
                ],
            )

            # Bind to scope: _scope_stack[-1]["error_name"] = {...}
            # Or if no scope stack, bind as local: error_name = {...}
            except_body.append(
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Subscript(
                                value=ast.Name(id="_scope_stack", ctx=ast.Load()),
                                slice=ast.Constant(value=-1),
                                ctx=ast.Load(),
                            ),
                            slice=ast.Constant(value=node.error_name),
                            ctx=ast.Store(),
                        )
                    ],
                    value=error_dict,
                )
            )

        # Compile fallback body (uses normal _append / yield)
        for child in node.fallback:
            except_body.extend(self._compile_node(child))

        if not except_body:
            except_body = [ast.Pass()]

        # Exception types to catch
        # From exceptions.py hierarchy:
        #   TemplateRuntimeError (line 368) — covers RequiredValueError, NoneComparisonError
        #   UndefinedError (line 588) — separate branch, not subclass of TemplateRuntimeError
        #   TypeError, ValueError — from Python builtins via filters
        exc_types = ast.Tuple(
            elts=[
                ast.Name(id="_TemplateRuntimeError", ctx=ast.Load()),
                ast.Name(id="_UndefinedError", ctx=ast.Load()),
                ast.Name(id="TypeError", ctx=ast.Load()),
                ast.Name(id="ValueError", ctx=ast.Load()),
            ],
            ctx=ast.Load(),
        )

        # Build the ast.Try
        try_node = ast.Try(
            body=try_body,
            handlers=[
                ast.ExceptHandler(
                    type=exc_types,
                    name=err_name,
                    body=except_body,
                )
            ],
            orelse=[],
            finalbody=[],
        )

        stmts.append(try_node)

        # Cleanup: del _try_buf_N, _try_append_N, _orig_append_N
        stmts.append(
            ast.Delete(
                targets=[
                    ast.Name(id=buf_name, ctx=ast.Del()),
                    ast.Name(id=append_name, ctx=ast.Del()),
                    ast.Name(id=orig_append, ctx=ast.Del()),
                ]
            )
        )

        return stmts
```

### Exception imports in generated code preamble

The generated code references `_TemplateRuntimeError` and `_UndefinedError`.
These must be injected into the template's module scope by the compiler's
preamble generator. The pattern follows existing precedent: the preamble
already imports `_escape`, `_str`, `_Markup`, etc. as module-level names.

Add to the preamble (in `compiler/core.py`, wherever `_escape` and `_Markup`
are imported into the generated module):

```python
from kida.exceptions import TemplateRuntimeError as _TemplateRuntimeError
from kida.exceptions import UndefinedError as _UndefinedError
```

### Register in dispatch table

In `src/kida/compiler/core.py`, add to `_NODE_DISPATCH_NAMES` (line 165):

```python
"Try": "_compile_try",
```

### Register in `_LINE_TRACKED_NODES`

In `src/kida/compiler/core.py`, add to `_LINE_TRACKED_NODES` (line 1684):

```python
"Try",  # Error boundary (line tracking for try block start)
```

### Register mixin in `src/kida/compiler/statements/__init__.py`

Import `ErrorHandlingMixin` and add it to `StatementCompilationMixin`'s
base classes (line 34):

```python
from kida.compiler.statements.error_handling import ErrorHandlingMixin

class StatementCompilationMixin(
    BasicStatementMixin,
    ControlFlowMixin,
    PatternMatchingMixin,
    VariableAssignmentMixin,
    TemplateStructureMixin,
    FunctionCompilationMixin,
    WithBlockMixin,
    CachingMixin,
    SpecialBlockMixin,
    ErrorHandlingMixin,
):
```

---

## Streaming Mode Detail

### The problem

`render_stream()` yields chunks progressively. Once a chunk is yielded, it
cannot be taken back. If a try body partially renders and then throws, the
partial output has already been sent to the client.

### The solution: sub-buffer

Try bodies always compile with a list-based sub-buffer (`_try_buf_N`),
regardless of whether the template is in streaming mode. This is the same
approach used by `_compile_cache` in `compiler/statements/caching.py` (line 94),
which rebinds `_append` to a local buffer and flushes on completion.

| Mode | Try body output | Success flush | Error behavior |
|------|----------------|---------------|----------------|
| StringBuilder | `_try_append_N(chunk)` | `_append(''.join(_try_buf_N))` | Discard `_try_buf_N` |
| Streaming | `_try_append_N(chunk)` | `for _chunk in _try_buf_N: yield _chunk` | Discard `_try_buf_N` |

### Intentional tradeoff

Try blocks opt out of streaming for their body. This is by design: error
boundaries are for risky subtrees (a user widget, an external data card),
not entire pages. The fallback content streams normally after an error.

Document this in user-facing docs: "Use `{% try %}` around small,
failure-prone components. Do not wrap your entire page in `{% try %}` — it
defeats streaming."

---

## Backward Compatibility

**100% backward compatible.** `try` is a new keyword; no existing behavior
changes.

- `try` is a Python reserved word but was **not** a Kida reserved word or
  block keyword prior to this RFC. No existing template can use `try` as a
  variable name in `{% set try = ... %}` because the lexer tokenizes it as
  `NAME` and variable names are unrestricted identifiers — but in practice
  no one names a variable `try` because Python would reject it.
- `fallback` is added as a continuation keyword (like `elif`, `else`,
  `empty`). It is only recognized inside a `{% try %}` block via
  `_parse_body(stop_on_continuation=True)`. Outside that context, `fallback`
  remains a valid variable name.
- No existing tests change. No existing templates break.

---

## Files Modified

| File | Change | Lines (est.) |
|------|--------|-------------|
| `src/kida/nodes/control_flow.py` | Add `Try` dataclass (after `Continue`, line 80) | +10 |
| `src/kida/nodes/__init__.py` | Re-export `Try` from `control_flow` | +1 |
| `src/kida/parser/blocks/error_handling.py` | **New file**: `ErrorHandlingBlockParsingMixin` with `_parse_try()` | +55 |
| `src/kida/parser/blocks/__init__.py` | Import and register `ErrorHandlingBlockParsingMixin` | +2 |
| `src/kida/parser/statements.py` | Add `"try": "_parse_try"` to `_BLOCK_PARSERS` (line 31); add `"fallback"` to `_CONTINUATION_KEYWORDS` (line 79) | +2 |
| `src/kida/compiler/statements/error_handling.py` | **New file**: `ErrorHandlingMixin` with `_compile_try()` | +120 |
| `src/kida/compiler/statements/__init__.py` | Import and register `ErrorHandlingMixin` in `StatementCompilationMixin` | +2 |
| `src/kida/compiler/core.py` | Add `"Try": "_compile_try"` to `_NODE_DISPATCH_NAMES` (line 165); add `"Try"` to `_LINE_TRACKED_NODES` (line 1684) | +2 |
| `src/kida/compiler/core.py` | Add `_TemplateRuntimeError` and `_UndefinedError` imports to generated preamble | +4 |
| `tests/test_error_boundaries.py` | **New file**: 12+ test cases | +200 |

---

## Test Plan

### New test file: `tests/test_error_boundaries.py`

```python
class TestTryBasic:
    """Basic error boundary behavior."""

    def test_undefined_variable_caught(self, env):
        """Undefined variable in try body renders fallback."""
        # {% try %}{{ missing_var }}{% fallback %}safe{% end %}
        # → "safe"

    def test_no_error_renders_body(self, env):
        """When no error occurs, body renders normally with no overhead."""
        # {% try %}{{ greeting }}{% fallback %}fallback{% end %}
        # render(greeting="hello") → "hello"

    def test_filter_error_caught(self, env):
        """Filter that raises ValueError is caught."""
        # {% try %}{{ "abc" | int }}{% fallback %}not a number{% end %}
        # → "not a number"

    def test_required_value_error_caught(self, env):
        """RequiredValueError from | require filter is caught."""
        # {% try %}{{ value | require }}{% fallback %}missing{% end %}
        # render(value=None) → "missing"


class TestTryErrorAccess:
    """{% fallback err %} exposes error details."""

    def test_error_message(self, env):
        """err.message contains the exception message string."""
        # {% try %}{{ x }}{% fallback err %}{{ err.message }}{% end %}
        # → contains "Undefined variable 'x'"

    def test_error_type(self, env):
        """err.type is the exception class name."""
        # {% try %}{{ x }}{% fallback err %}{{ err.type }}{% end %}
        # → "UndefinedError"

    def test_error_template_and_line(self, env):
        """err.template and err.line reflect source location."""
        # Load from named template, verify err.template and err.line

    def test_error_from_runtime_error(self, env):
        """TemplateRuntimeError subclass populates all error fields."""
        # Use a filter or expression that raises TemplateRuntimeError


class TestTryNesting:
    """Nested try blocks."""

    def test_inner_try_catches_first(self, env):
        """Inner try catches error before outer try sees it."""
        # {% try %}
        #   {% try %}{{ missing }}{% fallback %}inner fallback{% end %}
        # {% fallback %}outer fallback{% end %}
        # → "inner fallback"

    def test_inner_fallback_throws_outer_catches(self, env):
        """If inner fallback also throws, outer try catches it."""
        # {% try %}
        #   {% try %}{{ a }}{% fallback %}{{ b }}{% end %}
        # {% fallback %}outer safe{% end %}
        # render() with neither a nor b defined → "outer safe"


class TestTryStreaming:
    """Streaming mode: partial output not leaked."""

    def test_partial_output_not_leaked(self, env):
        """Try body that partially renders then errors: no partial in output."""
        # {% try %}before{{ missing }}after{% fallback %}safe{% end %}
        # Collect all chunks from render_stream()
        # Assert "before" does NOT appear in output
        # Assert "safe" appears in output


class TestTryWithComponents:
    """Integration with slots, includes, provide/consume."""

    def test_try_with_include(self, env):
        """Error in included template caught by surrounding try."""
        # included.html: {{ undefined_var }}
        # main: {% try %}{% include "included.html" %}{% fallback %}safe{% end %}
        # → "safe"

    def test_try_around_for_loop(self, env):
        """Error during for loop iteration replaces entire loop with fallback."""
        # {% try %}{% for item in items %}{{ item.name }}{% end %}{% fallback %}no items{% end %}
        # render(items=[{"name": "a"}, None]) — None.name throws
        # → "no items" (not "a" followed by error)

    def test_try_with_provide_consume(self, env):
        """Error in try body does not leak provided values."""
        # {% try %}
        #   {% provide theme = "dark" %}
        #     {{ missing }}
        #   {% end %}
        # {% fallback %}
        #   theme={{ consume("theme", "none") }}
        # {% end %}
        # → "theme=none" — the provide was inside the try body scope,
        #   and the error discarded it. The provide/unprovide is handled
        #   by the compiled finally block around {% provide %}, so the
        #   stack is clean.

    def test_try_with_slots(self, env):
        """Error in slot content caught by surrounding try."""
        # {% def card() %}<div>{% slot %}</div>{% end %}
        # {% try %}
        #   {% call card() %}{{ missing }}{% end %}
        # {% fallback %}safe{% end %}
        # → "safe"
```

### Test count: 14 tests (exceeds minimum of 12)

### Regression tests

All existing test suites must pass unchanged:
- `tests/test_control_flow.py`
- `tests/test_nested_def_call_slot.py`
- `tests/test_yield_directive.py`
- `tests/test_streaming.py`

---

## Error Handling & Diagnostics

### Parse errors

`_parse_try` produces clear errors for malformed usage:

| Input | Error |
|-------|-------|
| `{% try %}body{% end %}` | "Expected {% fallback %} inside {% try %} block" |
| `{% try %}body{% fallback` (EOF) | "Expected %}, got EOF" |
| `{% try %}` (no fallback, no end) | "Expected {% fallback %} inside {% try %} block" |

### Runtime behavior

| Scenario | Behavior |
|----------|----------|
| Body succeeds | Body output flushed, fallback never executed |
| Body throws `UndefinedError` | Buffer discarded, fallback rendered |
| Body throws `TemplateRuntimeError` | Buffer discarded, fallback rendered |
| Body throws `RequiredValueError` | Caught (subclass of `TemplateRuntimeError`) |
| Body throws `TypeError` | Caught (from filter/attribute access) |
| Body throws `ValueError` | Caught (from filter conversion) |
| Body throws `TemplateSyntaxError` | **NOT caught** — compile-time error, should never occur at render time |
| Body throws `KeyError` / `AttributeError` | **NOT caught** — these are wrapped into `TemplateRuntimeError` or `UndefinedError` by the runtime before reaching user code |
| Fallback body throws | Exception propagates normally (or caught by outer try) |

### Exceptions NOT caught (by design)

- `TemplateSyntaxError` — compile-time, not render-time
- `TemplateNotFoundError` — missing template is a deployment error, not a data error
- `SystemExit`, `KeyboardInterrupt`, `MemoryError` — system-level, must propagate
- `Exception` (general) — error boundaries catch **data errors**, not programming errors

---

## Alternatives Considered

### A. `undefined="default"` on individual expressions

Allow `{{ var | default("fallback") }}` patterns. This already exists and
works for single variables, but cannot protect a block of multiple expressions,
nested includes, or macro calls. Error boundaries protect subtrees, not
individual values.

**Rejected as sole solution**: Doesn't address multi-expression blocks or
errors inside includes/macros.

### B. `{% if has_var("x") %}` guards

Wrap risky blocks in explicit existence checks.

**Rejected**: Verbose and incomplete — doesn't catch filter errors, attribute
access on None, or errors in included templates. Also requires knowing which
variables might be missing, which isn't always possible with external data.

### C. Global `on_error` callback on Environment

```python
env = Environment(on_error=lambda err: f"<div class='error'>{err}</div>")
```

**Rejected**: Too coarse. Different components need different fallback content.
A global handler can't render component-specific fallback markup. Also doesn't
solve the streaming buffering problem.

### D. Catch all `Exception` types

Broaden the except clause to catch any exception.

**Rejected**: Dangerous. Catching `RuntimeError`, `AttributeError`, etc. would
mask genuine programming errors. The selected set (`TemplateRuntimeError`,
`UndefinedError`, `TypeError`, `ValueError`) covers data-related failures
while letting programming errors propagate.

---

## Future Considerations

### `{% try %}` with `{% finally %}`

A future enhancement could add `{% finally %}` for cleanup logic:

```kida
{% try %}
  {{ risky_thing() }}
{% fallback %}
  fallback content
{% finally %}
  {{ cleanup() }}
{% end %}
```

This would compile to Python's `try`/`except`/`finally`. Out of scope for
this RFC since the primary use case (fallback rendering) doesn't need cleanup.

### `{% try %}` without `{% fallback %}` (silent swallow)

```kida
{% try %}
  {{ optional_widget() }}
{% end %}
```

Could silently swallow errors, rendering nothing on failure. This is
convenient but dangerous (hides bugs). If added, it should require an
explicit opt-in, e.g. `{% try silent %}`. Out of scope for this RFC.

### Error logging hook

When a try block catches an error, applications may want to log it even
though the page renders successfully. A future `env.on_try_catch` callback
could enable this:

```python
env = Environment()
env.on_try_catch = lambda err, template, line: logger.warning(f"Caught: {err}")
```

This is orthogonal to the template syntax and can be added later without
breaking changes.

### Performance: skip sub-buffer when not streaming

In StringBuilder mode (the common case), the sub-buffer join adds one string
concatenation. A future optimization could detect when the body contains only
a single output node and inline it without buffering. This micro-optimization
is not worth the complexity for the initial implementation.

### Interaction with `{% provide %}` / `{% consume %}`

The `{% provide %}` block compiles with a `try`/`finally` to ensure
`unprovide()` is called (see `RenderContext.unprovide`, line 196 of
`render_context.py`). When a `{% provide %}` is inside a `{% try %}` body
and the body errors, the `finally` from provide runs before the `except`
from try, ensuring the provider stack is clean. This means provided values
do not leak into the fallback scope. No special handling needed.

### Interaction with `{% cache %}`

If a `{% cache %}` block is inside a `{% try %}` body and the body errors,
the cache entry is not written (the cache block uses its own sub-buffer,
which is also discarded). If a `{% try %}` is inside a `{% cache %}` body
and the fallback renders, the fallback content is cached. Both interactions
are correct without special handling.
