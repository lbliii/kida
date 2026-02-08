# RFC: Kida Documentation Site

**Status**: ✅ Implemented  
**Created**: 2026-01-04  
**Updated**: 2026-02-08  
**Author**: Kida Contributors

---

## Executive Summary

Create a documentation site for Kida at `kida/site/` using Bengal as the static site generator. This enables dogfooding of both projects—Bengal consumes Kida for templating, and Kida's documentation is built with Bengal—creating a self-reinforcing ecosystem.

**Key Outcomes:**
- **Dogfooding**: Bengal builds Kida docs using Kida templates
- **Ecosystem validation**: Proves Bengal + Kida integration works
- **Developer documentation**: Comprehensive docs for Kida adoption
- **Network effect**: Bengal, Rosettes, Kida all use the same toolchain

---

## Background

### The Ecosystem

```
┌─────────────────────────────────────────────────────────────┐
│                        Bengal Ecosystem                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Bengal (SSG)  ──uses──>  Kida (templates)                 │
│        │                        │                            │
│        │ builds                 │ builds                     │
│        ▼                        ▼                            │
│   bengal/site/            kida/site/                         │
│                                                              │
│   Rosettes (syntax) <──used by── Bengal                     │
│        │                                                     │
│        │ builds                                              │
│        ▼                                                     │
│   rosettes/site/                                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Each package in the ecosystem:
1. **Bengal**: Static site generator (builds all doc sites)
2. **Kida**: Template engine (used by Bengal for rendering)
3. **Rosettes**: Syntax highlighting (used by Bengal for code blocks)

### Existing Patterns

| Site | Repository | Structure |
|------|------------|-----------|
| Bengal docs | `bengal/site/` | Full-featured reference site |
| Rosettes docs | `rosettes/site/` | Compact library documentation |

Kida's site follows the Rosettes pattern—compact library documentation—with additional sections for tutorials and extensibility based on patterns proven successful in both Bengal and Rosettes.

---

## Goals

1. **Complete documentation**: API reference, syntax guide, usage patterns, examples
2. **Jinja2 migration path**: Clear comparison and step-by-step migration tutorial
3. **Extensibility guide**: Custom filters, tests, loaders, and globals
4. **Dogfooding**: Use Bengal + Kida to build the site
5. **Consistent branding**: Match Bengal ecosystem visual style
6. **Autodoc integration**: Auto-generate API docs from Python source

### Non-Goals

- Complex multi-version documentation (v0.1.x only initially)
- Internationalization (English only)
- Blog/changelog content (use GitHub Releases)

---

## Site Structure

### Directory Layout

```
kida/site/
├── config/
│   ├── _default/
│   │   ├── autodoc.yaml      # API doc generation
│   │   ├── build.yaml        # Build settings
│   │   ├── content.yaml      # Content processing
│   │   ├── fonts.yaml        # Typography
│   │   ├── params.yaml       # Custom parameters
│   │   ├── site.yaml         # Site metadata
│   │   └── theme.yaml        # Theme settings
│   └── environments/
│       ├── local.yaml        # Dev server overrides
│       └── production.yaml   # GitHub Pages settings
├── content/
│   ├── _index.md             # Homepage
│   ├── api/
│   │   └── _index.md         # API overview (autodoc populates)
│   ├── docs/
│   │   ├── _index.md         # Documentation hub
│   │   ├── get-started/
│   │   │   ├── _index.md     # Get Started overview
│   │   │   ├── installation.md
│   │   │   └── quickstart.md
│   │   ├── syntax/
│   │   │   ├── _index.md     # Syntax overview
│   │   │   ├── variables.md
│   │   │   ├── control-flow.md
│   │   │   ├── filters.md
│   │   │   ├── functions.md
│   │   │   ├── inheritance.md
│   │   │   ├── includes.md
│   │   │   ├── caching.md
│   │   │   └── async.md
│   │   ├── usage/
│   │   │   ├── _index.md     # Usage overview
│   │   │   ├── loading-templates.md
│   │   │   ├── rendering-contexts.md
│   │   │   ├── escaping.md
│   │   │   └── error-handling.md
│   │   ├── tutorials/
│   │   │   ├── _index.md     # Tutorials hub
│   │   │   ├── migrate-from-jinja2.md
│   │   │   ├── flask-integration.md
│   │   │   └── custom-filters.md
│   │   ├── extending/
│   │   │   ├── _index.md     # Extending overview
│   │   │   ├── custom-filters.md
│   │   │   ├── custom-tests.md
│   │   │   ├── custom-globals.md
│   │   │   └── custom-loaders.md
│   │   ├── reference/
│   │   │   ├── _index.md     # Reference overview
│   │   │   ├── api.md        # API quick reference
│   │   │   ├── filters.md    # Filter reference
│   │   │   ├── tests.md      # Test reference
│   │   │   └── configuration.md
│   │   ├── troubleshooting/
│   │   │   ├── _index.md     # Troubleshooting overview
│   │   │   ├── undefined-variable.md
│   │   │   └── template-not-found.md
│   │   └── about/
│   │       ├── _index.md     # About overview
│   │       ├── architecture.md
│   │       ├── performance.md
│   │       ├── thread-safety.md
│   │       ├── comparison.md
│   │       └── faq.md
│   └── releases/
│       ├── _index.md
│       └── 0.1.0.md
├── assets/
│   └── fonts/                # Outfit font files
└── public/                   # Build output (gitignored)
```

### Content Plan

#### Homepage (`_index.md`)

Hero section with:
- Tagline: "Modern template engine for Python 3.14t"
- Key features: AST-native, free-threading ready, zero dependencies
- Quick install: `pip install kida`
- Minimal example showing template rendering

Feature cards:
- **AST-Native Compilation**: No string manipulation
- **Free-Threading Ready**: PEP 703 compliant
- **Modern Syntax**: Unified `{% end %}`, pattern matching, pipelines
- **Zero Dependencies**: Pure Python, includes native Markup class

#### Get Started Section

| Page | Purpose |
|------|---------|
| `installation.md` | pip, uv, from source |
| `quickstart.md` | First template in 2 minutes |

#### Syntax Section

| Page | Content |
|------|---------|
| `variables.md` | `{{ }}`, expressions, escaping |
| `control-flow.md` | `{% if %}`, `{% for %}`, `{% match %}` |
| `filters.md` | Built-in filters, custom filters, pipelines |
| `functions.md` | `{% def %}`, macros, parameters |
| `inheritance.md` | `{% extends %}`, `{% block %}`, overrides |
| `includes.md` | `{% include %}`, partials |
| `caching.md` | `{% cache %}` directive, block-level caching |
| `async.md` | `async for`, `await`, async templates |

#### Usage Section

| Page | Content |
|------|---------|
| `loading-templates.md` | FileSystemLoader, PackageLoader, DictLoader patterns |
| `rendering-contexts.md` | Passing variables, nested contexts, globals |
| `escaping.md` | HTML escaping, Markup class, safe filter |
| `error-handling.md` | Template errors, debugging, stack traces |

#### Tutorials Section

| Page | Content |
|------|---------|
| `migrate-from-jinja2.md` | Step-by-step migration with before/after examples, API mapping table, verification steps |
| `flask-integration.md` | Integrate Kida with Flask/FastAPI applications |
| `custom-filters.md` | Build custom filters from scratch |

#### Extending Section

| Page | Content |
|------|---------|
| `custom-filters.md` | Register and implement custom filters |
| `custom-tests.md` | Create custom test functions (`is_*`) |
| `custom-globals.md` | Add global functions and variables |
| `custom-loaders.md` | FileSystemLoader, DictLoader, custom loaders |

#### Reference Section

| Page | Content |
|------|---------|
| `api.md` | Environment, Template, Markup classes |
| `filters.md` | All built-in filters with examples |
| `tests.md` | All built-in tests (is_defined, etc.) |
| `configuration.md` | Environment options, loader config |

#### Troubleshooting Section

| Page | Content |
|------|---------|
| `undefined-variable.md` | Debugging undefined variable errors |
| `template-not-found.md` | Fixing template loading issues |

#### About Section

| Page | Content |
|------|---------|
| `architecture.md` | Lexer → Parser → Compiler → Template pipeline |
| `performance.md` | StringBuilder vs generators, benchmarks |
| `thread-safety.md` | PEP 703, concurrent rendering |
| `comparison.md` | Kida vs Jinja2 comprehensive feature table |
| `faq.md` | Common questions: "Why not Jinja2?", "Production ready?", etc. |

---

## Configuration

### `config/_default/site.yaml`

```yaml
# Kida Documentation Site Configuration

site:
  title: "Kida"
  logo_text: ")彡"
  description: "Modern template engine for Python 3.14t — AST-native, free-threading ready"
  language: "en"

# Template Engine (dogfooding!)
template_engine: kida
```

### `config/_default/params.yaml`

```yaml
# Custom Parameters

params:
  project_status: "beta"
  repo_url: "https://github.com/lbliii/kida"
  min_python: "3.14"
```

### `config/_default/autodoc.yaml`

```yaml
# Autodoc Configuration
# Generates API documentation from Kida's Python source

autodoc:
  github_repo: "lbliii/kida"
  github_branch: "main"

  python:
    enabled: true
    source_dirs:
      - ../src/kida

    docstring_style: auto
    output_prefix: "api"
    display_name: "Kida API Reference"

    exclude:
      - "*/tests/*"
      - "*/test_*.py"
      - "*/__pycache__/*"
      - "*/.venv/*"

    include_private: false
    include_special: false

  cli:
    enabled: false

  openapi:
    enabled: false
```

### `config/_default/theme.yaml`

```yaml
# Theme Configuration

theme:
  name: default

  features:
    syntax_highlighting: true
    search: true
    toc: true

  colors:
    # Accent color for Kida branding
    primary: "#7c3aed"  # Purple (template/magic feel)
```

### `config/_default/build.yaml`

```yaml
# Build Configuration

build:
  output_dir: "public"
  clean: true

  # Asset handling
  assets:
    minify_css: true
    minify_js: true

  # HTML output
  html:
    pretty: false
    minify: true
```

### `config/_default/content.yaml`

```yaml
# Content Processing Configuration

content:
  # Markdown settings
  markdown:
    smart_punctuation: true
    heading_anchors: true

  # Code blocks
  code:
    syntax_highlighting: true
    line_numbers: false
    copy_button: true
```

### `config/_default/fonts.yaml`

```yaml
# Font Configuration

fonts:
  primary:
    family: "Outfit"
    weights: [400, 600, 700]
    source: "local"

  code:
    family: "JetBrains Mono"
    weights: [400, 500]
    source: "google"
```

### `config/environments/production.yaml`

```yaml
# Production (GitHub Pages)

site:
  baseurl: "https://lbliii.github.io/kida"
```

### `config/environments/local.yaml`

```yaml
# Local Development

site:
  baseurl: "http://localhost:8000"

build:
  html:
    minify: false
```

---

## Homepage Content

```markdown
---
title: Kida
description: Modern template engine for Python 3.14t
template: home.html
weight: 100
type: page
draft: false
lang: en
keywords: [kida, template-engine, jinja2, python, free-threading, async]
category: home

blob_background: true

cta_buttons:
  - text: Get Started
    url: /docs/get-started/
    style: primary
  - text: Syntax Guide
    url: /docs/syntax/
    style: secondary

show_recent_posts: false
---

## Templates, Evolved

**AST-native. Free-threading ready. Zero regex.**

Kida is a pure-Python template engine designed for Python 3.14t+. It compiles templates directly to Python AST—no string manipulation, no regex, no security vulnerabilities.

```python
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")
print(template.render(name="World"))
# Output: Hello, World!
```

---

## Why Kida?

:::{cards}
:columns: 2
:gap: medium

:::{card} AST-Native Compilation
:icon: cpu
Compiles templates to `ast.Module` objects directly. No string concatenation, no regex parsing, no code generation vulnerabilities.
:::{/card}

:::{card} Free-Threading Ready
:icon: zap
Built for Python 3.14t (PEP 703). Renders templates concurrently without the GIL. Declares `_Py_mod_gil = 0`.
:::{/card}

:::{card} Modern Syntax
:icon: code
Unified `{% end %}` for all blocks. Pattern matching with `{% match %}`. Pipelines with `|>`. Built-in caching.
:::{/card}

:::{card} Zero Dependencies
:icon: package
Pure Python with no runtime dependencies. Includes native `Markup` class—no markupsafe required.
:::{/card}

:::{/cards}

---

## Quick Comparison

| Feature | Kida | Jinja2 |
|---------|------|--------|
| **Compilation** | AST → AST | String generation |
| **Rendering** | StringBuilder O(n) | Generator yields |
| **Block endings** | Unified `{% end %}` | `{% endif %}`, `{% endfor %}` |
| **Async** | Native `async for` | `auto_await()` wrapper |
| **Pattern matching** | `{% match %}` | N/A |
| **Free-threading** | Native (PEP 703) | N/A |

---

## Performance

StringBuilder rendering is 25-40% faster than Jinja2's generator pattern:

```python
# Kida: O(n) StringBuilder
_out.append(...)
return "".join(_out)

# Jinja2: Generator yields (higher overhead)
yield ...
```

| Template Size | Kida | Jinja2 | Speedup |
|---------------|------|--------|---------|
| Small (10 vars) | 0.3ms | 0.5ms | 1.6x |
| Medium (100 vars) | 2ms | 3.5ms | 1.75x |
| Large (1000 vars) | 15ms | 25ms | 1.67x |

---

## Zero Dependencies

Kida is pure Python with no runtime dependencies:

```toml
[project]
dependencies = []  # Zero!
```

Includes a native `Markup` class for safe HTML handling—no markupsafe required.
```

---

## Implementation Plan

### Phase 1: Scaffold Site Structure

1. Create directory structure:
   ```bash
   mkdir -p kida/site/{config/_default,config/environments,content/{docs,api,releases},assets/fonts}
   ```

2. Copy configuration files from Rosettes as templates

3. Customize for Kida branding (logo, colors, descriptions)

### Phase 2: Core Content

1. **Homepage** (`content/_index.md`)
   - Hero, feature cards, comparison table, quick example

2. **Get Started** (`content/docs/get-started/`)
   - Installation, quickstart

3. **Syntax Guide** (`content/docs/syntax/`)
   - Variables, control flow, filters, functions

4. **Usage Guide** (`content/docs/usage/`)
   - Loading templates, rendering contexts, escaping, error handling

### Phase 3: Tutorials & Extending

1. **Tutorials** (`content/docs/tutorials/`)
   - Jinja2 migration (step-by-step with before/after)
   - Flask integration
   - Custom filters tutorial

2. **Extending** (`content/docs/extending/`)
   - Custom filters, tests, globals, loaders

### Phase 4: Reference Content

1. **API Reference** (`content/docs/reference/`)
   - Generated from autodoc + manual examples

2. **Troubleshooting** (`content/docs/troubleshooting/`)
   - Common errors and fixes

3. **About** (`content/docs/about/`)
   - Architecture, performance, thread-safety, comparison, FAQ

### Phase 5: Autodoc Integration

1. Configure `autodoc.yaml` to point to `../src/kida`

2. Run Bengal to generate API docs

3. Review and enhance generated content

### Phase 6: Polish and Deploy

1. Review all content for accuracy

2. Test site builds successfully

3. Configure GitHub Pages deployment

4. Add CI workflow for automatic builds

---

## Build Commands

```bash
# Development server
cd kida && bengal serve site/

# Production build
cd kida && bengal build site/

# Verify links
cd kida && bengal validate site/
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/docs.yaml
name: Build Documentation

on:
  push:
    branches: [main]
    paths:
      - 'site/**'
      - 'src/**'
  pull_request:
    paths:
      - 'site/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Install dependencies
        run: |
          pip install bengal kida

      - name: Build site
        run: bengal build site/

      - name: Deploy to GitHub Pages
        if: github.ref == 'refs/heads/main'
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site/public
```

---

## Success Criteria

1. ☐ Site builds successfully with Bengal
2. ☐ All pages render with Kida templates
3. ☐ Autodoc generates API reference
4. ☐ Search functionality works
5. ☐ Mobile-responsive layout
6. ☐ Syntax highlighting for code blocks (via Rosettes)
7. ☐ GitHub Pages deployment works
8. ☐ All internal links valid
9. ☐ Tutorials follow Rosettes' step-by-step format
10. ☐ Extending section covers all extension points

---

## Timeline Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Scaffold | 1 hour | None |
| Phase 2: Core content | 5 hours | Phase 1 |
| Phase 3: Tutorials & Extending | 4 hours | Phase 2 |
| Phase 4: Reference content | 3 hours | Phase 3 |
| Phase 5: Autodoc | 1 hour | Phase 4 |
| Phase 6: Polish & deploy | 2 hours | Phase 5 |
| **Total** | **~16 hours** | |

---

## Appendix A: Syntax Showcase Content

### Variables Page Preview

```markdown
---
title: Variables
description: Output expressions and variable access in Kida templates
---

# Variables

## Basic Output

Use double braces to output expressions:

```kida
{{ name }}
{{ user.email }}
{{ items[0] }}
{{ 1 + 2 }}
```

## HTML Escaping

By default, output is HTML-escaped:

```kida
{{ "<script>" }}  {# Outputs: &lt;script&gt; #}
```

Mark content as safe with the `safe` filter:

```kida
{{ html_content | safe }}
```

## Pipelines

Chain filters with the `|>` operator:

```kida
{{ title |> escape |> upper |> truncate(50) }}
```

Equivalent to nested calls:

```kida
{{ title | escape | upper | truncate(50) }}
```
```

### Control Flow Page Preview

```markdown
---
title: Control Flow
description: Conditionals, loops, and pattern matching in Kida
---

# Control Flow

## Conditionals

```kida
{% if user.is_admin %}
    <span class="badge">Admin</span>
{% elif user.is_moderator %}
    <span class="badge">Mod</span>
{% else %}
    <span class="badge">User</span>
{% end %}
```

Note: Kida uses unified `{% end %}` for all blocks.

## Loops

```kida
{% for item in items %}
    <li>{{ item.name }}</li>
{% else %}
    <li>No items found</li>
{% end %}
```

Loop context:

```kida
{% for item in items %}
    {{ loop.index }}      {# 1-based index #}
    {{ loop.index0 }}     {# 0-based index #}
    {{ loop.first }}      {# True on first iteration #}
    {{ loop.last }}       {# True on last iteration #}
    {{ loop.length }}     {# Total items #}
{% end %}
```

## Pattern Matching

```kida
{% match status %}
{% case "active" %}
    ✓ Active
{% case "pending" %}
    ⏳ Pending
{% case "error" %}
    ✗ Error: {{ error_message }}
{% case _ %}
    Unknown status
{% end %}
```
```

---

## Appendix B: Migration Tutorial Format

Based on the successful `rosettes/site/content/docs/tutorials/migrate-from-pygments.md` pattern:

```markdown
---
title: Migrate from Jinja2
description: Switch from Jinja2 to Kida for template rendering
---

# Migrate from Jinja2

Switch from Jinja2 to Kida for faster, safer template rendering.

## Prerequisites

- Python 3.14+
- Existing Jinja2 templates
- Basic understanding of template syntax

## Step 1: Install Kida

```bash
pip install kida
```

## Step 2: Update Imports

**Before (Jinja2):**

```python
from jinja2 import Environment, FileSystemLoader
```

**After (Kida):**

```python
from kida import Environment, FileSystemLoader
```

## Step 3: Update Environment Creation

**Before (Jinja2):**

```python
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True,
)
```

**After (Kida):**

```python
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True,
)
```

## Step 4: Update Block Endings

Update to unified `{% end %}` syntax:

**Jinja2 style (works in Kida):**

```kida
{% if condition %}...{% endif %}
{% for item in items %}...{% endfor %}
```

**Kida style (recommended):**

```kida
{% if condition %}...{% end %}
{% for item in items %}...{% end %}
```

## API Mapping

| Jinja2 | Kida |
|--------|------|
| `Environment` | `Environment` |
| `FileSystemLoader` | `FileSystemLoader` |
| `Template.render()` | `Template.render()` |
| `Markup` (markupsafe) | `Markup` (built-in) |
| `{% endif %}` | `{% end %}` (or `{% endif %}`) |

## Verification

```python
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")
result = template.render(name="World")
assert result == "Hello, World!"
print("✅ Migration successful!")
```

## Next Steps

- [[docs/syntax/control-flow|Control Flow]] — New pattern matching syntax
- [[docs/about/comparison|Comparison]] — Full Kida vs Jinja2 comparison
- [[docs/about/performance|Performance]] — Benchmark results
```

---

## References

**Existing Sites:**
- Bengal docs: `bengal/site/`
- Rosettes docs: `rosettes/site/`

**Dependencies:**
- Bengal: Static site generator
- Kida: Template engine (being documented)
- Rosettes: Syntax highlighting
