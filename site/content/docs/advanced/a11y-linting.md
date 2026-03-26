---
title: Accessibility Linting
description: Static accessibility checks for templates — img-alt, heading-order, html-lang, input-label
draft: false
weight: 68
lang: en
type: doc
tags:
  - advanced
  - accessibility
  - linting
keywords:
  - accessibility
  - a11y
  - linting
  - img-alt
  - heading-order
icon: eye
---

# Accessibility Linting

Kida can statically analyze parsed templates for common accessibility issues — missing alt text, skipped heading levels, missing `lang` attributes, and unlabeled form elements. Checks run against the template AST, so they catch issues in static markup without requiring a render pass.

```python
from kida.analysis.a11y import check_a11y
```

## Available Rules

| Rule | Severity | What It Checks |
|---|---|---|
| `img-alt` | error | `<img>` tags must have an `alt` attribute. Images with `role="presentation"` or `role="none"` are exempt. |
| `heading-order` | warning | Heading levels must not skip (e.g., `<h2>` directly followed by `<h4>`). |
| `html-lang` | warning | The `<html>` tag must have a `lang` attribute. |
| `input-label` | warning | `<input>`, `<select>`, and `<textarea>` elements must have an associated `<label for="...">`, `aria-label`, `aria-labelledby`, or `title` attribute. Hidden inputs are exempt. |

## Usage

### Python API

Run accessibility checks on any parsed template AST:

```python
from kida import Environment, DictLoader
from kida.analysis.a11y import check_a11y

env = Environment(
    loader=DictLoader({
        "page.html": """
            <html>
            <body>
                <img src="photo.jpg">
                <h1>Title</h1>
                <h3>Skipped h2</h3>
                <input type="text" name="email">
            </body>
            </html>
        """
    }),
    preserve_ast=True,
)

template = env.get_template("page.html")
issues = check_a11y(template._optimized_ast)

for issue in issues:
    print(f"Line {issue.lineno}: [{issue.rule}] {issue.message}")
```

Output:

```text
Line 2: [html-lang] <html> missing lang attribute
Line 4: [img-alt] <img> missing alt attribute
Line 6: [heading-order] Heading level skipped: <h3> after <h1> (expected <h2>)
Line 7: [input-label] Form element missing associated <label> or aria-label
```

### CLI

```bash
kida check --a11y templates/
```

### A11yIssue

Each finding is returned as an `A11yIssue` dataclass:

| Field | Type | Description |
|---|---|---|
| `lineno` | `int` | Line number in the template source |
| `col_offset` | `int` | Column offset |
| `rule` | `str` | Rule identifier (`img-alt`, `heading-order`, `html-lang`, `input-label`) |
| `message` | `str` | Human-readable description of the issue |
| `severity` | `str` | `"error"` or `"warning"` (default: `"warning"`) |

Results are sorted by `(lineno, col_offset)`.

### Build System Integration

Integrate accessibility linting into a build pipeline to fail on errors:

```python
from kida import Environment, FileSystemLoader
from kida.analysis.a11y import check_a11y

env = Environment(
    loader=FileSystemLoader("templates/"),
    preserve_ast=True,
)

errors = []
for template_name in env.loader.list_templates():
    template = env.get_template(template_name)
    issues = check_a11y(template._optimized_ast)
    for issue in issues:
        errors.append((template_name, issue))

if errors:
    for name, issue in errors:
        print(f"{name}:{issue.lineno} [{issue.rule}] {issue.message}")
    raise SystemExit(1)
```

## Examples of Violations and Fixes

### img-alt

Missing `alt` attribute on an `<img>` tag.

```html
<!-- violation -->
<img src="hero.jpg">

<!-- fix: add descriptive alt text -->
<img src="hero.jpg" alt="Mountain landscape at sunset">

<!-- fix: decorative image — mark as presentational -->
<img src="divider.png" role="presentation">
```

### heading-order

Heading levels must increase by one. Skipping from `<h1>` to `<h3>` is a violation.

```html
<!-- violation -->
<h1>Page Title</h1>
<h3>Subsection</h3>

<!-- fix -->
<h1>Page Title</h1>
<h2>Subsection</h2>
```

### html-lang

The `<html>` element must declare a language.

```html
<!-- violation -->
<html>

<!-- fix -->
<html lang="en">
```

### input-label

Form elements need an associated label. The linter accepts any of: a `<label>` with a matching `for` attribute, `aria-label`, `aria-labelledby`, or `title`.

```html
<!-- violation -->
<input type="text" name="email">

<!-- fix: explicit label -->
<label for="email">Email</label>
<input type="text" name="email" id="email">

<!-- fix: aria-label -->
<input type="text" name="email" aria-label="Email address">

<!-- exempt: hidden inputs are skipped -->
<input type="hidden" name="csrf_token" value="abc">
```

## Configuration

The `check_a11y()` function runs all rules unconditionally. To filter results by rule or severity, post-process the returned list:

```python
issues = check_a11y(template._optimized_ast)

# Only errors
errors = [i for i in issues if i.severity == "error"]

# Exclude specific rules
filtered = [i for i in issues if i.rule not in {"heading-order"}]

# Group by rule
from itertools import groupby
by_rule = {k: list(v) for k, v in groupby(issues, key=lambda i: i.rule)}
```

To enforce a strict policy in CI, treat all issues as failures:

```python
issues = check_a11y(template._optimized_ast)
if issues:
    for issue in issues:
        print(f"  Line {issue.lineno}: [{issue.rule}] {issue.message}")
    raise SystemExit(1)
```

To enforce only errors (ignoring warnings):

```python
errors = [i for i in check_a11y(template._optimized_ast) if i.severity == "error"]
if errors:
    raise SystemExit(1)
```

## See Also

- [[docs/advanced/analysis|Static Analysis]] — Dependency and purity analysis
- [[docs/advanced/coverage|Template Coverage]] — Line-level coverage tracking
