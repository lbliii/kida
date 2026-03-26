---
title: Template Formatter
description: Opinionated template formatting with kida fmt
draft: false
weight: 62
lang: en
type: doc
tags:
  - advanced
  - formatter
  - tooling
keywords:
  - formatter
  - kida fmt
  - formatting
  - code style
icon: align-left
---

# Template Formatter

Kida includes an opinionated template formatter that enforces consistent whitespace, indentation, and tag spacing across your templates. No other Python template engine ships with a built-in formatter.

## Quick Start

Format all templates in a directory:

```bash
kida fmt templates/
```

Format a single file:

```bash
kida fmt templates/page.html
```

Check formatting without modifying files (useful in CI):

```bash
kida fmt --check templates/
```

## What It Does

The formatter applies six rules to every template:

| Rule | Before | After |
|------|--------|-------|
| **Tag spacing** | `{%if x%}` | `{% if x %}` |
| **Output spacing** | `{{expr}}` | `{{ expr }}` |
| **Comment spacing** | `{#note#}` | `{# note #}` |
| **Block indentation** | Flat or inconsistent | Indented by configured amount |
| **Trailing whitespace** | `<div>   ` | `<div>` |
| **Blank line normalization** | 3+ consecutive blank lines | Max 1 consecutive blank line |
| **Final newline** | Missing or present | Always present |

### Tag Spacing

The formatter normalizes spacing inside all three tag types. Whitespace control markers (`-`) are preserved:

```html
{# Before #}
{%-  if user  -%}{{user.name}}{%endif%}

{# After #}
{%- if user -%}{{ user.name }}{% endif %}
```

### Block Indentation

Block bodies are indented by the configured amount (default: 2 spaces). The formatter recognizes all Kida block-opening keywords:

`if`, `for`, `block`, `while`, `with`, `def`, `region`, `call`, `capture`, `cache`, `filter`, `match`, `spaceless`, `embed`, `raw`, `push`, `globals`, `imports`, `unless`, `fragment`

Continuation keywords (`else`, `elif`, `empty`, `case`) are aligned with their opening tag, and their bodies are indented:

```html
{% if user.is_admin %}
  <span>Admin</span>
{% elif user.is_staff %}
  <span>Staff</span>
{% else %}
  <span>User</span>
{% endif %}
```

## Configuration

The `format_template` function accepts three options:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `indent` | `int` | `2` | Number of spaces per indentation level |
| `max_blank_lines` | `int` | `1` | Maximum consecutive blank lines allowed |
| `normalize_tag_spacing` | `bool` | `True` | Normalize spacing inside `{% %}`, `{{ }}`, and `{# #}` tags |

```python
from kida.formatter import format_template

formatted = format_template(
    source,
    indent=4,               # 4 spaces per level
    max_blank_lines=2,       # Allow up to 2 consecutive blank lines
    normalize_tag_spacing=True,
)
```

## Programmatic API

Import `format_template` directly for build scripts, pre-commit hooks, or editor integrations:

```python
from kida.formatter import format_template

source = open("templates/page.html").read()
formatted = format_template(source)

if source != formatted:
    open("templates/page.html", "w").write(formatted)
    print("Formatted page.html")
```

## CI Integration

Use the `--check` flag to fail CI when templates are not formatted. This does not modify any files — it only reports whether formatting changes are needed:

```bash
kida fmt --check templates/
```

A non-zero exit code means at least one file needs formatting. Pair this with your existing linting step:

```yaml
# GitHub Actions example
- name: Check template formatting
  run: kida fmt --check templates/
```

## Before and After

### Inconsistent spacing and flat indentation

**Before:**

```html
{%block sidebar%}
<aside>
{%if categories%}
<ul>
{%for cat in categories%}
<li>{{cat.name}}</li>
{%endfor%}
</ul>
{%endif%}
</aside>
{%endblock%}
```

**After:**

```html
{% block sidebar %}
  <aside>
    {% if categories %}
      <ul>
        {% for cat in categories %}
          <li>{{ cat.name }}</li>
        {% endfor %}
      </ul>
    {% endif %}
  </aside>
{% endblock %}
```

### Whitespace control markers preserved

**Before:**

```html
{%-  for item in items  -%}
{{-item.name-}}
{%-endfor-%}
```

**After:**

```html
{%- for item in items -%}
  {{- item.name -}}
{%- endfor -%}
```

## See Also

- [[docs/advanced/analysis|Static Analysis]] — Analyze templates for dependencies and caching potential
- [[docs/advanced/type-checking|Template Type Checking]] — Validate template context with `{% template %}` declarations
