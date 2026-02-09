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
| `TemplateNotFoundError` | Template file not found |
| `UndefinedError` | Accessing undefined variable (strict mode) |

All exception classes are importable from the top-level `kida` package:

```python
from kida import (
    TemplateError,
    TemplateSyntaxError,
    TemplateRuntimeError,
    TemplateNotFoundError,
    UndefinedError,
)
```

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

## Error Codes

Every Kida exception carries an `ErrorCode` that categorizes the error and links to documentation:

| Code | Category | Description |
|------|----------|-------------|
| `K-LEX-001` | Lexer | Unterminated string literal |
| `K-LEX-002` | Lexer | Invalid character in template |
| `K-PAR-001` | Parser | Unexpected token |
| `K-PAR-002` | Parser | Unclosed block tag |
| `K-PAR-003` | Parser | Invalid expression |
| `K-RUN-001` | Runtime | Undefined variable |
| `K-RUN-002` | Runtime | Type error in expression |
| `K-RUN-003` | Runtime | Index out of range |
| `K-RUN-004` | Runtime | Filter execution error |
| `K-TPL-001` | Template | Template not found |
| `K-TPL-002` | Template | Circular template inheritance |
| `K-TPL-003` | Template | Invalid block override |

Access the code programmatically:

```python
from kida import UndefinedError, ErrorCode

try:
    template.render()
except UndefinedError as e:
    print(e.code)        # ErrorCode.K_RUN_001
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

This is the recommended format for frameworks that wrap Kida errors (like Chirp and Bengal).

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
        print(snippet.filename)    # Template filename
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
UndefinedError: 'dict' object has no attribute 'nmae'
```

Fix: Check attribute spelling, verify object type.

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

- [[docs/troubleshooting/undefined-variable|Undefined Variable]] — Debug undefined errors
- [[docs/troubleshooting/template-not-found|Template Not Found]] — Fix loading issues
- [[docs/reference/api|API Reference]] — Exception classes
