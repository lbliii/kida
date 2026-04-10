# RFC: `{% trans %}` — Internationalization Support

**Status**: Draft
**Created**: 2026-04-09
**Updated**: 2026-04-09
**Related**: Epic: Template Framework Gaps (Sprint 3), Markup Security Hardening RFC
**Priority**: P1 (feature parity — i18n is table stakes for framework-level template tools)
**Affects**: kida-templates, downstream apps with non-English deployments

---

## Executive Summary

Kida has no built-in i18n support. Templates that need translated strings
must receive pre-translated values from application code — every project
reinvents translation wiring, and message extraction is impossible without
AST access that only the engine has.

This RFC adds:

1. **`{% trans %}` blocks** — translatable string regions with variable bindings
2. **`{% plural %}` delimiter** — singular/plural forms via `ngettext`
3. **`{{ _("literal") }}` shorthand** — inline gettext calls
4. **`{{ _n(singular, plural, count) }}` shorthand** — inline ngettext calls
5. **Message extraction CLI** — `kida extract templates/ -o messages.pot`
6. **Babel extractor plugin** — `kida.babel:extract` for pybabel integration
7. **Pluggable gettext backend** — `env.install_translations()` with identity-function default

| Change | Scope | Effort |
|--------|-------|--------|
| Nodes: `Trans`, `TransVar` | `nodes/structure.py` | Low |
| Parser: `_parse_trans` | `parser/blocks/i18n.py` (new) | Medium |
| Parser: register `trans` keyword | `parser/statements.py` (2 lines) | Low |
| Compiler: `_compile_trans` | `compiler/statements/i18n.py` (new) | Medium |
| Compiler: register `Trans` dispatch | `compiler/core.py` (1 line) | Low |
| Environment: translation backend | `environment/core.py` (~20 lines) | Low |
| Analysis: message extraction | `analysis/i18n.py` (new) | Medium |
| CLI: extract command | `cli/` | Low |
| Tests: new test suite (16+ tests) | `tests/test_i18n.py` | Medium |

**Zero breaking changes** — `trans` is new syntax. The `_` and `_n`
globals are injected only when translations are installed (or as
identity functions by default).

---

## Motivation

### Why native i18n?

1. **Table stakes**: Every major template engine ships i18n. Jinja2 has
   the `jinja2.ext.i18n` extension. Django has `{% blocktrans %}` and
   `{% translate %}`. Without native support, Kida cannot serve
   internationally deployed applications.

2. **Message extraction requires AST access**: Extracting translatable
   strings from templates requires walking the AST — only the engine
   can do this reliably. External tools that parse template syntax with
   regex are fragile and miss edge cases (nested expressions, whitespace
   normalization, pluralization patterns).

3. **Escaping semantics are engine-specific**: The interaction between
   translated strings, variable interpolation, and HTML auto-escaping
   (`Markup` class in `kida/utils/html.py`) must be handled at the
   engine level. Application-level translation cannot know whether a
   variable value needs escaping before interpolation into a translated
   string.

4. **Every project reinvents the wiring**: Without `{% trans %}`, each
   application must pass pre-translated strings through the render
   context, losing the ability to extract messages, validate
   completeness, or switch languages at render time.

---

## Syntax

### Simple translation

```kida
{% trans %}Hello, world!{% endtrans %}
```

Extracts message ID: `"Hello, world!"`
Compiles to: `_gettext("Hello, world!")`

### With variables

```kida
{% trans name=user.name %}Hello, {{ name }}!{% endtrans %}
```

Extracts message ID: `"Hello, %(name)s!"`
Compiles to: `_gettext("Hello, %(name)s!") % {"name": escape(name_value)}`

Variable bindings are declared in the `{% trans %}` tag. Inside the body,
only simple `{{ name }}` references are allowed — no filters, no attribute
access, no method calls. This constraint ensures message IDs are
predictable and extractable.

### Pluralization

```kida
{% trans count=items|length %}
  One item found.
{% plural %}
  {{ count }} items found.
{% endtrans %}
```

Extracts: singular `"One item found."`, plural `"%(count)s items found."`
Compiles to: `_ngettext("One item found.", "%(count)s items found.", count) % {"count": count_value}`

The `count` variable is required when `{% plural %}` is present — it
serves as the dispatch value for `ngettext`.

### Shorthand (expression-level)

```kida
{{ _("Hello") }}
{{ _n("%(count)s item", "%(count)s items", count) }}
```

`_` and `_n` are registered as template globals pointing to the
configured `gettext` and `ngettext` functions. These work in any
expression context — output tags, filter arguments, macro parameters.

### Whitespace handling

```kida
{%- trans -%}
  Hello, world!
{%- endtrans -%}
```

Standard Kida whitespace trimming (`-`) applies to the outer delimiters.
Inside the trans body, leading/trailing whitespace is stripped and
internal whitespace is normalized to single spaces for the message ID.

---

## Environment Configuration

### Installing translations

```python
import gettext
translations = gettext.translation("myapp", "locales", languages=["fr"])

env = Environment(loader=loader)
env.install_translations(translations)
```

`install_translations` extracts `gettext` and `ngettext` methods from
the translations object and registers them as globals.

### Direct callable installation

```python
env.install_gettext_callables(
    gettext=my_gettext_func,
    ngettext=my_ngettext_func,
)
```

### Default behavior (no translations installed)

When no translations are installed, `_` is an identity function
(`lambda s: s`) and `_n` selects singular/plural by count
(`lambda s, p, n: s if n == 1 else p`). Templates render untranslated
strings — zero-config works.

### Implementation in `environment/core.py`

```python
@dataclass
class Environment:
    # ... existing fields ...

    def install_translations(self, translations: Any) -> None:
        """Install a gettext translations object.

        The object must have gettext() and ngettext() methods
        (standard library gettext.GNUTranslations interface).
        """
        self.install_gettext_callables(
            gettext=translations.gettext,
            ngettext=translations.ngettext,
        )

    def install_gettext_callables(
        self,
        gettext: Callable[[str], str],
        ngettext: Callable[[str, str, int], str],
    ) -> None:
        """Install gettext/ngettext functions directly.

        These are registered as template globals `_` and `_n`, and
        stored as `_gettext`/`_ngettext` for compiler access.
        """
        self.globals["_"] = gettext
        self.globals["_n"] = ngettext
        self._gettext = gettext
        self._ngettext = ngettext
```

The `__post_init__` method installs identity defaults:

```python
def __post_init__(self) -> None:
    # ... existing init ...

    # i18n defaults (identity functions)
    if "_" not in self.globals:
        self.globals["_"] = _identity_gettext
        self.globals["_n"] = _identity_ngettext
        self._gettext = _identity_gettext
        self._ngettext = _identity_ngettext
```

Where the identity functions are module-level:

```python
def _identity_gettext(message: str) -> str:
    return message

def _identity_ngettext(singular: str, plural: str, n: int) -> str:
    return singular if n == 1 else plural
```

---

## Node Definitions

New nodes in `src/kida/nodes/structure.py`, following the existing
`@final @dataclass(frozen=True, slots=True)` pattern used by `Block`,
`Cache`, `Provide`, and all other structure nodes:

```python
@final
@dataclass(frozen=True, slots=True)
class TransVar(Node):
    """Variable binding in {% trans name=expr %}.

    Binds a template expression to a simple name for use inside
    the trans body as {{ name }}.
    """

    name: str
    expr: Expr


@final
@dataclass(frozen=True, slots=True)
class Trans(Node):
    """{% trans %}...{% endtrans %} block.

    Represents a translatable string region. The singular field holds
    the message ID with %(name)s placeholders. When {% plural %} is
    present, the plural field holds the plural form and count_expr
    provides the ngettext dispatch value.
    """

    singular: str                              # Message ID: "Hello, %(name)s!"
    plural: str | None = None                  # Plural form, if {% plural %} present
    variables: tuple[TransVar, ...] = ()       # Variable bindings from tag
    count_expr: Expr | None = None             # Expression for ngettext count
```

These nodes must be registered in `src/kida/nodes/__init__.py`:

```python
from kida.nodes.structure import (
    # ... existing ...
    Trans,
    TransVar,
)

__all__ = [
    # ... existing ...
    "Trans",
    "TransVar",
]
```

### Design rationale

- `singular` and `plural` are plain strings (the extracted message IDs),
  not AST node sequences. The parser builds these strings by replacing
  `{{ name }}` with `%(name)s` during parsing. This makes extraction
  trivial — just read the field.

- `variables` is a tuple of `TransVar` (not a dict) to preserve
  declaration order and source locations for each binding.

- `count_expr` is separated from `variables` because it has special
  semantics — it is the ngettext dispatch value, not just an
  interpolation variable.

---

## Parser Changes

### New file: `src/kida/parser/blocks/i18n.py`

```python
"""i18n block parsing for Kida parser.

Provides mixin for parsing {% trans %} blocks with variable bindings,
pluralization via {% plural %}, and message ID extraction.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from kida._types import TokenType
from kida.nodes import Trans, TransVar

if TYPE_CHECKING:
    from kida.nodes import Expr, Node


class I18nParsingMixin:
    """Mixin for parsing {% trans %}...{% endtrans %} blocks."""

    def _parse_trans(self) -> Trans:
        """Parse {% trans [var=expr, ...] %}...{% endtrans %}.

        Syntax:
            {% trans %}literal body{% endtrans %}
            {% trans name=expr %}Hello, {{ name }}!{% endtrans %}
            {% trans count=expr %}One item.{% plural %}{{ count }} items.{% endtrans %}

        Body restrictions:
            - Only {{ name }} references allowed (simple names)
            - No filters, attribute access, or method calls
            - All referenced names must be declared in the {% trans %} tag
        """
        start = self._advance()  # consume 'trans'

        # Parse variable bindings: name=expr, name=expr
        variables: list[TransVar] = []
        count_expr: Expr | None = None

        while self._current.type == TokenType.NAME:
            var_name = self._advance().value
            self._expect(TokenType.ASSIGN)  # '='
            var_expr = self._parse_expression()
            var_node = TransVar(
                lineno=start.lineno,
                col_offset=start.col_offset,
                name=var_name,
                expr=var_expr,
            )
            variables.append(var_node)
            if var_name == "count":
                count_expr = var_expr
            if not self._match(TokenType.COMMA):
                break

        self._expect(TokenType.BLOCK_END)

        # Collect declared variable names for validation
        declared_names = {v.name for v in variables}

        # Parse body: collect text and {{ name }} references
        singular_parts, plural_parts, has_plural = self._parse_trans_body(
            declared_names
        )

        singular = self._normalize_message(" ".join(singular_parts))
        plural_str: str | None = None
        if has_plural:
            plural_str = self._normalize_message(" ".join(plural_parts))
            if count_expr is None:
                raise self._error(
                    "{% plural %} requires a 'count' variable in {% trans %}",
                    suggestion="Add count=expr to the {% trans %} tag: "
                    "{% trans count=items|length %}",
                )

        return Trans(
            lineno=start.lineno,
            col_offset=start.col_offset,
            singular=singular,
            plural=plural_str,
            variables=tuple(variables),
            count_expr=count_expr,
        )
```

### Body parsing detail

`_parse_trans_body` reads tokens until `{% endtrans %}` or `{% end %}`.
When it encounters `{% plural %}`, it switches from collecting singular
parts to plural parts. Text tokens become literal strings. Variable
output tokens (`{{ name }}`) are validated against `declared_names` and
converted to `%(name)s` in the message ID string.

```python
    def _parse_trans_body(
        self, declared_names: set[str]
    ) -> tuple[list[str], list[str], bool]:
        """Parse trans block body, returning singular parts, plural parts, and has_plural flag."""
        singular_parts: list[str] = []
        plural_parts: list[str] = []
        current_parts = singular_parts
        has_plural = False

        while True:
            if self._current.type == TokenType.DATA:
                current_parts.append(self._advance().value)

            elif self._current.type == TokenType.VARIABLE_BEGIN:
                self._advance()  # consume {{
                if self._current.type != TokenType.NAME:
                    raise self._error(
                        "Only simple variable names allowed inside {% trans %} body",
                        suggestion="Use variable bindings: {% trans name=user.name %}{{ name }}{% endtrans %}",
                    )
                ref_name = self._advance().value
                if ref_name not in declared_names:
                    raise self._error(
                        f"Undeclared variable '{{ ref_name }}' in {% trans %} body",
                        suggestion=f"Add {ref_name}=expr to the {{% trans %}} tag",
                    )
                # Check for filters or attribute access (forbidden)
                if self._current.type not in (TokenType.VARIABLE_END,):
                    raise self._error(
                        f"Complex expressions not allowed inside {{% trans %}} body "
                        f"(found {self._current.type} after '{ref_name}')",
                        suggestion=f"Bind the expression in the tag: "
                        f"{{% trans {ref_name}=your_expr %}}{{{{ {ref_name} }}}}{{% endtrans %}}",
                    )
                self._expect(TokenType.VARIABLE_END)
                current_parts.append(f"%({ref_name})s")

            elif self._current.type == TokenType.BLOCK_BEGIN:
                self._advance()  # consume {%
                keyword = self._current.value
                if keyword in ("endtrans", "end"):
                    self._advance()  # consume keyword
                    self._expect(TokenType.BLOCK_END)
                    break
                elif keyword == "plural":
                    if has_plural:
                        raise self._error("Duplicate {% plural %} in {% trans %} block")
                    self._advance()  # consume 'plural'
                    self._expect(TokenType.BLOCK_END)
                    has_plural = True
                    current_parts = plural_parts
                else:
                    raise self._error(
                        f"Unexpected block tag '{keyword}' inside {{% trans %}}",
                        suggestion="Only {% plural %} and {% endtrans %} are allowed inside {% trans %}",
                    )
            else:
                raise self._error(
                    f"Unexpected token {self._current.type} inside {{% trans %}} body"
                )

        return singular_parts, plural_parts, has_plural

    @staticmethod
    def _normalize_message(msg: str) -> str:
        """Normalize whitespace in a message ID.

        Strips leading/trailing whitespace and collapses internal
        whitespace to single spaces. This ensures consistent message
        IDs regardless of template formatting.
        """
        return " ".join(msg.split())
```

### Register keyword in `src/kida/parser/statements.py`

Add to `_BLOCK_PARSERS`:

```python
_BLOCK_PARSERS: dict[str, str] = {
    # ... existing entries ...
    # i18n
    "trans": "_parse_trans",
}
```

Add to `_END_KEYWORDS`:

```python
_END_KEYWORDS: frozenset[str] = frozenset({
    # ... existing entries ...
    "endtrans",
})
```

### Nested trans validation

The parser must detect and reject nested `{% trans %}` blocks. When
`_parse_trans` is entered, it should check the block stack:

```python
if self._block_stack and self._block_stack[-1][0] == "trans":
    raise self._error(
        "{% trans %} blocks cannot be nested",
        suggestion="Extract the inner translation to a separate variable",
    )
```

---

## Compiler Changes

### New file: `src/kida/compiler/statements/i18n.py`

Following the mixin pattern used by `BasicStatementMixin` in
`compiler/statements/basic.py`, `ControlFlowMixin` in
`compiler/statements/control_flow.py`, etc.

```python
"""i18n statement compilation for Kida compiler.

Compiles Trans nodes to gettext/ngettext calls with proper HTML escaping.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Node, Trans


class I18nStatementMixin:
    """Mixin for compiling {% trans %} blocks."""

    if TYPE_CHECKING:
        _streaming: bool
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...
        def _emit_output(self, value_expr: ast.expr) -> ast.stmt: ...

    def _compile_trans(self, node: Trans) -> list[ast.stmt]:
        """Compile {% trans %}...{% endtrans %} to gettext/ngettext calls.

        Singular (no variables):
            _append(_escape(_gettext("Hello, world!")))

        Singular with variables:
            _append(_escape(_gettext("Hello, %(name)s!") % {"name": name_value}))

        Plural:
            _append(_escape(_ngettext("One item.", "%(count)s items.", count)
                    % {"count": count_value}))

        HTML escaping strategy:
            1. Call gettext/ngettext with raw message ID (no escaping)
            2. Escape each variable value individually
            3. Use Markup() % {escaped_vars} for interpolation
               (Markup.__mod__ auto-escapes non-Markup values)
        """
        stmts: list[ast.stmt] = []

        # Build the variable dict: {"name": compiled_expr, ...}
        var_keys: list[ast.expr] = []
        var_values: list[ast.expr] = []
        for tv in node.variables:
            var_keys.append(ast.Constant(value=tv.name))
            var_values.append(self._compile_expr(tv.expr))

        # gettext or ngettext call
        if node.plural is not None and node.count_expr is not None:
            # _ngettext(singular, plural, count)
            translate_call = ast.Call(
                func=ast.Name(id="_ngettext", ctx=ast.Load()),
                args=[
                    ast.Constant(value=node.singular),
                    ast.Constant(value=node.plural),
                    self._compile_expr(node.count_expr),
                ],
                keywords=[],
            )
        else:
            # _gettext(singular)
            translate_call = ast.Call(
                func=ast.Name(id="_gettext", ctx=ast.Load()),
                args=[ast.Constant(value=node.singular)],
                keywords=[],
            )

        # If there are variables, apply %-formatting with Markup
        if node.variables:
            # Markup(translated_string) % {"name": value, ...}
            markup_wrapped = ast.Call(
                func=ast.Name(id="_Markup", ctx=ast.Load()),
                args=[translate_call],
                keywords=[],
            )
            format_dict = ast.Dict(keys=var_keys, values=var_values)
            result_expr = ast.BinOp(
                left=markup_wrapped,
                op=ast.Mod(),
                right=format_dict,
            )
        else:
            # No variables — escape the translated string directly
            result_expr = ast.Call(
                func=ast.Name(id="_escape", ctx=ast.Load()),
                args=[translate_call],
                keywords=[],
            )

        stmts.append(self._emit_output(result_expr))
        return stmts
```

### Register in compiler dispatch

In `src/kida/compiler/core.py`, add to `_NODE_DISPATCH_NAMES`:

```python
_NODE_DISPATCH_NAMES: ClassVar[dict[str, str]] = {
    # ... existing entries ...
    "Trans": "_compile_trans",
}
```

### Compiler globals

The compiler must ensure `_gettext`, `_ngettext`, and `_Markup` are
available in the compiled template's namespace. These are injected in
the template execution namespace alongside `_escape`, `_str`, etc.

In `src/kida/template.py` (or wherever the execution namespace is built):

```python
namespace = {
    # ... existing ...
    "_gettext": env._gettext,
    "_ngettext": env._ngettext,
    "_Markup": Markup,
}
```

---

## Analysis: Message Extraction

### New file: `src/kida/analysis/i18n.py`

Following the `NodeVisitor` pattern from `analysis/node_visitor.py`
and the `DependencyWalker` pattern from `analysis/dependencies.py`:

```python
"""Message extraction for i18n support.

Walks the AST and collects translatable strings from Trans nodes
and _() / _n() function calls. Outputs standard PO template format.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kida.analysis.node_visitor import NodeVisitor

if TYPE_CHECKING:
    from kida.nodes import FuncCall, Node, Trans


@dataclass(frozen=True, slots=True)
class ExtractedMessage:
    """A translatable message extracted from a template."""

    filename: str
    lineno: int
    function: str            # "gettext" or "ngettext"
    message: str | tuple[str, str]  # singular or (singular, plural)
    comments: tuple[str, ...] = ()


class ExtractMessagesVisitor(NodeVisitor):
    """Walk AST and collect translatable messages.

    Collects messages from:
    - Trans nodes ({% trans %}...{% endtrans %})
    - FuncCall nodes calling _() or _n()
    """

    def __init__(self, filename: str = "<template>") -> None:
        self._filename = filename
        self._messages: list[ExtractedMessage] = []

    def extract(self, node: Node) -> list[ExtractedMessage]:
        """Extract all translatable messages from an AST."""
        self._messages = []
        self.visit(node)
        return list(self._messages)

    def visit_Trans(self, node: Trans) -> None:  # noqa: N802
        """Extract message from {% trans %} block."""
        if node.plural is not None:
            self._messages.append(ExtractedMessage(
                filename=self._filename,
                lineno=node.lineno,
                function="ngettext",
                message=(node.singular, node.plural),
            ))
        else:
            self._messages.append(ExtractedMessage(
                filename=self._filename,
                lineno=node.lineno,
                function="gettext",
                message=node.singular,
            ))

    def visit_FuncCall(self, node: FuncCall) -> None:  # noqa: N802
        """Extract message from _("literal") or _n("s", "p", n) calls."""
        from kida.nodes import Const, Name

        if not isinstance(node.func, Name):
            self.generic_visit(node)
            return

        if node.func.name == "_" and len(node.args) == 1:
            arg = node.args[0]
            if isinstance(arg, Const) and isinstance(arg.value, str):
                self._messages.append(ExtractedMessage(
                    filename=self._filename,
                    lineno=node.lineno,
                    function="gettext",
                    message=arg.value,
                ))

        elif node.func.name == "_n" and len(node.args) >= 2:
            singular_arg = node.args[0]
            plural_arg = node.args[1]
            if (
                isinstance(singular_arg, Const)
                and isinstance(singular_arg.value, str)
                and isinstance(plural_arg, Const)
                and isinstance(plural_arg.value, str)
            ):
                self._messages.append(ExtractedMessage(
                    filename=self._filename,
                    lineno=node.lineno,
                    function="ngettext",
                    message=(singular_arg.value, plural_arg.value),
                ))

        self.generic_visit(node)
```

### CLI command

`kida extract templates/ -o messages.pot`

The CLI loads each template via the environment, parses it to AST, runs
`ExtractMessagesVisitor`, and writes a standard `.pot` file:

```
# SOME DESCRIPTIVE TITLE.
# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.
#
#, fuzzy
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"

#: templates/index.html:5
msgid "Hello, %(name)s!"
msgstr ""

#: templates/index.html:10
msgid "One item found."
msgid_plural "%(count)s items found."
msgstr[0] ""
msgstr[1] ""
```

### Babel extractor plugin

For projects using pybabel, provide an entry point:

```python
# src/kida/babel.py

def extract(fileobj, keywords, comment_tags, options):
    """Babel extraction method for Kida templates.

    Usage in babel.cfg:
        [kida: templates/**.html]
        encoding = utf-8
    """
    from kida import Environment
    from kida.analysis.i18n import ExtractMessagesVisitor

    source = fileobj.read().decode(options.get("encoding", "utf-8"))
    env = Environment()
    ast = env._parse(source, name=fileobj.name)

    visitor = ExtractMessagesVisitor(filename=fileobj.name)
    messages = visitor.extract(ast)

    for msg in messages:
        if isinstance(msg.message, tuple):
            yield (msg.lineno, msg.function, msg.message, list(msg.comments))
        else:
            yield (msg.lineno, msg.function, msg.message, list(msg.comments))
```

Registered via `pyproject.toml`:

```toml
[project.entry-points."babel.extractors"]
kida = "kida.babel:extract"
```

---

## HTML Escaping Interaction

The interaction between translation and HTML escaping is the most
security-sensitive aspect of this design. The strategy leverages
Kida's `Markup` class (`src/kida/utils/html.py`) which auto-escapes
non-Markup values in `%`-formatting and `.format()` calls.

### Escaping rules

1. **Translated strings are NOT auto-escaped** — they may contain
   intentional HTML like `<em>important</em>`. The translator is
   trusted to produce safe markup.

2. **Variable interpolations ARE escaped** — `Markup("Hello, %(name)s!") % {"name": user_input}`
   auto-escapes `user_input` via `Markup.__mod__` (line 219-230 in
   `utils/html.py`), which calls `_escape_arg` on each value.

3. **Markup passthrough** — if a variable value is already `Markup`,
   it is NOT double-escaped. `_escape_arg` (line 381-391 in
   `utils/html.py`) checks `isinstance(value, Markup)` and returns
   it unchanged.

4. **No-variable translations** — when there are no variables, the
   translated string is escaped via `_escape()` (the standard
   autoescape function). This handles the case where a translation
   accidentally contains `<` or `&`.

### Security documentation

Translators should NOT include user-controlled content directly in
translation strings. The pattern is:

```
GOOD: _("Hello, %(name)s!") % {"name": user_input}   # user_input escaped
BAD:  _(f"Hello, {user_input}!")                       # user_input in message ID
```

This must be documented prominently in the i18n guide.

---

## Compile-Time Optimization

When `env.optimize_translations = True` and the gettext function is
registered as a pure function, trans blocks with constant message IDs
and no variables can be folded at compile time during partial evaluation
(`src/kida/compiler/partial_eval.py`).

### Registration

Add `_` and `_n` to the pure function registry when optimization is
enabled:

```python
# In partial_eval.py or environment setup
if env.optimize_translations:
    pure_functions.add("_gettext")
    pure_functions.add("_ngettext")
```

### Folding example

```kida
{% trans %}Welcome{% endtrans %}
```

With `optimize_translations=True` and a French translations object:

- Compile time: `_gettext("Welcome")` evaluates to `"Bienvenue"`
- Compiled output: `_append("Bienvenue")` — zero runtime translation cost

This is useful for static sites where the language is known at build
time.

---

## Dependency Analysis Integration

### `DependencyWalker` update

Add a visitor in `src/kida/analysis/dependencies.py`:

```python
def visit_Trans(self, node: Trans) -> None:  # noqa: N802
    """Handle trans block: visit variable expressions."""
    for tv in node.variables:
        self.visit(tv.expr)
    if node.count_expr is not None:
        self.visit(node.count_expr)

def visit_TransVar(self, node: TransVar) -> None:  # noqa: N802
    """Handle trans variable binding."""
    self.visit(node.expr)
```

### `PurityAnalyzer` update

Trans blocks that call `_gettext`/`_ngettext` are impure by default
(translation functions may read locale state). When
`optimize_translations` is enabled, they are treated as pure.

---

## Backward Compatibility

**100% backward compatible.** This RFC introduces only new syntax and
new API surface.

- `trans` is a new keyword that does not conflict with any existing
  syntax. It was not previously reserved.
- `_` is commonly used as a variable name (e.g., `{% for _ in range(3) %}`).
  The global `_` only conflicts if someone has `{% let _ = ... %}` at
  template scope. This is documented but not expected to be common.
- `_n` has no known conflicts.
- Existing templates continue to work unchanged whether or not
  translations are installed (identity functions are the default).

---

## Files Modified

| File | Change | Lines (est.) |
|------|--------|-------------|
| `src/kida/nodes/structure.py` | Add `Trans`, `TransVar` node definitions | ~25 |
| `src/kida/nodes/__init__.py` | Re-export `Trans`, `TransVar` | ~4 |
| `src/kida/parser/blocks/i18n.py` | **New file**: `I18nParsingMixin` with `_parse_trans` | ~150 |
| `src/kida/parser/statements.py` | Add `"trans": "_parse_trans"` to `_BLOCK_PARSERS`, `"endtrans"` to `_END_KEYWORDS` | ~2 |
| `src/kida/compiler/statements/i18n.py` | **New file**: `I18nStatementMixin` with `_compile_trans` | ~80 |
| `src/kida/compiler/core.py` | Add `"Trans": "_compile_trans"` to `_NODE_DISPATCH_NAMES` | ~1 |
| `src/kida/environment/core.py` | Add `install_translations()`, `install_gettext_callables()`, identity defaults | ~30 |
| `src/kida/template.py` | Inject `_gettext`, `_ngettext`, `_Markup` into execution namespace | ~5 |
| `src/kida/analysis/i18n.py` | **New file**: `ExtractMessagesVisitor`, `ExtractedMessage` | ~80 |
| `src/kida/analysis/dependencies.py` | Add `visit_Trans`, `visit_TransVar` | ~10 |
| `src/kida/babel.py` | **New file**: Babel extractor plugin | ~30 |
| `src/kida/cli/` | Add `extract` command | ~50 |
| `tests/test_i18n.py` | **New file**: 16+ test cases | ~300 |

---

## Testing Plan

### New test file: `tests/test_i18n.py`

```python
class TestTransBasic:
    """{% trans %} block rendering with mock gettext."""

    def test_simple_trans(self):
        """{% trans %}Hello{% endtrans %} calls gettext and renders result."""
        # Mock gettext returns "Bonjour"
        # Expected output: "Bonjour"

    def test_trans_with_variables(self):
        """{% trans name=user.name %}Hello, {{ name }}!{% endtrans %}"""
        # Mock gettext receives "Hello, %(name)s!"
        # Variable value is interpolated into translated string
        # Expected: "Bonjour, Alice!"

    def test_trans_pluralization(self):
        """{% trans count=items|length %}One item.{% plural %}{{ count }} items.{% endtrans %}"""
        # count=1 → ngettext returns singular
        # count=5 → ngettext returns plural with interpolated count
        # Expected: "5 items." (or translated equivalent)

    def test_shorthand_gettext(self):
        """{{ _("Hello") }} calls gettext global."""
        # Mock gettext returns "Bonjour"
        # Expected output: "Bonjour"

    def test_shorthand_ngettext(self):
        """{{ _n("%(count)s item", "%(count)s items", count) }}"""
        # Mock ngettext returns plural form
        # Expected: "5 items" (caller must format)


class TestTransEscaping:
    """HTML escaping interaction with translated strings."""

    def test_variable_values_escaped(self):
        """Variable values are HTML-escaped in translated string."""
        # {% trans name=user_input %}Hello, {{ name }}!{% endtrans %}
        # user_input = "<script>alert(1)</script>"
        # Expected: translated string with &lt;script&gt; in name position

    def test_markup_passthrough(self):
        """Markup variable values are not double-escaped."""
        # {% trans name=safe_html %}Hello, {{ name }}!{% endtrans %}
        # safe_html = Markup("<b>bold</b>")
        # Expected: translated string with <b>bold</b> in name position

    def test_no_variables_escaped(self):
        """Simple trans without variables escapes the translated string."""
        # {% trans %}Hello & goodbye{% endtrans %}
        # gettext returns "Hello & goodbye" (raw)
        # Expected: "Hello &amp; goodbye" (escaped)


class TestTransNoTranslations:
    """Behavior when no translations are installed."""

    def test_identity_gettext(self):
        """Without translations, _("Hello") returns "Hello"."""

    def test_identity_ngettext_singular(self):
        """Without translations, _n("item", "items", 1) returns "item"."""

    def test_identity_ngettext_plural(self):
        """Without translations, _n("item", "items", 5) returns "items"."""


class TestTransExtraction:
    """Message extraction from template ASTs."""

    def test_extract_simple_message(self):
        """Extract message ID from {% trans %}Hello{% endtrans %}."""
        # ExtractMessagesVisitor returns [("gettext", "Hello")]

    def test_extract_line_numbers(self):
        """Extracted messages include correct line numbers."""

    def test_extract_plural_forms(self):
        """Extract singular and plural from {% trans %}...{% plural %}...{% endtrans %}."""
        # Returns [("ngettext", ("One item.", "%(count)s items."))]

    def test_extract_shorthand_calls(self):
        """Extract messages from {{ _("literal") }} calls."""


class TestTransErrors:
    """Parse-time error handling."""

    def test_nested_trans_raises_syntax_error(self):
        """{% trans %} inside {% trans %} raises TemplateSyntaxError."""

    def test_undeclared_variable_raises_syntax_error(self):
        """{{ unknown }} inside {% trans %} without declaration raises error."""

    def test_complex_expression_raises_syntax_error(self):
        """{{ user.name }} inside trans body raises error (must use binding)."""
        # Must use: {% trans name=user.name %}{{ name }}{% endtrans %}

    def test_plural_without_count_raises_syntax_error(self):
        """{% plural %} without count variable in {% trans %} raises error."""


class TestTransIntegration:
    """Integration tests for trans in various template contexts."""

    def test_trans_inside_for_loop(self):
        """{% trans %} inside {% for %} translates on each iteration."""
        # {% for item in items %}
        #   {% trans name=item.name %}Hello, {{ name }}!{% endtrans %}
        # {% endfor %}

    def test_trans_with_whitespace_trimming(self):
        """{%- trans -%} trims surrounding whitespace correctly."""
        # {%- trans -%}
        #   Hello, world!
        # {%- endtrans -%}
        # Message ID: "Hello, world!" (normalized)
```

### Regression tests

All existing tests must pass unchanged. The identity-function default
ensures that templates without `{% trans %}` blocks are not affected.

### AST verification tests

```python
def test_trans_node_fields(env):
    """Trans node has correct singular, plural, variables, count_expr."""
    # Parse: {% trans count=n %}One item.{% plural %}{{ count }} items.{% endtrans %}
    # Assert: node.singular == "One item."
    # Assert: node.plural == "%(count)s items."
    # Assert: len(node.variables) == 1
    # Assert: node.variables[0].name == "count"
    # Assert: node.count_expr is not None
```

---

## Alternatives Considered

### A. Extension-only (no core syntax)

Implement i18n as a Kida Extension (using the existing `extensions`
list on `Environment`) rather than core syntax.

**Rejected**: Extensions cannot add new node types to `_NODE_DISPATCH_NAMES`
without monkey-patching. The extraction CLI needs first-class AST
access. Core support ensures consistent escaping semantics. Jinja2's
i18n extension is widely criticized for being bolted-on rather than
integrated.

### B. Filter-based approach (`{{ "Hello" | trans }}`)

Use a filter instead of a block tag.

**Rejected**: Filters cannot handle pluralization, variable bindings,
or multi-line translatable regions. Message extraction from filter
arguments is fragile (requires expression-level AST walking rather
than dedicated node types). The block syntax `{% trans %}...{% endtrans %}`
is the established pattern (Jinja2, Django, Twig).

### C. ICU MessageFormat instead of gettext

Use ICU MessageFormat (`{count, plural, one {# item} other {# items}}`)
instead of gettext's `ngettext`.

**Rejected for v1**: ICU is more powerful but adds a heavy dependency
(PyICU or manual parser). Gettext is the Python ecosystem standard,
supported by Babel, standard library, and every existing translation
workflow. ICU MessageFormat support can be added as a future extension
on top of the pluggable backend.

### D. Compile-time only (no runtime gettext)

Pre-translate all strings at compile time and produce language-specific
compiled templates.

**Rejected as sole approach**: This works for static sites but not for
applications that switch languages per request. The compile-time
optimization path is included in this RFC as an opt-in
(`optimize_translations`) for the static-site use case.

---

## Future Considerations

### Translation context (msgctxt)

Some strings are ambiguous without context — "Post" could mean a blog
post or the HTTP method. A future enhancement could add context support:

```kida
{% trans context="blog" %}Post{% endtrans %}
```

This would generate `pgettext("blog", "Post")` calls. The `Trans` node
could be extended with an optional `context: str | None` field.

### Translator comments

Allow template authors to add comments for translators:

```kida
{# trans: This greeting appears on the homepage #}
{% trans %}Welcome back!{% endtrans %}
```

The extraction visitor would capture the comment from the preceding
comment token and include it in the `.pot` output.

### ICU MessageFormat backend

For projects that need gender-aware, locale-specific pluralization
rules beyond gettext's simple singular/plural split:

```python
env.install_icu_backend(locale="fr_FR")
```

This would replace the gettext backend with ICU MessageFormat parsing,
using the same `{% trans %}` syntax but with richer interpolation
capabilities.

### Language-per-request middleware

A future middleware or context processor that sets `env._gettext` and
`env._ngettext` per HTTP request based on `Accept-Language` headers
or user preferences. This requires thread-safe translation function
swapping — potentially via `contextvars` (Kida already uses
`contextvars` for render context in `kida/render_context.py`).
