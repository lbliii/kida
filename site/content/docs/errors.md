---
title: Error Codes
description: Reference for all Kida error codes with descriptions and fixes
draft: false
weight: 50
lang: en
type: doc
tags:
- reference
- errors
- troubleshooting
keywords:
- error codes
- K-LEX
- K-PAR
- K-RUN
- K-TPL
icon: alert-triangle
---

# Error Codes

Kida exceptions and static-analysis findings use the public `ErrorCode` registry
to categorize diagnostics and link to this page. Exception codes are enum
members (`exc.code.value`); analysis records expose the corresponding stable
string through `finding.code`. For full error handling guidance, see
[[docs/usage/error-handling|Error Handling]].

## Lexer Errors (K-LEX-xxx)

Lexer errors occur during tokenization of template source.

### k-lex-001

**Unclosed tag** — A `{%` or `{{` or `{#` was not closed.

Fix: Ensure every `{%` has a matching `%}`, every `{{` has `}}`, and every `{#` has `#}`.

### k-lex-002

**Unclosed comment** — A comment block `{# ... #}` was not closed.

Fix: Add the closing `#}` to the comment.

### k-lex-003

**Unclosed variable** — An output block `{{ ... }}` was not closed.

Fix: Add the closing `}}` to the expression.

### k-lex-004

**Token limit exceeded** — The template exceeded the maximum token count.

Fix: Split the template into smaller includes or simplify the template.

## Parser Errors (K-PAR-xxx)

Parser errors occur when building the template AST from tokens.

### k-par-001

**Unexpected token** — The parser encountered a token it did not expect at this position.

Fix: Check syntax around the reported line. Common causes: misplaced `{% end %}`, invalid tag name, or malformed expression.

#### Coming from Jinja2?

When you type a Jinja2-ism that Kida does not accept, the parser error suggestion points at the Kida equivalent. Common traps:

Matching explicit closers such as `{% endif %}`, `{% endfor %}`, and
`{% endblock %}` are accepted and do not trigger these migration errors.

| Jinja2 | Kida | Hint surfaced by parser |
|--------|------|------------------------|
| `{% macro name(...) %}` | `{% def name(...) %}` | "Kida uses `{% def %}` for macros" |
| `{% endmacro %}` | `{% end %}` | "Kida uses unified `{% end %}` for all blocks" |
| `{% namespace ns %}` / `namespace(count=0)` | `{% let %}` + `{% export %}` | "Kida has no `namespace()` — use `{% let %}` / `{% export %}`" |
| `{% fill name %}` | `{% slot name %}` inside `{% call %}` | "Kida has no `{% fill %}` tag" |
| `{% set x %}...{% endset %}` | `{% capture x %}...{% end %}` | "Kida uses unified `{% end %}` for block-capture" |

See [Migrating from Jinja2]({{< ref "docs/tutorials/migrate-from-jinja2" >}}) for the complete translation table.

### k-par-002

**Unclosed block** — A block tag (e.g. `{% if %}`, `{% for %}`) was not closed.

Fix: Add canonical `{% end %}` or the matching explicit closer, such as
`{% endif %}` or `{% endfor %}`, for every opening block tag.

### k-par-003

**Invalid expression** — An expression could not be parsed.

Fix: Check the expression syntax. Ensure proper operator usage, balanced parentheses, and valid filter/test syntax.

### k-par-004

**Invalid filter** — A filter name or filter arguments are invalid.

Fix: Use a valid built-in or registered filter name. Check filter argument types.

### k-par-005

**Invalid test** — A test name or test arguments are invalid.

Fix: Use a valid built-in or registered test name. Check test argument types.

### k-par-006

**Invalid identifier** — A block name, fragment name, or other identifier contains a hyphen.

Fix: Use underscores instead of hyphens. For example, `{% block settings-status %}` should be `{% block settings_status %}`.

### k-par-007

**Unsupported syntax** — A syntax construct was recognized but is not supported.

Fix: Check the error message for the specific construct. Common case: `{% set x %}...{% endset %}` block capture is not supported — use `{% let x = ... %}` or `{% capture x %}...{% end %}` instead.

## Runtime Errors (K-RUN-xxx)

Runtime errors occur during template rendering.

### k-run-001

**Undefined variable** — A variable or attribute was accessed that does not exist.

Fix: Pass the variable in the render context, use `| default(fallback)`, or check with `{% if var is defined %}`.

### k-run-002

**Filter execution error** — A filter raised an exception during execution.

Fix: Check the filter's input type and arguments. Use `| default()` for optional values.

### k-run-003

**Test execution error** — A test raised an exception during execution.

Fix: Check the test's input type and arguments.

### k-run-004

**Required value was None** — A required value (e.g. from `| require`) was None or missing.

Fix: Ensure the value is present in context or pass a valid default.

### k-run-005

**None comparison (sorting)** — `sort` or `sortattr` encountered None in a comparison.

Fix: Enable `strict_none=True` to raise, or filter out None values before sorting.

### k-run-006

**Include depth exceeded** — Too many nested `{% include %}` calls.

Fix: Reduce include nesting. Check for circular includes.

### k-run-007

**Generic runtime error** — A Python exception occurred during rendering.

Fix: Check the traceback for the underlying cause. Ensure context values have expected types.

### k-run-008

**Macro not found** — A `{% call %}` or `{{ macro_name() }}` referenced a macro/def that does not exist.

Fix: Ensure the macro is defined with `{% def %}` or imported before use. Check for typos in the name.

### k-run-009

**Key error** — A dictionary key lookup failed during rendering.

Fix: Use `dict.get(key, default)` or the `| default()` filter to handle missing keys.

### k-run-010

**Attribute error** — An attribute access failed during rendering.

Fix: Ensure the object has the expected attribute. Use optional chaining (`?.`) or `| default()` for optional attributes.

### k-run-011

**Division by zero** — A division or modulo operation encountered a zero divisor.

Fix: Guard with `{% if divisor != 0 %}` or use a default value.

### k-run-012

**Type error** — An operation received a value of the wrong type.

Fix: Check that the value has the expected type. Use filters like `| int`, `| string` to convert, or `| default()` for missing values.

### k-run-013

**Macro iteration** — A macro was used in a `{% for %}` loop (e.g. `{% for x in route_tabs %}`). This usually means a macro and a context variable share the same name; when the variable is missing, the name resolves to the imported macro.

Fix: Rename the macro to avoid collision. Use verb-prefixed names for macros (e.g. `render_route_tabs`) and noun-like names for context variables (`route_tabs`). See [[docs/syntax/functions#macro-vs-context-variable-naming|Macro vs Context Variable Naming]].

### k-run-014

**Environment garbage collected** — The `Environment` object was garbage collected while templates still reference it.

Fix: Keep a reference to the `Environment` for the lifetime of your application. Store it in a module-level variable or application state.

### k-run-015

**Template not compiled** — A template method was called before the template was compiled.

Fix: Use `env.get_template()` or `env.from_string()` to create templates. Do not construct `Template` objects directly.

### k-run-016

**No loader configured** — `get_template()` was called on an `Environment` with no loader.

Fix: Pass a loader when creating the environment: `Environment(loader=FileSystemLoader("templates/"))`.

### k-run-017

**Not in render context** — A function that requires an active render context was called outside of template rendering.

Fix: Only call `get_render_context()` or context-dependent functions during `template.render()`.

## Template Loading Errors (K-TPL-xxx)

Template loading errors occur when resolving or loading template files.

### k-tpl-001

**Template not found** — The loader could not find the requested template.

Fix: Check the template name and path. Verify the loader configuration (e.g. `FileSystemLoader` paths).

### k-tpl-002

**Syntax error in template** — The template file contains invalid syntax.

Fix: Fix the syntax error at the reported line. See parser and lexer errors above for related codes.

### k-tpl-003

**Circular import** — Two or more templates extend or include each other in a cycle.

Fix: Restructure template inheritance to eliminate the cycle. Use a shared base template or `{% include %}` instead of circular `{% extends %}`.

### k-tpl-004

**Definition not top-level** — A `{% def %}` or `{% region %}` was declared
inside another block, loop, conditional, component, or region.

Fix: Move `{% def %}` and `{% region %}` declarations to the template top
level. Top-level declarations are visible to render, block render, component
metadata, and static validation. Nested defs are not render-block targets and
cannot be validated reliably.

## Security Errors (K-SEC-xxx)

Security errors occur in sandboxed environments when a template tries to access restricted resources.

### k-sec-001

**Blocked attribute** — Access to an attribute was denied by the sandbox policy.

Fix: Check the `SandboxPolicy.allowed_attributes` configuration. Add the attribute if it should be accessible, or access the data through a different path.

### k-sec-002

**Blocked type** — An object type is not allowed in the sandbox.

Fix: Check the `SandboxPolicy.blocked_types` configuration. Remove the type from the blocked list if it should be allowed, or pass only supported types in the render context.

### k-sec-003

**Range limit exceeded** — A `range()` call exceeded the sandbox's maximum allowed range size.

Fix: Reduce the range size or increase `SandboxPolicy.max_range`.

### k-sec-004

**Blocked callable** — A function or method call was denied by the sandbox policy.

Fix: Check the `SandboxPolicy.allow_calling` configuration. If calling is required, enable it only for trusted templates, or use a filter instead of calling methods directly.

### k-sec-005

**Output limit exceeded** — Rendered output exceeded `SandboxPolicy.max_output_size`.

Fix: Reduce template output size or increase `SandboxPolicy.max_output_size`. Consider paginating large datasets.

## Component Validation (K-CMP-xxx)

Component validation diagnostics are emitted by `Environment(validate_calls=True)`
and `kida check --validate-calls`. They are compile-time diagnostics for
`{% def %}` call sites, including calls to literal `{% from "..." import ... %}`
component imports. Dynamic imports are skipped because Kida cannot know the
target template at check time.

### k-cmp-001

**Component call signature mismatch** — A component call used unknown keyword
arguments, omitted required parameters, or supplied duplicate keyword
arguments.

Fix: Compare the call site with the component's `{% def %}` signature. Rename
misspelled props, add missing required props, or remove props the component does
not accept.

Example:

```kida
{% def card(title: str) %}{{ title }}{% end %}
{{ card(titl="Settings") }}
```

Use `title=` instead of `titl=`.

### k-cmp-002

**Component literal type mismatch** — A literal argument does not match the
component parameter annotation. Kida validates literal `str`, `int`, `float`,
`bool`, `None`, and simple `|` unions. Variable arguments and custom types are
documentary and skipped.

Fix: Pass a literal with the annotated type, update the annotation if the
component accepts both shapes, or move validation into Python when the value is
dynamic.

Example:

```kida
{% def badge(count: int) %}{{ count }}{% end %}
{{ badge("five") }}
```

Pass `5` or change the parameter type if string counts are intentional.

## Privacy Findings (K-PRI-xxx)

Static privacy lint findings are conservative review signals; they never echo
secret-like literal values.

### k-pri-001

**Sensitive context path** — A template reads a context path whose name looks
sensitive. Fix: Confirm the value is intended for rendered output.

### k-pri-002

**Secret-like literal** — Template source contains a literal that resembles a
secret. Fix: Move secrets out of templates and redact fixtures.

### k-pri-003

**Sensitive value marked safe** — A sensitive-looking value bypasses escaping.
Fix: Remove `| safe` or document and enforce the sanitizer/trust boundary.

### k-pri-004

**Broad context output** — A template appears to render a broad request,
session, debug, or context object. Fix: Render only the required fields.

### k-pri-005

**Dynamic template name** — A dynamic include/import target cannot be checked
against a static privacy allowlist. Fix: Prefer literal template names when the
policy requires static proof.

## Context Contract Findings (K-CTX-xxx)

### k-ctx-001

**Missing context path** — A template dependency is absent from the provided
route/framework contract. Fix: Provide the path or explicitly mark it optional.

### k-ctx-002

**Unused context path** — Strict extra-data checking found a provided path the
template does not read. Fix: Remove it or disable extra-data checking for broad
framework contexts.

## Escape Audit Findings (K-ESC-xxx)

### k-esc-001

**Escaped output** — An output expression is protected by the active render
surface. This is an informational static observation.

### k-esc-002

**Trusted markup boundary** — `| safe` or an equivalent node bypasses escaping.
Fix: Document why the value is trusted and sanitized.

### k-esc-003

**Unescaped output** — Autoescape is disabled for an output or template block.
Fix: Enable escaping or make the trust boundary explicit.

### k-esc-004

**Trusted JSON markup** — `tojson` intentionally returns trusted JSON markup.
Use `tojson(attr=true)` inside HTML attributes.

### k-esc-005

**Trusted attribute markup** — `xmlattr` intentionally returns trusted HTML
attribute markup. Ensure its input keys and values are appropriate for output.

## Accessibility Findings (K-A11Y-xxx)

### k-a11y-001

**Image missing alternative text** — A non-decorative `<img>` has no `alt`
attribute. Fix: Add meaningful `alt` text or an explicit decorative role.

### k-a11y-002

**Heading order skipped** — Heading levels jump by more than one. Fix: Use a
sequential document outline.

### k-a11y-003

**Document language missing** — `<html>` has no `lang` attribute. Fix: Declare
the document language.

### k-a11y-004

**Form control missing label** — A form control has no associated `<label>`,
`aria-label`, or `aria-labelledby`. Fix: Add an accessible name.

## Template Declaration Type Findings (K-TYP-xxx)

### k-typ-001

**Undeclared variable** — A template uses a variable absent from its
`{% template %}` declaration. Fix: Declare it or correct the reference.

### k-typ-002

**Unused declaration** — A declared template variable is never read. Fix:
Remove the declaration or use the intended value.

### k-typ-003

**Likely variable typo** — An undeclared variable closely resembles a declared
name. Fix: Review and apply the suggestion only when semantically correct.

## Template Path Findings (K-PATH-xxx)

### k-path-001

**Fragile same-folder template path** — A same-folder include, extends, embed,
or import uses a root-relative path. Fix: Use the suggested `./` path so moving
the folder does not require editing its internal references.

## Modularity Findings (K-MOD-xxx)

### k-mod-102

**Extraction candidate** — Several independent signals suggest that a source
region may support a typed local component boundary. Review the exact span,
contributing signals, tentative props and slots, dependencies, and related
locations before changing source. This opt-in informational diagnostic is
conservative and never supplies an automatic edit.

## Warnings (K-WARN-xxx)

Compile-time warnings that indicate potential issues but do not prevent rendering.

### k-warn-001

**Filter precedence** — The filter pipe `|` binds tighter than the null coalescing operator `??`. This means `x ?? [] | length` is parsed as `x ?? ([] | length)`, which applies the filter only to the fallback, not the full expression.

Fix: Add parentheses to clarify intent: `(x ?? []) | length`.

### k-warn-002

**Jinja2 `set` scoping difference** — An `{% if %}` branch contains `{% set x = ... %}` whose Jinja binding is read after the block, or it targets a name already bound template-wide via `{% let x %}` or `{% export x %}`. In Kida this creates a branch-scoped value that does not leak to outer scope; in Jinja2 an `if` does not create a scope.

Fix: For a fresh name that must remain visible, use `{% let x = ... %}`. To update an existing template-wide binding, use `{% export x = ... %}`. The diagnostic is advisory and never supplies an automatic edit.

Enabled by default. Suppress with `warnings.filterwarnings("ignore", category=MigrationWarning)` or `Environment(jinja2_compat_warnings=False)`. The read-after-block analysis follows nested `if` branches, stops at unambiguous rebinding, and does not claim that assignments inside Jinja-local `for` scopes escape. Ambiguous binding origins remain unreported.

The warning is also available through `kida check`, `diagnose_source()`, and
`diagnose_directory()` with its template path, line, suggestion, and proven
confidence. It is advisory and has no automatic edit.

## See Also

- [[docs/usage/error-handling|Error Handling]] — Exception types, format_compact(), SourceSnippet
- [[/docs/troubleshooting/undefined-variable/|Undefined Variable]] — Debugging K-RUN-001
- [[/docs/troubleshooting/template-not-found/|Template Not Found]] — Debugging K-TPL-001
