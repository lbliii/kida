---
title: Template Type Checking
description: Annotate expected context types with template declarations for compile-time validation
draft: false
weight: 63
lang: en
type: doc
tags:
  - advanced
  - type-checking
  - tooling
keywords:
  - type checker
  - template declaration
  - type annotation
  - validation
icon: check-circle
---

# Template Type Checking

Kida can validate template variables against `{% template %}` declarations at compile time — catching typos, missing variables, and undeclared context access before any template is rendered.

## Template Declarations

Add a `{% template %}` block at the top of a template to declare the expected context variables:

```html
{% template page: Page, site: Site %}

<h1>{{ page.title }}</h1>
<p>Published on {{ site.name }}</p>
```

When a `{% template %}` declaration is present, the type checker validates that every variable used in the template is either declared, locally defined, or a built-in name. Templates without a `{% template %}` declaration are unconstrained — no type checking is performed.

## Supported Types

The type checker validates variable **names**, not Python types. The type annotations in declarations (e.g., `Page`, `Site`) serve as documentation. What the checker enforces is that every context variable accessed in the template appears in the declaration list.

### Built-In Names

The following names are always available and never need to be declared:

| Category | Names |
|----------|-------|
| **Python builtins** | `range`, `len`, `str`, `int`, `float`, `bool`, `list`, `dict`, `set`, `tuple`, `min`, `max`, `sum`, `abs`, `round`, `sorted`, `reversed`, `enumerate`, `zip`, `map`, `filter`, `any`, `all`, `hasattr`, `getattr`, `isinstance`, `type` |
| **Boolean/None literals** | `true`, `false`, `none`, `True`, `False`, `None` |
| **Template globals** | `loop`, `caller`, `super` |
| **HTMX helpers** | `hx_request`, `hx_target`, `hx_trigger`, `hx_boosted` |
| **Security tokens** | `csrf_token`, `csp_nonce` |

### Locally Defined Names

Variables introduced by template constructs do not need declaration. The type checker tracks names created by:

| Construct | Example |
|-----------|---------|
| `{% set %}` | `{% set total = items \| length %}` |
| `{% let %}` | `{% let count = 0 %}` |
| `{% export %}` | `{% export title = "Home" %}` |
| `{% capture %}` | `{% capture sidebar %}...{% endcapture %}` |
| `{% for %}` | `{% for item in items %}` (binds `item`) |
| `{% with %}` | `{% with x = 1, y = 2 %}` |
| `{% def %}` | `{% def button(text, url) %}` (binds `button`, `text`, `url`) |
| `{% import %}` | `{% import "macros.html" as macros %}` |
| `{% from ... import %}` | `{% from "macros.html" import button %}` |

The checker respects scoping: variables bound inside `{% for %}`, `{% with %}`, and `{% def %}` blocks are only visible within those blocks.

## Usage

### Python API

```python
from kida.analysis.type_checker import check_types

# Parse and compile a template with a {% template %} declaration
template = env.get_template("page.html")

# Run the type checker against the AST
issues = check_types(template._optimized_ast)

for issue in issues:
    print(f"Line {issue.lineno}: [{issue.rule}] {issue.message}")
```

The `check_types` function accepts a parsed `Template` AST node and returns a list of `TypeIssue` findings sorted by line number. If the template has no `{% template %}` declaration, it returns an empty list.

### CLI

```bash
kida check --typed templates/
```

For component prop validation, use:

```bash
kida check --validate-calls templates/
```

This checks calls to local `{% def %}` components and literal `{% from "..." import ... %}` components. It reports unknown keyword arguments, missing required props, and literal type mismatches with component error codes such as `K-CMP-001` and `K-CMP-002`.

## Error Messages

The type checker produces three categories of findings:

### undeclared-var

A variable is used in the template but does not appear in the `{% template %}` declaration and is not locally defined or built-in.

```
Line 12: Variable 'author' used but not declared in {% template %}
```

**Fix:** Add the variable to the `{% template %}` declaration:

```html
{% template page: Page, site: Site, author: Author %}
```

### unused-declared

A variable is declared in `{% template %}` but never referenced anywhere in the template.

```
Line 1: Declared variable 'sidebar' is never used
```

**Fix:** Remove the unused variable from the declaration, or add usage in the template body.

### typo-suggestion

A variable is undeclared, and its name is similar to a declared variable (edit distance of 1, or matching prefix). The checker suggests the likely intended name.

```
Line 8: Variable 'titl' used but not declared in {% template %} (did you mean 'title'?)
```

The typo detector uses two heuristics:
- **Prefix matching** — the first 3 characters of the used name match a declared name
- **Edit distance** — the used name differs from a declared name by exactly one character (insertion, deletion, or substitution)

## TypeIssue

Each finding is a `TypeIssue` dataclass:

| Field | Type | Description |
|-------|------|-------------|
| `lineno` | `int` | Line number of the issue |
| `col_offset` | `int` | Column offset of the issue |
| `rule` | `str` | One of `"undeclared-var"`, `"unused-declared"`, `"typo-suggestion"` |
| `message` | `str` | Human-readable description |
| `severity` | `str` | `"warning"` (default) or `"error"` |

## Examples

### Catching a typo

```html
{% template user: User, items: list %}

<h1>{{ usr.name }}</h1>
<ul>
  {% for item in items %}
    <li>{{ item.title }}</li>
  {% endfor %}
</ul>
```

```
Line 3: Variable 'usr' used but not declared in {% template %} (did you mean 'user'?)
```

### Catching an undeclared variable

```html
{% template page: Page %}

<h1>{{ page.title }}</h1>
<p>{{ site.description }}</p>
```

```
Line 4: Variable 'site' used but not declared in {% template %}
```

### Detecting unused declarations

```html
{% template page: Page, nav_items: list, footer: dict %}

<h1>{{ page.title }}</h1>
```

```
Line 1: Declared variable 'nav_items' is never used
Line 1: Declared variable 'footer' is never used
```

## Limitations

- The type checker validates variable **names** only. It does not check that runtime values match the annotated types (e.g., it does not verify that `page` is actually a `Page` object).
- Typo suggestions use simple heuristics (prefix matching and edit distance of 1). Longer or more creative misspellings may not produce suggestions.
- Analysis is conservative for unused-declared checks: if a declared variable is only used inside a conditional branch, it is still counted as used.

## See Also

- [[docs/advanced/analysis|Static Analysis]] — Dependency analysis, purity detection, and caching recommendations
- [[docs/advanced/formatter|Template Formatter]] — Opinionated formatting with `kida fmt`
