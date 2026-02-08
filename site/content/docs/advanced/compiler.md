---
title: Compiler Internals
description: F-string coalescing, AST preservation, and compilation optimization
draft: false
weight: 30
lang: en
type: doc
tags:
- advanced
- compiler
- performance
keywords:
- compiler
- f-string coalescing
- optimization
- AST
- pure filters
icon: cpu
---

# Compiler Internals

Kida compiles templates into Python functions at load time. This article covers the optimization passes and configuration options available to framework authors and performance-conscious users.

## F-String Coalescing

The compiler's primary optimization is **f-string coalescing** — merging consecutive output nodes into single f-string appends instead of multiple `buf.append()` calls.

### Before (5 function calls)

```python
_append('<div id="')
_append(_e(item["id"]))
_append('">')
_append(_e(item["name"]))
_append('</div>')
```

### After (1 function call)

```python
_append(f'<div id="{_e(item["id"])}">{_e(item["name"])}</div>')
```

This reduces function call overhead by ~37% in output-heavy templates.

### How It Works

The compiler scans template bodies for consecutive **coalesceable** nodes:

| Node Type | Coalesceable? | Notes |
|-----------|--------------|-------|
| Static text (`Data`) | Yes | Literal HTML |
| Simple variable output | Yes | `{{ name }}`, `{{ item.title }}` |
| Pure filter output | Yes | `{{ name \| upper }}`, `{{ text \| trim }}` |
| Item access | Yes | `{{ items[0] }}`, `{{ data["key"] }}` |
| Function calls | No | May have side effects |
| Ternary expressions | No | Complex control flow |
| Control flow (`{% if %}`, `{% for %}`) | No | Breaks the coalescing run |

When 2 or more consecutive coalesceable nodes are found, they are merged into a single `ast.JoinedStr` (Python f-string AST node). Brace escaping is handled automatically by the AST compiler.

### Configuration

F-string coalescing is enabled by default:

```python
env = Environment(
    fstring_coalescing=True,   # Default — recommended
)
```

Disable it when debugging compiled template output:

```python
env = Environment(
    fstring_coalescing=False,  # Each output is a separate append
)
```

### Pure Filters

The compiler only coalesces filter expressions that are known to be **pure** (no side effects, deterministic). Kida includes a built-in set of pure filters:

```
upper, lower, title, capitalize, swapcase, trim, strip, lstrip, rstrip,
escape, e, forceescape, default, d, int, float, string, str, bool,
length, count, first, last, join, center, ljust, rjust, truncate,
wordwrap, indent, urlencode
```

Register your own pure filters so the compiler can coalesce them:

```python
env = Environment(
    pure_filters={"markdown", "highlight", "currency"},
)
```

These are combined with the built-in set at compilation time.

### Backslash Limitation

Python f-strings cannot contain backslashes in expression parts. The compiler detects backslashes in string constants and falls back to separate appends for those expressions.

## AST Preservation

Kida can preserve the optimized AST after compilation, enabling runtime introspection via the [[docs/advanced/analysis|static analysis]] API.

```python
env = Environment(
    preserve_ast=True,   # Default — enables analysis API
)
```

### Memory Trade-Off

Preserving the AST uses ~2x memory per template. Disable it in memory-constrained environments where you don't need introspection:

```python
env = Environment(
    preserve_ast=False,  # Saves memory, disables analysis
)
```

With `preserve_ast=False`, the following methods return empty/None results:
- `template.block_metadata()` returns `{}`
- `template.template_metadata()` returns `None`
- `template.depends_on()` returns `frozenset()`
- `template.required_context()` returns `frozenset()`
- `template.is_cacheable()` returns `False`
- `template.validate_context()` returns `[]`

## Render Modes

The compiler generates code for three render modes in a single compilation pass:

| Mode | Method | Output |
|------|--------|--------|
| **StringBuilder** | `render()` | Full string in memory (fastest) |
| **Streaming** | `render_stream()` | Generator yielding chunks |
| **Async streaming** | `render_stream_async()` | Async generator yielding chunks |

The compiler emits `_append(...)` calls for StringBuilder mode and `yield ...` statements for streaming mode. Both share the same expression compilation logic.

### Line Tracking

The compiler emits line-number updates using `ContextVar`-based `RenderContext`. This enables accurate error messages without polluting the user's context dictionary:

```python
# Compiler emits this before each statement:
_ctx.line = 42  # Current template line
```

On error, the line number is read from `RenderContext` to produce messages like:

```
TemplateRuntimeError: 'page' is undefined
  File "page.html", line 42, in template
```

## See Also

- [[docs/advanced/analysis|Static Analysis]] — Using analysis results from preserved ASTs
- [[docs/reference/configuration|Configuration]] — `fstring_coalescing`, `pure_filters`, `preserve_ast`
- [[docs/about/performance|Performance]] — Benchmark results
