---
name: kida-template-debugging
description: Debug Kida template errors: UndefinedError, TemplateSyntaxError, TemplateRuntimeError, unexpected output. Use when template rendering fails, variables are undefined, or output is wrong.
---

# Kida Template Debugging

## Quick Diagnosis

| Error | Cause | Fix |
|-------|-------|-----|
| **UndefinedError** | Missing context variable | Use `template.validate_context(ctx)` before render; add variable to context or use `\| default()` |
| **TemplateSyntaxError** | Invalid syntax | Check block endings (`{% end %}`), tag spelling, hyphen in block names |
| **TemplateRuntimeError** | Error during render | Check filter args, None access, index out of range |
| **TemplateNotFoundError** | Template file missing | Verify loader path, check filename spelling |
| **Unexpected output** | Expression semantics | Check `+` operator (list vs string), `{% export %}` accumulation |

## Pre-Render Validation

Catch missing variables before rendering:

```python
missing = template.validate_context(user_context)
if missing:
    raise ValueError(f"Missing template variables: {missing}")
result = template.render(**user_context)
```

## Exception Types

```python
from kida import (
    TemplateError,
    TemplateSyntaxError,
    TemplateRuntimeError,
    TemplateNotFoundError,
    UndefinedError,
)
```

## Common Fixes

### Undefined Variable

- **Typo**: `{{ usre.name }}` → `{{ user.name }}`
- **Not passed**: Add variable to `render()` call
- **Optional**: `{{ user.nickname | default("Anonymous") }}`
- **Nested None**: Use `{% if page.parent %}{{ page.parent.title }}{% end %}` or `| default()`

### Syntax Errors

- **Missing `{% end %}`**: Every `{% if %}`, `{% for %}`, `{% block %}` needs `{% end %}`
- **Hyphen in block name**: Use `settings_status` not `settings-status` (K-PAR-006)

### Runtime Errors

- **Filter on None**: `{{ items | default([]) | length }}`
- **Index out of range**: Check list bounds before access

## Debug Tools

### debug Filter

```kida
{{ user | debug }}
{{ posts | debug("my posts") }}
```

Outputs to stderr with structure. Use during development.

### Source Snippet

```python
from kida import build_source_snippet

try:
    template.render()
except UndefinedError as e:
    if e.source_snippet:
        print(e.source_snippet.lines)
        print(e.source_snippet.error_line)
    print(e.format_compact())  # Recommended: includes hint, docs link
```

### Error Codes

| Code | Category | Description |
|------|----------|-------------|
| K-RUN-001 | Runtime | Undefined variable |
| K-RUN-002 | Runtime | Type error in expression |
| K-RUN-004 | Runtime | Filter execution error |
| K-PAR-002 | Parser | Unclosed block tag |
| K-PAR-006 | Parser | Invalid identifier (hyphen in name) |
| K-TPL-001 | Template | Template not found |

Access: `e.code` → `ErrorCode.K_RUN_001`, `e.code.value` → `"K-RUN-001"`

## List vs String Pitfall

`{% export members = members + [m] %}` must stay list concatenation. If `+` incorrectly stringifies, iteration over the result produces character-by-character output. See kida-expression-semantics skill for details.

## Best Practices

1. **Validate context** before render in CI or build pipelines
2. **Use `| default()`** for optional variables
3. **Check before access**: `{% if user and user.profile %}`
4. **Log with `format_compact()`** for clean error output in production
