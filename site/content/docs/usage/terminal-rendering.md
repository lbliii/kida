---
title: Terminal Rendering
description: Declarative terminal/CLI output with ANSI colors, components, and live rendering
draft: false
weight: 28
lang: en
type: doc
tags:
  - usage
  - terminal
  - ansi
  - cli
keywords:
  - terminal rendering
  - ANSI
  - terminal mode
  - CLI output
  - autoescape terminal
  - LiveRenderer
icon: terminal
---

# Terminal Rendering

Kida's terminal rendering mode lets you build CLI dashboards, status reports, and interactive terminal UIs using the same template syntax you use for HTML. Set `autoescape="terminal"` and you get ANSI color filters, box-drawing components, progress bars, live re-rendering, and automatic degradation across color depths and character sets.

Terminal mode replaces HTML escaping with ANSI sanitization. Untrusted input has dangerous escape sequences (cursor movement, screen manipulation) stripped while safe SGR styling codes are preserved. The `Styled` class is the terminal analogue of `Markup` -- it marks content as already safe for terminal output.

## Quick Start

The fastest way to activate terminal mode is with `terminal_env()`, which creates a pre-configured `Environment` with built-in component templates:

```python
from kida.terminal import terminal_env

env = terminal_env()
template = env.from_string("""
{{ "Build Report" | bold | cyan }}
{{ hr(40) }}
{{ "Tests" | kv("412 passed", width=35) }}
{{ "Coverage" | kv("94.2%", width=35) }}
{{ 0.85 | bar(width=25) }}
""")
print(template.render())
```

You can also set terminal mode on a standard `Environment`:

```python
from kida import Environment

env = Environment(autoescape="terminal")
```

The difference is that `terminal_env()` adds a loader for the built-in component templates (`components.txt`), so you can `{% from "components.txt" import panel, header, footer %}`. When using `Environment(autoescape="terminal")` directly, you get all terminal filters and globals but need to supply your own loader if you want to import the component library.

### Environment Options

Both approaches accept these terminal-specific keyword arguments:

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `terminal_color` | `str` | Auto-detected | Color depth: `"none"`, `"basic"`, `"256"`, or `"truecolor"` |
| `terminal_width` | `int` | Auto-detected | Terminal width in columns |
| `terminal_unicode` | `bool` | Auto-detected | Whether to use Unicode box-drawing and icons |
| `ambiguous_width` | `int` | Auto-detected | Width for East Asian Ambiguous characters (1 or 2) |

```python
# Force basic 16-color output at 60 columns
env = terminal_env(terminal_color="basic", terminal_width=60)
```

### Template Globals

Terminal mode injects these globals into every template:

| Global | Type | Description |
|--------|------|-------------|
| `columns` | `int` | Terminal width in columns |
| `rows` | `int` | Terminal height in lines |
| `tty` | `bool` | Whether stdout is a TTY |
| `icons` | `IconSet` | Unicode/ASCII icon proxy |
| `box` | `BoxSet` | Box-drawing character set proxy |
| `hr()` | function | Horizontal rule generator |

## Terminal Filters

Terminal mode registers over 30 filters for styling, layout, and data display. All style filters return `Styled` strings that bypass ANSI sanitization.

### Color Filters

Named color filters apply ANSI foreground colors. When colors are disabled (`terminal_color="none"`), they return the text unchanged.

| Filter | SGR Code | Example |
|--------|----------|---------|
| `black` | 30 | `{{ text \| black }}` |
| `red` | 31 | `{{ text \| red }}` |
| `green` | 32 | `{{ text \| green }}` |
| `yellow` | 33 | `{{ text \| yellow }}` |
| `blue` | 34 | `{{ text \| blue }}` |
| `magenta` | 35 | `{{ text \| magenta }}` |
| `cyan` | 36 | `{{ text \| cyan }}` |
| `white` | 37 | `{{ text \| white }}` |
| `bright_red` | 91 | `{{ text \| bright_red }}` |
| `bright_green` | 92 | `{{ text \| bright_green }}` |
| `bright_yellow` | 93 | `{{ text \| bright_yellow }}` |
| `bright_blue` | 94 | `{{ text \| bright_blue }}` |
| `bright_magenta` | 95 | `{{ text \| bright_magenta }}` |
| `bright_cyan` | 96 | `{{ text \| bright_cyan }}` |

### Extended Color: `fg` and `bg`

The `fg` and `bg` filters accept named colors, hex strings, 256-color indices, and RGB tuples. They degrade automatically based on the terminal's color depth (see [Color Depth & Fallback](#color-depth--fallback)).

```kida
{# Hex color #}
{{ title | fg("#00ccff") }}

{# 256-color index #}
{{ status | fg(196) }}

{# Named color #}
{{ label | bg("blue") }}
```

### Decoration Filters

| Filter | Effect | SGR Code |
|--------|--------|----------|
| `bold` | Bold / bright | 1 |
| `dim` | Dim / faint | 2 |
| `italic` | Italic | 3 |
| `underline` | Underline | 4 |
| `blink` | Blink | 5 |
| `inverse` | Swap fg/bg | 7 |
| `strike` | Strikethrough | 9 |

Filters chain naturally:

```kida
{{ "CRITICAL" | bold | red }}
{{ filename | underline | cyan }}
{{ "(deprecated)" | dim | strike }}
```

### Layout Filters

#### `pad(width, align="left", fill=" ")`

ANSI-aware padding. Measures visible character width (ignoring escape sequences) and pads to the target width.

```kida
{{ name | pad(20) }}                     {# left-align in 20 cols #}
{{ count | pad(10, align="right") }}     {# right-align #}
{{ title | pad(40, align="center") }}    {# center #}
```

#### `wordwrap` / `wrap`

ANSI-aware word wrapping. Tracks active style state across line breaks so colors carry over to wrapped lines.

```kida
{{ long_text | wrap(60) }}
```

#### `truncate`

ANSI-aware truncation. Counts visible characters, not raw bytes, so ANSI codes never cause premature truncation or broken escape sequences.

```kida
{{ description | truncate(40) }}
```

#### `center`

ANSI-aware centering to the specified width.

```kida
{{ title | center(80) }}
```

### Data Display Filters

#### `badge`

Maps status keywords to colored icons. Recognized statuses: `pass`/`success`/`ok`, `fail`/`error`/`failed`, `warn`/`warning`, `skip`/`skipped`, `info`.

```kida
{{ "pass" | badge }}   {# green checkmark #}
{{ "fail" | badge }}   {# red cross #}
{{ "warn" | badge }}   {# yellow warning #}
{{ "skip" | badge }}   {# dim circle #}
```

When colors are disabled, badges render as ASCII labels: `[PASS]`, `[FAIL]`, `[WARN]`, `[SKIP]`.

#### `bar(width=20, show_pct=True)`

Progress bar from a 0.0--1.0 float value.

```kida
{{ 0.75 | bar(width=30) }}           {# block chars + percentage #}
{{ ratio | bar(width=20, show_pct=False) }}
```

Uses Unicode block characters when available, falls back to `[####----]` on ASCII terminals.

#### `kv(value, width=40, sep=" ", fill=".")`

Key-value pair with dot-leader fill.

```kida
{{ "Version" | kv("2.4.1", width=35) }}
{{ "Uptime" | kv("3h 42m", width=35) }}
```

#### `table(headers=None, border="light", align=None, max_width=None)`

Renders a list of dicts or list of lists as a bordered table.

```kida
{{ users | table(headers=["Name", "Role", "Status"]) }}
{{ data | table(border="heavy", align={"Score": "right"}) }}
{{ results | table(max_width=60) }}
```

Available border styles: `light`, `heavy`, `double`, `round`, `ascii`.

#### `tree(indent=2)`

Renders a nested dict as a tree with box-drawing connectors.

```kida
{{ directory_structure | tree }}
```

Outputs:

```
├── src
│   ├── main.py
│   └── utils.py
└── tests
    └── test_main.py
```

#### `diff(new, context=3)`

Unified diff between two strings with colored additions/deletions.

```kida
{{ old_config | diff(new_config) }}
```

Green `+` lines for additions, red `-` lines for deletions, cyan `@@` headers.

## Built-in Components

The component library lives in `components.txt` and provides reusable template macros for structured terminal layouts. Import them in any template loaded through `terminal_env()`:

```kida
{% from "components.txt" import panel, header, footer, row, cols, rule, connector, banner, stack, two_col, dl %}
```

Components are organized in three layers:

**Primitives** -- single-line building blocks:

- `row(content, width, border="|")` -- bordered line with ANSI-aware padding
- `cols(cells, sep=" ")` -- multi-column layout from `(content, width[, align])` tuples
- `rule(width, title="", char="---")` -- horizontal rule with optional title

**Components** -- bordered panels:

- `panel(title="", width=0, style="round", padding=1)` -- box with inline title in the top border
- `header(width=0, style="double")` -- double-bordered title bar
- `footer(width=0, style="heavy")` -- heavy-bordered summary bar
- `box(title="", width=0, style="round", padding=1)` -- bordered box with title in a separate header row
- `connector(indent=2)` -- vertical pipe between panels for visual continuity

**Layout helpers** -- content arrangement:

- `banner(text, width=0, char="=", padding=1)` -- full-width centered banner
- `two_col(left_width=0, sep=" | ")` -- two-column layout split on `|||`
- `stack(threshold=60, sep=" | ")` -- responsive: side-by-side when wide, stacked when narrow
- `dl(items, label_width=20, sep=" : ", color="cyan")` -- definition list

All components default their width to the `columns` global (terminal width) when `width=0`.

### Panel Example

```kida
{% from "components.txt" import panel %}

{% call panel(title="CPU Usage", width=60) %}
Core 0   {{ 0.67 | bar(width=20) }}
Core 1   {{ 0.25 | bar(width=20) }}
Core 2   {{ 0.91 | bar(width=20) }}
{% endcall %}
```

### Header + Panel + Footer Layout

A complete dashboard layout with header, content panels, connectors, and a footer:

```kida
{% from "components.txt" import header, panel, footer, connector %}
{% set w = 64 %}

{% call header(width=w) %}
{{ icons.gear | bright_cyan }} {{ "DEPLOY PIPELINE" | bold | bright_cyan | pad(20) }}{{ version | dim }}
{% endcall %}

{% for stage in stages %}
{% call panel(title=stage.name, width=w) %}
{{ stage.name | bold | pad(26) }}{{ stage.status | badge | pad(10) }}{{ stage.duration | dim }}
{% endcall %}
{% if not loop.last %}{{ connector() }}{% endif %}
{% endfor %}

{% call footer(width=w) %}
{{ icons.zap | yellow }} {{ "SUMMARY" | bold | yellow }}   {{ "Duration" | kv(total_duration, width=32) }}
{% endcall %}
```

### Responsive Stacking

The `stack` component renders side-by-side when the terminal is wide enough, and vertically when narrow. Split content with `|||`:

```kida
{% from "components.txt" import stack %}

{% call stack(threshold=80) %}
{{ icons.star }} {{ "Latency" | bold }}
  p50 {{ metrics.p50 }}
  p99 {{ metrics.p99 }}
|||
{{ icons.zap }} {{ "Health" | bold }}
  Uptime     {{ metrics.uptime }}
  Error Rate {{ metrics.error_rate }}
{% endcall %}
```

### Definition List

```kida
{% from "components.txt" import dl %}

{{ dl([
    ("Version", "2.4.1"),
    ("Uptime", "3h 42m"),
    ("Status", "running"),
], label_width=12) }}
```

## Color Depth & Fallback

The `fg()` and `bg()` filters degrade gracefully across four color depths. You write colors once and they render correctly everywhere:

| Depth | Env Variable / Detection | `fg("#00ccff")` Emits |
|-------|--------------------------|----------------------|
| `truecolor` | `COLORTERM=truecolor` or `24bit` | `\033[38;2;0;204;255m` |
| `256` | `TERM` contains `256color` | `\033[38;5;45m` (nearest cube color) |
| `basic` | TTY detected | `\033[36m` (nearest of 16 ANSI colors) |
| `none` | `NO_COLOR` set, or not a TTY | Plain text, no escapes |

The conversion pipeline:

1. **RGB to 256**: Maps to the nearest color in the 6x6x6 color cube (indices 16--231) or the grayscale ramp (232--255), whichever is closer by Euclidean distance.
2. **RGB/256 to basic 16**: Finds the nearest of the 16 standard ANSI colors by squared Euclidean distance against canonical RGB values.
3. **Named colors**: Always work at any depth -- `red`, `cyan`, `bright_green`, etc. use fixed SGR codes.

```python
# Force a specific color depth
env = terminal_env(terminal_color="256")

# Or let auto-detection handle it (default)
env = terminal_env()
```

## Character Width

Terminal output requires precise column alignment. ANSI escape sequences are zero-width (they occupy bytes but no screen columns), and some Unicode characters are double-width. Kida handles both.

### WidthStrategy

The `WidthStrategy` dataclass controls how ambiguous-width characters are measured:

```python
from kida.utils.ansi_width import WidthStrategy, configure_width

# Configure for CJK terminals where ambiguous chars render at double width
configure_width(ambiguous_width=2)
```

Width resolution follows a fallback chain when `ambiguous_width` is not explicitly set:

1. **Explicit override**: `Environment(ambiguous_width=2)` or `terminal_env(ambiguous_width=2)`
2. **Terminal probe**: Writes a test character and measures cursor movement via ANSI DSR
3. **`wcwidth` library**: Uses per-character width data if the optional `wcwidth` package is installed
4. **Locale heuristic**: CJK locales (`ja`, `ko`, `zh`) default to 2
5. **Default**: 1

### ANSI-Aware String Operations

All built-in string operations in terminal mode are ANSI-aware. They measure visible width (ignoring escape sequences) and handle double-width characters:

- `visible_len(s)` -- visible character count, ignoring ANSI escapes
- `ansi_ljust(s, width)` -- left-justify to visible width
- `ansi_rjust(s, width)` -- right-justify to visible width
- `ansi_center(s, width)` -- center within visible width
- `ansi_truncate(s, width)` -- truncate at visible width, preserving ANSI codes
- `ansi_wrap(s, width)` -- word-wrap at visible width, re-applying styles on new lines

The `pad`, `truncate`, `center`, and `wordwrap` template filters all use these functions automatically in terminal mode.

## LiveRenderer

`LiveRenderer` provides in-place terminal re-rendering. It uses ANSI cursor movement to overwrite previously rendered output, creating smooth animation effects.

```python
import time
from kida.terminal import terminal_env, LiveRenderer, Spinner

env = terminal_env()
tpl = env.from_string("""\
{% from "components.txt" import panel %}
{% call panel(title="Build", width=50) %}
{{ spinner() }} {{ status | bold | pad(20) }}{{ progress | bar(width=20) }}
{% endcall %}
""", name="live")

with LiveRenderer(tpl) as live:
    live.update(status="compiling", progress=0.0)
    time.sleep(1)
    live.update(status="testing", progress=0.5)
    time.sleep(1)
    live.update(status="done", progress=1.0)
```

### How It Works

1. On `__enter__`, the cursor is hidden to prevent flicker
2. Each `update(**context)` re-renders the template and overwrites the previous output using `\033[A` (cursor up) and `\033[2K` (erase line)
3. On `__exit__`, the cursor is restored; Ctrl+C is handled gracefully
4. Context accumulates across `update()` calls -- you only need to pass changed values

### Constructor Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `template` | `Template` | required | Compiled Kida template |
| `refresh_rate` | `float` | `0.1` | Minimum seconds between auto-refreshes |
| `file` | `TextIO` | `sys.stdout` | Output stream |
| `transient` | `bool` | `False` | Clear output on exit instead of leaving it |

### Auto-Refresh

For continuous animation (spinners, progress), use `start_auto()` to re-render in a background thread:

```python
with LiveRenderer(tpl, refresh_rate=0.1) as live:
    live.start_auto(status="building")
    # Spinner animates automatically every 0.1s
    time.sleep(5)
    live.stop_auto()
    live.update(status="done")
```

### Spinner

`Spinner` is a callable that returns a different frame on each call. It is automatically provided as `spinner` in `LiveRenderer` context.

```kida
{{ spinner() }} Loading...
```

Built-in frame sets:

| Name | Frames | Style |
|------|--------|-------|
| `Spinner.BRAILLE` / `Spinner.DOTS` | Braille dot pattern | Braille dots (default) |
| `Spinner.LINE` | `- \ \| /` | ASCII line spinner |
| `Spinner.ARROW` | Directional arrows | 8-direction rotation |

Custom frames:

```python
spinner = Spinner(frames=(".", "..", "...", "...."))
```

### Non-TTY Fallback

When output is not a TTY (piped, CI, etc.), `LiveRenderer` appends each render separated by a blank line instead of overwriting. No cursor manipulation is attempted.

## stream_to_terminal()

`stream_to_terminal()` writes `render_stream()` chunks progressively with an optional delay between them, creating a typewriter-style reveal effect.

```python
from kida.terminal import terminal_env, stream_to_terminal

env = terminal_env()
template = env.from_string("""
{{ "Build Log" | bold | cyan }}
{{ hr(40) }}
{% for step in steps %}
{{ icons.check | green }} {{ step }}
{% endfor %}
""")

stream_to_terminal(template, {"steps": ["compile", "test", "deploy"]}, delay=0.05)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `template` | `Template` | required | Compiled Kida template |
| `context` | `dict` | `None` | Template context variables |
| `delay` | `float` | `0.02` | Seconds between chunks (0 = no delay) |
| `file` | `TextIO` | `sys.stdout` | Output stream |

When output is not a TTY, the delay is skipped and all chunks are written immediately.

Use `{% flush %}` in templates to create explicit chunk boundaries for streaming.

## Icons & Box Drawing

### Icons

The `icons` global is an `IconSet` proxy. Access icons as attributes:

```kida
{{ icons.check }} All tests passed
{{ icons.arrow_r }} Next step
{{ icons.gear }} Settings
```

Available icons (Unicode / ASCII fallback):

| Name | Unicode | ASCII | | Name | Unicode | ASCII |
|------|---------|-------|-|------|---------|-------|
| `check` | ✓ | `[ok]` | | `arrow_r` | → | `->` |
| `cross` | ✗ | `[FAIL]` | | `arrow_l` | ← | `<-` |
| `warn` | ⚠ | `[!]` | | `arrow_u` | ↑ | `^` |
| `info` | ℹ | `[i]` | | `arrow_d` | ↓ | `v` |
| `dot` | ● | `*` | | `play` | ▶ | `>` |
| `circle` | ○ | `o` | | `stop` | ■ | `[]` |
| `star` | ★ | `*` | | `bullet` | • | `*` |
| `diamond` | ◆ | `*` | | `gear` | ⚙ | `[G]` |
| `flag` | ⚑ | `[F]` | | `zap` | ⚡ | `!` |
| `heart` | ♥ | `<3` | | `spark` | ✦ | `*` |
| `lock` | 🔒 | `[L]` | | `folder` | 📁 | `[D]` |
| `key` | 🔑 | `[K]` | | `file` | 📄 | `[F]` |

There is no generic `icons.arrow` — use a directional variant (`arrow_r`, `arrow_l`,
`arrow_u`, `arrow_d`) or `fat_arrow` (⇒). If you reference an unknown icon name, Kida
raises `AttributeError` with "did you mean?" suggestions.

Several icons append VS15 (U+FE0E, Variation Selector 15) to force text presentation and prevent emoji rendering in terminals that would otherwise display them as double-width color emoji.

When `terminal_unicode=False`, all icons return their ASCII fallback.

### Box Drawing

The `box` global is a `BoxSet` proxy with five built-in styles:

```kida
{% set b = box.round %}
{{ b.tl }}{{ b.h * 38 }}{{ b.tr }}
{{ b.v }} {{ "Hello, Terminal!" | bold | pad(36) }} {{ b.v }}
{{ b.bl }}{{ b.h * 38 }}{{ b.br }}
```

| Style | Corners | Lines | Description |
|-------|---------|-------|-------------|
| `box.light` | `+-+` | `-\|` | Light single-line |
| `box.heavy` | Heavy single | Thick lines | Heavy single-line |
| `box.double` | Double-line | Double lines | Double-line borders |
| `box.round` | Rounded corners | Light lines | Light with rounded corners |
| `box.ascii` | `+` | `-\|` | Pure ASCII, always available |

Each style provides these characters: `tl`, `tr`, `bl`, `br` (corners), `h`, `v` (lines), `lj`, `rj`, `tj`, `bj` (junctions), and `cross` (four-way junction).

When `terminal_unicode=False`, all styles fall back to `ascii`.

### Horizontal Rules

The `hr()` global generates horizontal rules:

```kida
{{ hr() }}                          {# full terminal width #}
{{ hr(40) }}                        {# 40 characters wide #}
{{ hr(60, title="Results") }}       {# -- Results ---------- #}
{{ hr(40, char="=") }}              {# ======== #}
```

## CLI: `kida render`

The `kida render` command renders a template to stdout from the command line. It defaults to terminal mode.

```bash
# Basic render with JSON data
kida render template.txt --data context.json

# Inline JSON
kida render template.txt --data-str '{"name": "world"}'

# Override width and color depth
kida render template.txt --data data.json --width 60 --color basic

# Progressive streaming output
kida render template.txt --data data.json --stream --stream-delay 0.05

# HTML mode (disables terminal features)
kida render template.txt --data data.json --mode html
```

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--data FILE` | Path | -- | JSON file providing template context |
| `--data-str JSON` | String | -- | Inline JSON context |
| `--mode` | `html` / `terminal` | `terminal` | Rendering mode |
| `--width N` | int | Auto | Override terminal width |
| `--color DEPTH` | `none`/`basic`/`256`/`truecolor` | Auto | Override color depth |
| `--stream` | flag | off | Progressive chunk-by-chunk output |
| `--stream-delay SECS` | float | `0.02` | Delay between streamed chunks |

The template's parent directory is used as the loader root, so `{% from "components.txt" import panel %}` works when `components.txt` is in the same directory.

## NO_COLOR / TTY Detection

Kida follows the [NO_COLOR](https://no-color.org/) convention and performs automatic TTY detection.

### Environment Variables

| Variable | Effect |
|----------|--------|
| `NO_COLOR` | Set to any value to disable all color output |
| `FORCE_COLOR` | Set to any value to force color output (overrides `NO_COLOR` and non-TTY) |
| `COLORTERM=truecolor` or `24bit` | Enables 24-bit RGB color |
| `TERM=*256color*` | Enables 256-color mode |

### Detection Order

Color depth is auto-detected in this order:

1. `NO_COLOR` set --> `"none"` (no colors)
2. `FORCE_COLOR` set --> `"basic"` (16 colors)
3. `COLORTERM` is `truecolor` or `24bit` --> `"truecolor"`
4. `TERM` contains `256color` --> `"256"`
5. stdout is a TTY --> `"basic"`
6. Otherwise --> `"none"`

### Unicode Detection

Unicode support is detected from the `LANG` environment variable. If `LANG` contains `UTF` (case-insensitive), Unicode box-drawing and icon characters are used. Otherwise, ASCII fallbacks are substituted.

### Non-TTY Behavior

When stdout is not a TTY:

- All colors are disabled (unless `FORCE_COLOR` is set)
- `LiveRenderer` appends output instead of overwriting
- `stream_to_terminal()` writes immediately with no delay
- `kida render` output is safe to pipe or redirect

## See Also

- [[docs/usage/streaming|Streaming]] -- `render_stream()` and `{% flush %}` for progressive output
- [[docs/usage/escaping|Escaping]] -- How autoescape modes work, including terminal sanitization
- [[docs/reference/api|API Reference]] -- Full method signatures for `Environment`, `Template`, and filters
