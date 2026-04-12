# RFC: Terminal Rendering Tutorial — Outline

**Status**: Draft
**Created**: 2026-04-12
**Epic**: `plan/epic-kida-milo-integration.md` — Sprint 0, Task 0.2

---

## Target Audience

Python developer who:
- Knows Kida for HTML rendering (has read getting-started or used Flask/Django integration)
- Hasn't used terminal rendering mode
- Wants to build CLI tools with rich output (colors, progress, live updates)
- May or may not know about Milo

---

## Placement

**File**: `site/content/docs/tutorials/terminal-rendering.md`
**Weight**: 25 (between Flask integration at 20 and Custom Filters at 30)
**Index card** in `_index.md`:

```markdown
:::{card} Terminal Rendering
:icon: terminal
:link: /docs/tutorials/terminal-rendering/
:description: Build rich terminal output with colors, components, and live updates
Render templates to the terminal with ANSI colors, responsive layouts, and real-time animation.
:::{/card}
```

---

## Frontmatter

```yaml
---
title: Terminal Rendering
description: Build rich terminal output with colors, components, and live updates
draft: false
weight: 25
lang: en
type: doc
tags:
- tutorial
- terminal
- cli
keywords:
- terminal rendering
- cli output
- ansi colors
- live rendering
- dashboard
- progress bars
icon: terminal
---
```

---

## Section Outline

### Section 1: Your First Terminal Render (~300 words)

**Goal**: Get colored output in 5 lines.

```python
from kida.terminal import terminal_env

env = terminal_env()
tpl = env.from_string('{{ "Hello" | bold | cyan }} from Kida!')
print(tpl.render())
```

Cover:
- `terminal_env()` factory vs manual `Environment(autoescape="terminal")`
- Running with `kida render template.txt --mode terminal`
- Basic filters: `bold`, `dim`, `underline`, `cyan`, `green`, `red`, `yellow`

**Code examples**: 2 (inline string, CLI command)

---

### Section 2: Colors and Graceful Degradation (~400 words)

**Goal**: Understand color depth and how it fails gracefully.

Cover:
- Color depth: `none` / `basic` / `256` / `truecolor`
- `terminal_env(terminal_color="basic")` vs auto-detection
- `NO_COLOR` / `FORCE_COLOR` environment variables
- `fg("#ff6600")` for hex colors, `fg("red")` for named
- What happens when truecolor template runs on basic terminal (auto-fallback)
- `kida render template.txt --color basic` for testing

**Code examples**: 3 (auto-detect, explicit color, fallback demo)

:::note[Testing Tip]
Use `--color none` to see exactly what your template renders without ANSI codes.
:::

---

### Section 3: Layout and Built-in Components (~500 words)

**Goal**: Build a structured dashboard with panels, headers, and rules.

Cover:
- `hr(width)` — horizontal rules
- `pad(width)` — padding
- `kv(value, width, sep)` — key-value pairs
- `badge()` — status badges
- `bar(width)` — progress bars
- Icons: `icons.check`, `icons.cross`, `icons.warn`, `icons.gear`
- Built-in component templates: `panel`, `header`, `cols`, `row`, `rule`
- Using `{% from "components.txt" import panel, header %}`

**Code examples**: 2 (inline with filters, FileSystemLoader with components.txt)

---

### Section 4: LiveRenderer — Animated Output (~500 words)

**Goal**: Build a live-updating status display.

Cover:
- `LiveRenderer` context manager
- `live.update(**context)` — re-render in place
- `live.start_auto(**context)` / `live.stop_auto()` — spinner animation
- `spinner()` filter in templates
- Thread safety (frozen state, atomic swap)
- Typical pattern: loop with sleep + update

```python
from kida.terminal import LiveRenderer, terminal_env

env = terminal_env()
tpl = env.from_string(TEMPLATE)

with LiveRenderer(tpl) as live:
    for step in deploy_steps:
        run_step(step)
        live.update(steps=steps, current=step)
```

**Code examples**: 1 (full working deploy status)

---

### Section 5: Optimize with static_context (~400 words)

**Goal**: Make rendering faster by folding known values at compile time.

Cover:
- What `static_context` does (compile-time constant folding, dead branch elimination)
- When to use it (app config, version, feature flags — anything known at startup)
- `env.from_string(template, static_context={...})` API
- `kida render template.txt --explain` to see what got optimized
- Before/after comparison (conceptual, not benchmark numbers)

```python
# Values known at app startup — fold at compile time
static = {"app_name": "deployer", "version": "2.1.0", "debug": False}

tpl = env.from_string(TEMPLATE, static_context=static)

# Only pass dynamic data at render time
tpl.render(services=current_services)
```

:::note[How it works]
With `debug: False` in static_context, the entire `{% if debug %}` block is removed from the compiled template. Zero runtime cost.
:::

**Code examples**: 2 (with/without static_context, --explain output)

---

### Section 6: Streaming Output (~250 words)

**Goal**: Show progressive rendering for long output.

Cover:
- `stream_to_terminal(template, context, delay=0.02)` API
- `kida render template.txt --stream --stream-delay 0.05`
- When to use streaming vs LiveRenderer

**Code examples**: 1 (CLI streaming command)

---

### Section 7: Complete Example — Service Dashboard (~200 words + full code)

**Goal**: Tie everything together in one runnable example.

A terminal dashboard that:
- Uses `FileSystemLoader` with a `templates/` directory
- Has a `dashboard.txt` template using components, colors, status badges
- Uses `static_context` for app config
- Uses `LiveRenderer` for live updates
- Simulates fetching service status in a loop

Reference `examples/terminal_dashboard/` for the pattern.

**Code examples**: 1 (full working example with directory structure)

---

### Section 8: Next Steps (~100 words)

Links to:
- [[docs/reference/terminal-filters|Terminal Filter Reference]]
- [[docs/reference/terminal-components|Built-in Components]]
- Terminal API contract (`docs/terminal-api-contract.md`)
- Milo for interactive terminal apps (external link)
- `examples/terminal_*` for more patterns

---

## Estimated Total

| Section | Words | Code Examples |
|---------|-------|---------------|
| 1. First Render | 300 | 2 |
| 2. Colors | 400 | 3 |
| 3. Components | 500 | 2 |
| 4. LiveRenderer | 500 | 1 |
| 5. static_context | 400 | 2 |
| 6. Streaming | 250 | 1 |
| 7. Complete Example | 200 | 1 |
| 8. Next Steps | 100 | 0 |
| **Total** | **~2,650** | **12** |

---

## Conventions to Follow

From analysis of existing tutorials:
- Language tags: `python`, `bash`, `kida` for code blocks
- Callouts: `:::note[Title]` ... `:::`
- Internal links: `[[docs/path|Text]]`
- All code examples must be copy-pasteable and produce described output
- No speculative performance claims — refer to `--explain` and benchmarks
