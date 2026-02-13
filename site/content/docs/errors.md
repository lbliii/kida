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

Every Kida exception carries an `ErrorCode` that categorizes the error and links to this page. Use `exc.code.value` to get the code string (e.g. `"K-RUN-001"`). For full error handling guidance, see [[docs/usage/error-handling|Error Handling]].

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

### k-par-002

**Unclosed block** — A block tag (e.g. `{% if %}`, `{% for %}`) was not closed with `{% end %}`.

Fix: Add `{% end %}` for every opening block tag.

### k-par-003

**Invalid expression** — An expression could not be parsed.

Fix: Check the expression syntax. Ensure proper operator usage, balanced parentheses, and valid filter/test syntax.

### k-par-004

**Invalid filter** — A filter name or filter arguments are invalid.

Fix: Use a valid built-in or registered filter name. Check filter argument types.

### k-par-005

**Invalid test** — A test name or test arguments are invalid.

Fix: Use a valid built-in or registered test name. Check test argument types.

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

## Template Loading Errors (K-TPL-xxx)

Template loading errors occur when resolving or loading template files.

### k-tpl-001

**Template not found** — The loader could not find the requested template.

Fix: Check the template name and path. Verify the loader configuration (e.g. `FileSystemLoader` paths).

### k-tpl-002

**Syntax error in template** — The template file contains invalid syntax.

Fix: Fix the syntax error at the reported line. See parser and lexer errors above for related codes.

## See Also

- [[docs/usage/error-handling|Error Handling]] — Exception types, format_compact(), SourceSnippet
- [[docs/troubleshooting/undefined-variable|Undefined Variable]] — Debugging K-RUN-001
- [[docs/troubleshooting/template-not-found|Template Not Found]] — Debugging K-TPL-001
