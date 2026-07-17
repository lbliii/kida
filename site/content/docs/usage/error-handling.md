---
title: Error Handling
description: Template errors, debugging, and stack traces
draft: false
weight: 40
lang: en
type: doc
tags:
- usage
- debugging
keywords:
- errors
- debugging
- exceptions
- stack traces
icon: alert-triangle
---

# Error Handling

Kida provides clear error messages with source locations, error codes, and actionable hints.

## Exception Types

| Exception | When Raised |
|-----------|-------------|
| `TemplateError` | Base class for all template errors |
| `TemplateSyntaxError` | Invalid template syntax |
| `TemplateRuntimeError` | Error during template rendering |
| `TemplateNotFoundError` | Template file not found (includes caller context) |
| `UndefinedError` | Accessing undefined variable or attribute |
| `SecurityError` | Sandbox policy violation |

All exception classes are importable from the top-level `kida` package:

```python
from kida import (
    TemplateError,
    TemplateSyntaxError,
    TemplateRuntimeError,
    TemplateNotFoundError,
    UndefinedError,
    SecurityError,
)
```

For editor, CI, or framework integration, use the public programmatic
diagnostics API instead of parsing exception strings:

```python
from kida.diagnostics import diagnostic_from_exception

try:
    template.render()
except TemplateError as error:
    finding = diagnostic_from_exception(error)
    print(finding.code, finding.span, finding.suggestion)
```

See [Programmatic Diagnostics](/docs/reference/api/#programmatic-diagnostics)
for in-memory source and directory-wide collection.

## Syntax Errors

```python
from kida import Environment, TemplateSyntaxError

env = Environment()
try:
    template = env.from_string("{% if x %}")  # Missing end
except TemplateSyntaxError as e:
    print(e)
    # TemplateSyntaxError: Unexpected end of template (expected {% end %})
    # File "<string>", line 1
```

Error messages include:

- Error description
- File name (or `<string>` for from_string)
- Line number
- Relevant source snippet

## Undefined Variables

By default, undefined variables raise `UndefinedError`:

```python
from kida import UndefinedError

template = env.from_string("{{ missing }}")
try:
    html = template.render()
except UndefinedError as e:
    print(e)
    # UndefinedError: Undefined variable 'missing' in <string>:1
```

### Handle Missing Values

Use the `default` filter:

```kida
{{ user.nickname | default("Anonymous") }}
{{ config.timeout | default(30) }}
```

Or check with `is defined`:

```kida
{% if user is defined %}
    {{ user.name }}
{% end %}
```

## Template Not Found

```python
from kida import TemplateNotFoundError

try:
    template = env.get_template("nonexistent.html")
except TemplateNotFoundError as e:
    print(e)
    # TemplateNotFoundError: Template 'nonexistent.html' not found in: templates/
```

## Runtime Errors

Python errors during rendering include template context:

```python
template = env.from_string("{{ items[10] }}")
try:
    html = template.render(items=[1, 2, 3])
except IndexError as e:
    # Traceback shows template location
    pass
```

## Debug Filter

Inspect values during development:

```kida
{{ posts | debug }}
{{ posts | debug("my posts") }}
```

Output (to stderr):

```
DEBUG [my posts]: <list[5]>
  [0] Post(title='First Post', weight=10)
  [1] Post(title='Second', weight=None)  <-- None: weight
  ...
```

## Component Call Stack

When an error occurs inside a `{% def %}` component, `TemplateRuntimeError` and `UndefinedError` include a `component_stack` showing the call chain that led to the error:

```python
try:
    template.render(data=data)
except TemplateRuntimeError as e:
    for tpl_name, lineno, def_name in e.component_stack:
        print(f"  in {def_name}() at {tpl_name}:{lineno}")
```

The `format_compact()` output automatically includes the component stack when present.

## Compile-Time Warnings

Kida emits Python warnings during template compilation for common pitfalls:

| Warning | Code | Trigger |
|---------|------|---------|
| `PrecedenceWarning` | K-WARN-001 | `x ?? [] \| length` — filter pipe binds tighter than `??` |
| `CoercionWarning` | — | `"abc" \| float` — silent type coercion to `0.0` |
| `MigrationWarning` | K-WARN-002 | Jinja `if`-local `{% set %}` flow differs from Kida block scope (default-on; disable via `jinja2_compat_warnings=False`) |

Access warnings on a compiled template:

```python
template = env.get_template("page.html")
for w in template.warnings:
    print(f"{w.code}: {w.message} (line {w.lineno})")
```

`kida check`, `diagnose_source()`, and `diagnose_directory()` also include
code-bearing compiler warnings in the shared structured-diagnostics collection.
Text, diagnostics JSON v1, and SARIF preserve the same path, line, suggestion,
and confidence. These advisory findings do not include automatic edits.

These are standard Python warnings — filter them with `warnings.filterwarnings("ignore", category=PrecedenceWarning)`.

## Error Codes

Kida exceptions and registered static-analysis findings use `ErrorCode` values
that categorize the diagnostic and link to documentation:

| Code | Category | Description |
|------|----------|-------------|
| `K-LEX-001` | Lexer | Unclosed tag |
| `K-LEX-002` | Lexer | Unclosed comment |
| `K-LEX-003` | Lexer | Unclosed variable |
| `K-LEX-004` | Lexer | Token limit exceeded |
| `K-PAR-001` | Parser | Unexpected token |
| `K-PAR-002` | Parser | Unclosed block tag |
| `K-PAR-003` | Parser | Invalid expression |
| `K-PAR-004` | Parser | Invalid filter |
| `K-PAR-005` | Parser | Invalid test |
| `K-PAR-006` | Parser | Invalid identifier (hyphen in block/fragment name) |
| `K-PAR-007` | Parser | Unsupported syntax |
| `K-RUN-001` | Runtime | Undefined variable |
| `K-RUN-002` | Runtime | Filter execution error |
| `K-RUN-003` | Runtime | Test execution error |
| `K-RUN-004` | Runtime | Required value was None or missing |
| `K-RUN-005` | Runtime | None comparison |
| `K-RUN-006` | Runtime | Include depth exceeded |
| `K-RUN-007` | Runtime | Generic runtime error |
| `K-RUN-008` | Runtime | Macro not found |
| `K-RUN-009` | Runtime | Key error |
| `K-RUN-010` | Runtime | Attribute error |
| `K-RUN-011` | Runtime | Division by zero |
| `K-RUN-012` | Runtime | Type error |
| `K-RUN-013` | Runtime | Macro iteration |
| `K-RUN-014` | Runtime | Environment garbage collected |
| `K-RUN-015` | Runtime | Template not compiled |
| `K-RUN-016` | Runtime | No loader configured |
| `K-RUN-017` | Runtime | Not in render context |
| `K-TPL-001` | Template | Template not found |
| `K-TPL-002` | Template | Template syntax error |
| `K-TPL-003` | Template | Circular macro import |
| `K-TPL-004` | Template | Definition not top-level |
| `K-TPL-005` | Template | Invalid or ambiguous explicit template-root configuration |
| `K-SEC-001` | Security | Blocked attribute access |
| `K-SEC-002` | Security | Blocked type access |
| `K-SEC-003` | Security | Range limit exceeded |
| `K-SEC-004` | Security | Blocked callable |
| `K-SEC-005` | Security | Output limit exceeded |
| `K-CMP-001` | Component | Component call signature mismatch |
| `K-CMP-002` | Component | Component literal type mismatch |
| `K-WARN-001` | Warning | Filter precedence warning |
| `K-WARN-002` | Warning | Jinja2 `set` scoping difference |
| `K-PRI-001`–`005` | Privacy | Sensitive paths, secret literals, trust boundaries, broad output, dynamic templates |
| `K-CTX-001`–`002` | Context | Missing or unused context-contract paths |
| `K-ESC-001`–`005` | Escape | Escaped output and trusted/unescaped markup boundaries |
| `K-A11Y-001`–`004` | Accessibility | Alternative text, heading order, document language, form labels |
| `K-TYP-001`–`003` | Type | Undeclared, unused, or likely misspelled template variables |
| `K-PATH-001` | Path | Fragile same-folder template reference |

Access the code programmatically:

```python
from kida import UndefinedError, ErrorCode

try:
    template.render()
except UndefinedError as e:
    print(e.code)        # ErrorCode.UNDEFINED_VARIABLE
    print(e.code.value)  # "K-RUN-001"
```

## Compact Error Format

All Kida exceptions provide a `format_compact()` method that produces a structured, human-readable summary for terminal output or logging:

```python
from kida import TemplateError

try:
    template.render()
except TemplateError as e:
    print(e.format_compact())
```

Output:

```
K-RUN-001: Undefined variable 'usernme' in base.html:42

     |
> 42 | <h1>{{ usernme }}</h1>
     |

Hint: Did you mean 'username'?
Docs: https://lbliii.github.io/kida/docs/errors/#k-run-001
```

The compact format includes:

- **Error code** and description
- **Source snippet** with line numbers and error pointer
- **Hint** with suggestions (typo corrections, `default` filter usage)
- **Docs link** to the relevant error code documentation

Use `format_compact()` for terminal output and logs. Framework debug pages should
prefer `UndefinedError.to_diagnostic()` so they can render the same code,
location, source snippet, hints, documentation URL, template stack, and component
stack without parsing terminal text.

```python
from kida import UndefinedError

try:
    template.render()
except UndefinedError as exc:
    diagnostic = exc.to_diagnostic()
    html = diagnostic.format_html_page()
```

The diagnostic payload stores plain strings. HTML, Markdown, and terminal
escaping happen only in the final renderer.

## Source Snippets

For programmatic access to the source context around an error, use the `source_snippet` attribute:

```python
from kida import UndefinedError, SourceSnippet

try:
    template.render()
except UndefinedError as e:
    snippet: SourceSnippet | None = e.source_snippet
    if snippet:
        print(snippet.lines)       # List of (line_number, line_text) tuples
        print(snippet.error_line)  # The line number with the error
        print(e.template)          # Template name
        print(e.lineno)            # Error line
```

You can also build snippets manually with `build_source_snippet()`:

```python
from kida import build_source_snippet

snippet = build_source_snippet(source_text, error_line=42, context_lines=3)
```

## Common Error Patterns

### Missing Variable

```
UndefinedError: Undefined variable 'usre' in page.html:5
```

Fix: Check for typos, ensure variable is passed to render().

### Attribute Error

```
UndefinedError: Undefined attribute/key 'User.nmae' in page.html:5
```

Fix: Check attribute spelling, verify object type.

## Reading Template and Component Stacks

`template_stack` explains how rendering reached another template through
`include`, `extends`, or imported macros. `component_stack` explains which
`{% def %}` components were active. In an HTML error view, show the source
location first, then these stacks as supporting context. Python traceback frames
from generated code are secondary.

For imported components with slots, Kida reports slot-body errors against the
caller template while still keeping the imported component path in the component
stack.

### Type Error in Filter

```
TypeError: object of type 'NoneType' has no len()
```

Fix: Use `default` filter or check for None.

```kida
{{ items | default([]) | length }}
```

### Template Not Found

```
TemplateNotFoundError: Template 'bsae.html' not found
```

Fix: Check file path, verify loader configuration.

### Hyphen in Block or Fragment Name

```
Kida Parse Error [K-PAR-006]: Invalid block name: 'settings-status' contains a hyphen
```

Fix: Use underscores instead of hyphens. Change `{% block settings-status %}` to `{% block settings_status %}`.

## Error Handling in Production

```python
from kida import TemplateError

def render_page(template_name, **context):
    try:
        return env.render(template_name, **context)
    except TemplateError as e:
        # Log the compact format for clean terminal output
        logger.error("Template error:\n%s", e.format_compact())
        # Return fallback
        return env.render("error.html", error=str(e))
```

## Best Practices

### Validate Context

```python
def render_safely(template, **context):
    # Validate required fields
    required = ["title", "user"]
    missing = [k for k in required if k not in context]
    if missing:
        raise ValueError(f"Missing context: {missing}")

    return template.render(**context)
```

### Use Default Values

```kida
{# Defensive defaults #}
{{ user.name | default("Guest") }}
{{ items | default([]) | length }}
{{ config.get("timeout", 30) }}
```

### Check Before Access

```kida
{% if user and user.profile %}
    {{ user.profile.bio }}
{% end %}
```

## See Also

- [Error Boundaries]({{< ref "docs/usage/error-boundaries" >}}) — Catch rendering errors inside templates with `{% try %}`/`{% fallback %}`
- [[/docs/troubleshooting/undefined-variable/|Undefined Variable]] — Debug undefined errors
- [[/docs/troubleshooting/template-not-found/|Template Not Found]] — Fix loading issues
- [[docs/reference/api|API Reference]] — Exception classes
