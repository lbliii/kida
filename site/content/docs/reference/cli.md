---
title: CLI Reference
description: Command-line tools for checking, rendering, and formatting Kida templates
draft: false
weight: 35
lang: en
type: doc
tags:
  - reference
  - cli
  - check
  - render
  - fmt
keywords:
  - kida check
  - kida render
  - kida fmt
  - command line
  - template validation
icon: terminal
---

# CLI Reference

Kida ships three subcommands: `check` for validation, `render` for output, and `fmt` for formatting. All are available through the `kida` entry point or `python -m kida`.

```bash
kida <command> [options]
```

## kida check

Parse all `.html` templates under a directory. Reports syntax errors, loader resolution failures, and optional lint checks.

```bash
kida check <template_dir> [flags]
```

**Positional argument:**

| Argument | Description |
|----------|-------------|
| `template_dir` | Root directory passed to `FileSystemLoader`. All `*.html` files are scanned recursively. |

**Flags:**

| Flag | Description |
|------|-------------|
| `--strict` | Fail on bare `{% end %}` closers. Requires explicit `{% endif %}`, `{% endblock %}`, `{% endcall %}`, etc. |
| `--validate-calls` | Validate macro call sites against `{% def %}` signatures. Reports unknown parameters, missing required parameters, and duplicates. |
| `--a11y` | Check templates for accessibility issues (missing `alt` attributes, heading order, etc.). |
| `--typed` | Type-check templates against `{% template %}` declarations. |

### Examples

Basic syntax check:

```bash
kida check templates/
```

Strict mode with call validation:

```bash
kida check templates/ --strict --validate-calls
```

Full lint pass (all checks enabled):

```bash
kida check templates/ --strict --validate-calls --a11y --typed
```

### Output format

Errors and warnings print to stderr, one per line:

```
layouts/base.html: unexpected tag 'endblock'
partials/nav.html:12: strict: unified {% end %} closes 'if' — prefer {% endif %}
components/card.html:8: a11y/img-alt [WARNING]: <img> missing alt attribute
```

## kida render

Render a single template to stdout. Supports HTML and terminal rendering modes.

```bash
kida render <template> [flags]
```

**Positional argument:**

| Argument | Description |
|----------|-------------|
| `template` | Path to the template file to render. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--data FILE` | none | JSON file providing template context variables. |
| `--data-str JSON` | none | Inline JSON string providing template context variables. |
| `--mode {html,terminal}` | `terminal` | Rendering mode. `terminal` enables ANSI styling and width-aware layout. |
| `--width INT` | auto | Override terminal width (terminal mode only). |
| `--color {none,basic,256,truecolor}` | auto | Override color depth (terminal mode only). |
| `--stream` | off | Progressive output: reveal template chunks with a brief delay. |
| `--stream-delay SECONDS` | `0.02` | Delay between stream chunks. Requires `--stream`. |

### Examples

Render with inline data:

```bash
kida render page.html --data-str '{"title": "Hello"}'
```

Render from a JSON file in HTML mode:

```bash
kida render page.html --data context.json --mode html
```

Terminal mode with explicit width and color:

```bash
kida render dashboard.html --width 120 --color 256
```

Streaming output:

```bash
kida render report.html --data stats.json --stream --stream-delay 0.05
```

## kida fmt

Auto-format Kida template files. Accepts individual files or directories (scans for `*.html` recursively).

```bash
kida fmt <paths...> [flags]
```

**Positional argument:**

| Argument | Description |
|----------|-------------|
| `paths` | One or more files or directories to format. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--indent INT` | `2` | Spaces per indentation level. |
| `--check` | off | Check formatting without writing changes. Exits `1` if any file would be reformatted. |

### Examples

Format all templates in a directory:

```bash
kida fmt templates/
```

Format specific files with 4-space indent:

```bash
kida fmt layouts/base.html partials/nav.html --indent 4
```

CI check (no writes, non-zero exit on drift):

```bash
kida fmt templates/ --check
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success. No errors or formatting drift. |
| `1` | One or more problems found (`check`), render failure, or formatting drift (`fmt --check`). |
| `2` | Invalid input: path not found, bad JSON data, or unknown command. |

## See Also

- [[docs/reference/configuration|Configuration Reference]] — environment and loader options
- [[docs/reference/filters|Filters Reference]] — built-in filters
- [[docs/reference/api|API Reference]] — Python API for `Environment`, `FileSystemLoader`, and templates
