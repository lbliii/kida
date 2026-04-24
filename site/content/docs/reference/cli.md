---
title: CLI Reference
description: Command-line tools for checking, rendering, formatting, inspecting, and generating with Kida templates
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
  - components
  - readme
  - extract
keywords:
  - kida check
  - kida render
  - kida fmt
  - kida components
  - kida readme
  - kida extract
  - command line
  - template validation
icon: terminal
---

# CLI Reference

Kida ships eight subcommands: `check`, `render`, `fmt`, `components`, `readme`, `extract`, `manifest`, and `diff`. All are available through the `kida` entry point or `python -m kida`.

```bash
kida <command> [options]
```

## Contract Status

The public CLI contract is the set of subcommands and flags documented here.
Output text can become clearer, but machine-readable JSON shapes for
`components --json`, `readme --json`, and `manifest` should only change
deliberately with docs and changelog updates when behavior changes.

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
| `--lint-fragile-paths` | Suggest `./` relative paths for same-folder include, extends, embed, and import statements so folder moves stay zero-edit. |

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
kida check templates/ --strict --validate-calls --a11y --typed --lint-fragile-paths
```

### Output format

Errors and warnings print to stderr, one per line:

```
layouts/base.html: unexpected tag 'endblock'
partials/nav.html:12: strict: unified {% end %} closes 'if' — prefer {% endif %}
components/card.html:8: a11y/img-alt [WARNING]: <img> missing alt attribute
```

`--validate-calls` diagnostics use stable `K-CMP-*` codes:

```
components/page.html:12: K-CMP-001: Call to 'card' — missing required: title
components/page.html:18: K-CMP-002: type: card() param 'count' expects int, got str ('many')
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
| `--mode {html,terminal,markdown}` | `html` | Rendering mode. `terminal` enables ANSI styling and width-aware layout. |
| `--width INT` | auto | Override terminal width (terminal mode only). |
| `--color {none,basic,256,truecolor}` | auto | Override color depth (terminal mode only). |
| `--data-format {json,junit-xml,sarif,lcov}` | `json` | Format of the data file. |
| `--set KEY=VALUE` | none | Set template variables (repeatable). Values are parsed as JSON if valid, otherwise kept as strings. |
| `--explain` | off | Show which compile-time optimizations were applied. |
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

## kida components

List all `{% def %}` components across templates in a directory. Useful for auditing component libraries and generating documentation.

```bash
kida components <template_dir> [flags]
```

**Positional argument:**

| Argument | Description |
|----------|-------------|
| `template_dir` | Root directory passed to `FileSystemLoader`. All `*.html` files are scanned recursively. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | off | Output as JSON for machine consumption. |
| `--filter NAME` | none | Filter components by name (case-insensitive substring match). |

### Examples

List all components:

```bash
kida components templates/
```

Filter by name:

```bash
kida components templates/ --filter card
```

Machine-readable output:

```bash
kida components templates/ --json
```

### Output format

Human-readable output groups by template file:

```
components/card.html
  def card(title: str, variant: str = ...)
    slots: (default), actions

components/nav.html
  def nav_link(href: str, label: str)

2 component(s) found.
```

JSON output produces an array of objects with `name`, `template`, `lineno`, `params`, `slots`, and `has_default_slot` fields.

## kida manifest

Render templates with capture instrumentation and emit a render manifest as
JSON. Frameworks can use this to track rendered block fragments and context
keys.

```bash
kida manifest <template_dir> [flags]
```

**Positional argument:**

| Argument | Description |
|----------|-------------|
| `template_dir` | Root directory passed to `FileSystemLoader`. All `*.html` and `*.kida` files are scanned recursively. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--output FILE` | stdout | Write manifest JSON to a file. |
| `--data FILE` | none | JSON object mapping template names to context dictionaries. |
| `--search` | off | Output a search manifest instead of the raw capture manifest. |

## kida diff

Compare two render manifests and report added, removed, and changed fragment
content hashes.

```bash
kida diff <old_manifest> <new_manifest>
```

**Positional arguments:**

| Argument | Description |
|----------|-------------|
| `old_manifest` | Path to the previous manifest JSON file. |
| `new_manifest` | Path to the new manifest JSON file. |

## kida readme

Auto-generate a README from project metadata. Detects project structure from `pyproject.toml`, filesystem, and git, then renders a styled markdown README using Kida's own template engine.

```bash
kida readme [root] [flags]
```

**Positional argument:**

| Argument | Default | Description |
|----------|---------|-------------|
| `root` | `.` (current directory) | Project root directory to scan. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output FILE` | stdout | Write to file instead of stdout. |
| `--preset {default,minimal,library,cli}` | auto-detected | Built-in template preset. Auto-detected from project type if not specified. |
| `--template FILE` | none | Path to a custom Kida template (overrides `--preset`). |
| `--set KEY=VALUE` | none | Override detected values (repeatable). Value is parsed as JSON, falls back to string. |
| `--depth INT` | `2` | Directory tree depth for project scanning. |
| `--json` | off | Dump auto-detected context as JSON instead of rendering. |

### Examples

Generate a README for the current project:

```bash
kida readme
```

Write to a file with a specific preset:

```bash
kida readme -o README.md --preset library
```

Override detected values:

```bash
kida readme --set description="A fast template engine" --set license=MIT
```

Inspect detected metadata:

```bash
kida readme --json
```

Use a custom template:

```bash
kida readme --template .github/readme.kida -o README.md
```

### Presets

| Preset | Best For |
|--------|----------|
| `default` | General projects with standard structure |
| `minimal` | Small projects or packages |
| `library` | Python libraries with API documentation focus |
| `cli` | CLI tools with command documentation focus |

### Python API

```python
from kida.readme import detect_project, render_readme

# Auto-detect metadata
ctx = detect_project(root_path, depth=2)

# Render with a preset
md = render_readme(root_path, preset="library")

# Render with custom template and overrides
md = render_readme(
    root_path,
    template=Path("custom.kida"),
    context={"description": "Override"},
)
```

## kida extract

Extract translatable messages from templates into a `.pot` (PO Template) file for internationalization workflows.

```bash
kida extract <template_dir> [flags]
```

**Positional argument:**

| Argument | Description |
|----------|-------------|
| `template_dir` | Root directory to scan for templates. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output FILE` | stdout | Write output to file instead of stdout. |
| `--ext .EXT` | `.html .kida .txt .xml` | File extensions to scan (repeatable). |

### Examples

Extract messages to stdout:

```bash
kida extract templates/
```

Write to a `.pot` file:

```bash
kida extract templates/ -o messages.pot
```

Scan only `.html` and `.kida` files:

```bash
kida extract templates/ --ext .html --ext .kida
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
