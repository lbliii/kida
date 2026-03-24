# Kida Terminal Mode Proposal

## 1. Executive Summary

Kida's rendering pipeline is output-agnostic except for one coupling: the escape function is hardcoded to `html_escape`. This proposal introduces a terminal rendering mode (`autoescape="terminal"`) that transforms Kida into the first declarative template engine for CLI/terminal output. The template source reads like the terminal output — WYSIWYG for CLIs.

The implementation adds no new compiler syntax. Everything is achieved through an escape strategy swap, a terminal-aware filter set, built-in component templates, and smart TTY detection. The architecture already supports this — streaming, components, inheritance, and block rendering all work unchanged.

## 2. Problem Statement

Every Python CLI tool reinvents output formatting imperatively:

```python
# Typical CLI output code — formatting tangled with logic
click.echo(click.style(f"  {name:<30}", fg="green") + click.style(f"{status}", fg="yellow"))
```

There is no declarative template layer for terminal output. `rich` is powerful but imperative (build renderables in Python). `click.style()` is minimal. `tabulate` handles one use case. Developers scatter formatting across command handlers, tangling presentation with business logic.

HTML solved this problem 20 years ago with template engines. Terminal output hasn't had the same treatment.

## 3. Design Principles

1. **The template IS the wireframe.** What you write looks like what you'll see.
2. **Zero new syntax.** Filters, globals, and `{% def %}` components — no compiler changes.
3. **Graceful degradation.** One template works everywhere: TTY, pipe, NO_COLOR, narrow terminals.
4. **Composable primitives.** Small filters that chain well beat monolithic constructs.
5. **Security by default.** Untrusted input is sanitized against terminal injection (ANSI escape attacks).

## 4. Architecture

### 4.1 Escape Strategy Swap

**Current coupling** (`template/core.py:199`):
```python
"_escape": html_escape,
```

**Proposed**: The escape function is selected based on `Environment.autoescape`:

| `autoescape` value | Escape function | Behavior |
|---|---|---|
| `True` (default) | `html_escape` | Current behavior — escapes `& < > " '` |
| `False` | `str` | No escaping |
| `"terminal"` | `ansi_sanitize` | Strips dangerous ANSI sequences, preserves safe styling |
| `callable` | User function | Current behavior — called per template name |

**Implementation site**: `template/core.py` `__init__`, where `namespace["_escape"]` is set.

### 4.2 Terminal Escape Function: `ansi_sanitize`

**File**: `src/kida/utils/terminal_escape.py`

Strips dangerous ANSI sequences from untrusted input while preserving safe styling sequences. This prevents terminal injection attacks (cursor repositioning, screen clearing, title rewriting, clipboard access via OSC).

**Safe sequences (preserved):**
- SGR (Select Graphic Rendition): `\033[...m` — colors, bold, underline, etc.

**Dangerous sequences (stripped):**
- Cursor movement: `\033[A`, `\033[B`, `\033[H`, etc.
- Screen manipulation: `\033[2J` (clear screen), `\033[K` (clear line)
- OSC sequences: `\033]...` (title set, clipboard, hyperlinks)
- Device control: `\033[6n` (cursor position report)
- Bracketed paste mode manipulation

**Approach**: Allowlist-based. Parse escape sequences and only preserve SGR (`\033[...m` where `...` is semicolon-separated digits). Strip everything else.

```python
_SAFE_SGR = re.compile(r"\033\[[\d;]*m")

def ansi_sanitize(value: object) -> str:
    """Strip dangerous ANSI sequences from untrusted values.

    Preserves color/style (SGR) sequences. Strips cursor movement,
    screen manipulation, OSC, and device control sequences.
    """
    s = str(value)
    if "\033" not in s:
        return s  # Fast path: no escape sequences

    # Extract safe SGR sequences, strip everything else
    safe_positions = [(m.start(), m.end()) for m in _SAFE_SGR.finditer(s)]
    # ... rebuild string keeping only safe sequences and plain text
```

### 4.3 ANSI-Width-Aware String Operations

**File**: `src/kida/utils/ansi_width.py`

ANSI escape sequences are zero-width but occupy bytes. Any padding, truncation, or wrapping operation must count *visible* characters, not raw string length.

```python
_ANSI_ESCAPE = re.compile(r"\033\[[^m]*m")

def visible_len(s: str) -> int:
    """Return the visible width of a string, ignoring ANSI escapes."""
    return len(_ANSI_ESCAPE.sub("", s))

def ansi_ljust(s: str, width: int, fillchar: str = " ") -> str:
    """Left-justify, ANSI-aware."""
    visible = visible_len(s)
    if visible >= width:
        return s
    return s + fillchar * (width - visible)

def ansi_rjust(s: str, width: int, fillchar: str = " ") -> str:
    """Right-justify, ANSI-aware."""
    visible = visible_len(s)
    if visible >= width:
        return s
    return fillchar * (width - visible) + s

def ansi_center(s: str, width: int, fillchar: str = " ") -> str:
    """Center, ANSI-aware."""
    visible = visible_len(s)
    if visible >= width:
        return s
    left = (width - visible) // 2
    right = width - visible - left
    return fillchar * left + s + fillchar * right

def ansi_truncate(s: str, width: int, suffix: str = "…") -> str:
    """Truncate to visible width, preserving ANSI state."""
    # Walk characters, tracking visible count, preserving escape sequences
    # Append suffix and reset code if truncated
    ...

def ansi_wrap(s: str, width: int) -> str:
    """Word-wrap at visible width, preserving ANSI state across lines."""
    # Track active style state, re-apply after each line break
    ...
```

### 4.4 `Styled` Safe-String Class

Analogous to `Markup` for HTML. A `str` subclass that marks content as already-styled, bypassing `ansi_sanitize` on output. Follows the same `__html__` protocol pattern.

**File**: `src/kida/utils/terminal_escape.py`

```python
class Styled(str):
    """A string that has been intentionally styled with ANSI codes.

    Bypasses ansi_sanitize() in terminal mode, just like Markup
    bypasses html_escape() in HTML mode. Use for template-generated
    styling (filters, components) — never for raw user input.
    """

    def __terminal__(self) -> str:
        return self

    def __add__(self, other: str) -> "Styled":
        if hasattr(other, "__terminal__"):
            return Styled(str.__add__(self, other))
        return Styled(str.__add__(self, ansi_sanitize(other)))

    # ... same operator overloading pattern as Markup
```

The escape function checks for `__terminal__()` just as `html_escape` checks for `__html__()`.

## 5. Primitives

### 5.1 Terminal Globals

Auto-injected when `autoescape="terminal"`:

```python
{
    "columns": os.get_terminal_size().columns,   # Terminal width (default: 80)
    "rows": os.get_terminal_size().lines,         # Terminal height (default: 24)
    "tty": sys.stdout.isatty(),                   # Is output a TTY?
    "icons": _ICON_SET,                           # Named icon dict (see §5.4)
    "box": _BOX_SETS,                             # Box-drawing character sets (see §5.5)
    "hr": _hr_func,                               # Horizontal rule helper (see §5.6)
}
```

Terminal size is captured once at Environment creation (not per-render) for consistency within a render pass. Users can override by passing `columns=N` in context.

### 5.2 Style Filters

Applied to any value. Return `Styled` strings. When `tty=False` or `NO_COLOR` is set, all style filters become identity functions (return plain text).

#### Colors (foreground)

```
{{ value | black }}
{{ value | red }}
{{ value | green }}
{{ value | yellow }}
{{ value | blue }}
{{ value | magenta }}
{{ value | cyan }}
{{ value | white }}
{{ value | bright_red }}
{{ value | bright_green }}
{{ value | bright_yellow }}
{{ value | bright_blue }}
{{ value | bright_magenta }}
{{ value | bright_cyan }}
```

**Extended colors:**
```
{{ value | fg(196) }}           # 256-color (0–255)
{{ value | fg("#ff6b2b") }}     # True-color (hex)
{{ value | fg(255, 107, 43) }}  # True-color (RGB)
```

#### Colors (background)

```
{{ value | bg("red") }}         # Named background
{{ value | bg(196) }}           # 256-color background
{{ value | bg("#1a1a2e") }}     # True-color background
```

#### Text decoration

```
{{ value | bold }}
{{ value | dim }}
{{ value | italic }}
{{ value | underline }}
{{ value | strike }}
{{ value | inverse }}
{{ value | blink }}             # Use sparingly
```

#### Chainable

```
{{ error_msg | red | bold | underline }}
{{ subtitle | bright_cyan | italic }}
```

Implementation: each filter wraps the string with `\033[Nm...\033[0m`, but nested application is smart — it resets only to the parent state, not fully, to avoid breaking outer styles. Since these run at template-render time and produce `Styled` strings, they're never re-escaped.

### 5.3 Layout Filters

All ANSI-width-aware. Use `visible_len()` internally.

#### Padding and alignment

```
{{ value | pad(30) }}                  # Right-pad to 30 visible chars (left-align)
{{ value | pad(30, "right") }}         # Left-pad (right-align)
{{ value | pad(30, "center") }}        # Center within 30 chars
{{ value | pad(30, fill=".") }}        # Custom fill character
```

#### Truncation

```
{{ value | truncate(40) }}             # Existing filter, made ANSI-aware in terminal mode
{{ value | truncate(40, end="…") }}    # Custom suffix
{{ value | truncate(40, end="") }}     # Hard cut, no suffix
```

#### Word wrapping

```
{{ value | wrap(80) }}                 # Word-wrap at 80 cols (ANSI-aware)
{{ value | wrap(columns) }}            # Dynamic to terminal width
{{ value | wrap(columns - 4) }}        # With margin
```

#### Indentation

```
{{ value | indent(4) }}                # Existing filter — works unchanged
{{ value | indent(4, "│ ") }}          # Custom prefix per line (tree/box style)
```

### 5.4 Icon Sets

A dict of named Unicode symbols, accessible as `icons.name` in templates. Each icon has a Unicode form and an ASCII fallback (used when terminal doesn't support Unicode or `TERM=dumb`).

```python
_ICONS = {
    # Status
    "check":      ("✓", "[ok]"),
    "cross":      ("✗", "[FAIL]"),
    "warn":       ("⚠", "[!]"),
    "info":       ("ℹ", "[i]"),
    "dot":        ("●", "*"),
    "circle":     ("○", "o"),
    "diamond":    ("◆", "*"),
    "star":       ("★", "*"),
    "heart":      ("♥", "<3"),
    "flag":       ("⚑", "[F]"),

    # Arrows
    "arrow_r":    ("→", "->"),
    "arrow_l":    ("←", "<-"),
    "arrow_u":    ("↑", "^"),
    "arrow_d":    ("↓", "v"),
    "fat_arrow":  ("⇒", "=>"),
    "return":     ("↵", "<-'"),

    # Progress / activity
    "play":       ("▶", ">"),
    "pause":      ("⏸", "||"),
    "stop":       ("■", "[]"),
    "record":     ("⏺", "(o)"),
    "reload":     ("⟳", "(R)"),
    "ellipsis":   ("…", "..."),

    # Bullets / list markers
    "bullet":     ("•", "*"),
    "dash":       ("–", "-"),
    "triangle_r": ("▸", ">"),
    "triangle_d": ("▾", "v"),

    # Misc
    "lock":       ("🔒", "[L]"),
    "unlock":     ("🔓", "[U]"),
    "key":        ("🔑", "[K]"),
    "link":       ("🔗", "[~]"),
    "clip":       ("📎", "[@]"),
    "folder":     ("📁", "[D]"),
    "file":       ("📄", "[F]"),
    "gear":       ("⚙", "[G]"),
    "spark":      ("✦", "*"),
    "zap":        ("⚡", "[!]"),
}
```

**Usage in templates:**
```
{{ icons.check | green }} All tests passed
{{ icons.cross | red }} Build failed
{{ icons.arrow_r }} Next step
{{ icons.warn | yellow }} {{ warnings | length }} warnings
```

**Fallback behavior**: When Unicode is not supported (`LANG` doesn't contain `UTF` and `TERM=dumb` or similar), the ASCII fallback is used automatically. Implemented as a simple proxy object:

```python
class IconSet:
    def __getattr__(self, name):
        icon = _ICONS.get(name)
        if icon is None:
            raise AttributeError(f"Unknown icon: {name}")
        return Styled(icon[0] if _use_unicode else icon[1])
```

### 5.5 Box-Drawing Character Sets

Named character sets for borders and boxes. Accessible as `box.style_name`.

```python
_BOX_SETS = {
    "light": BoxChars(
        tl="┌", tr="┐", bl="└", br="┘",
        h="─", v="│",
        lj="├", rj="┤", tj="┬", bj="┴", cross="┼",
    ),
    "heavy": BoxChars(
        tl="┏", tr="┓", bl="┗", br="┛",
        h="━", v="┃",
        lj="┣", rj="┫", tj="┳", bj="┻", cross="╋",
    ),
    "double": BoxChars(
        tl="╔", tr="╗", bl="╚", br="╝",
        h="═", v="║",
        lj="╠", rj="╣", tj="╦", bj="╩", cross="╬",
    ),
    "round": BoxChars(
        tl="╭", tr="╮", bl="╰", br="╯",
        h="─", v="│",
        lj="├", rj="┤", tj="┬", bj="┴", cross="┼",
    ),
    "ascii": BoxChars(
        tl="+", tr="+", bl="+", br="+",
        h="-", v="|",
        lj="+", rj="+", tj="+", bj="+", cross="+",
    ),
}
```

**`BoxChars` is a frozen dataclass** with a `__getattr__` that makes fields accessible in templates:

```
{{ box.round.tl }}{{ box.round.h * 40 }}{{ box.round.tr }}
{{ box.round.v }} {{ title | pad(38) }} {{ box.round.v }}
{{ box.round.bl }}{{ box.round.h * 40 }}{{ box.round.br }}
```

Renders:
```
╭────────────────────────────────────────╮
│ My Application                         │
╰────────────────────────────────────────╯
```

### 5.6 Horizontal Rules

```
{{ hr() }}                   # ──────────── (full terminal width)
{{ hr(40) }}                 # ──────────── (40 chars)
{{ hr(40, "═") }}            # ══════════════ (custom char)
{{ hr(40, "─", "Section") }} # ── Section ───────────────────────
```

Implemented as a global function, not a filter, since it generates content rather than transforming it.

### 5.7 Data Formatting Filters

#### Badge

Renders a status label with color and icon.

```
{{ "pass" | badge }}          # ✓ pass    (green)
{{ "fail" | badge }}          # ✗ fail    (red)
{{ "warn" | badge }}          # ⚠ warn    (yellow)
{{ "skip" | badge }}          # ○ skip    (dim)
{{ "info" | badge }}          # ℹ info    (blue)
{{ status | badge }}          # Auto-detects known statuses
```

Non-TTY degradation:
```
{{ "pass" | badge }}          # [PASS]
{{ "fail" | badge }}          # [FAIL]
```

Custom badges via keyword arguments:
```
{{ "deploy" | badge(icon="⚡", color="cyan") }}
```

#### Progress bar

```
{{ 0.6 | bar }}                  # ████████████░░░░░░░░ 60%
{{ 0.6 | bar(width=30) }}        # ██████████████████░░░░░░░░░░░░ 60%
{{ 0.6 | bar(show_pct=False) }}  # ████████████░░░░░░░░
```

Non-TTY degradation:
```
{{ 0.6 | bar }}                  # [############--------] 60%
```

#### Key-value pair

```
{{ "Version" | kv(app.version) }}        # Version ··········· 1.2.3
{{ "Status" | kv(status, width=40) }}    # Status ········· running
```

Aligns the key left, the value right, fills the gap with a configurable dot leader.

#### Table (filter form)

For simple cases — a list of dicts or list of lists:

```
{{ users | table }}
{{ users | table(headers=["Name", "Role", "Active"]) }}
{{ users | table(headers=["Name", "Role"], align={"Role": "center"}) }}
{{ users | table(border="round") }}
```

Output:
```
╭──────────┬───────────┬────────╮
│ Name     │   Role    │ Active │
├──────────┼───────────┼────────┤
│ Alice    │   admin   │ yes    │
│ Bob      │   user    │ no     │
╰──────────┴───────────┴────────╯
```

Non-TTY:
```
+----------+-----------+--------+
| Name     |   Role    | Active |
+----------+-----------+--------+
| Alice    |   admin   | yes    |
| Bob      |   user    | no     |
+----------+-----------+--------+
```

The `table` filter auto-sizes columns based on content width. Accepts optional `max_width` parameter to constrain total width (defaults to `columns`).

#### Tree

Renders a nested dict or list as a tree:

```
{{ file_tree | tree }}
```

Output:
```
├── src/
│   ├── main.py
│   └── utils/
│       ├── helpers.py
│       └── config.py
└── tests/
    └── test_main.py
```

Input structure:
```python
{"src/": {"main.py": None, "utils/": {"helpers.py": None, "config.py": None}}, "tests/": {"test_main.py": None}}
```

## 6. Components (via `{% def %}`)

These are shipped as includable template files in a `kida/terminal/` package directory, usable via:
```
{% from "kida/terminal/components.txt" import box, banner, columns, definition_list %}
```

Or available as importable defs when using a `TerminalEnvironment` convenience subclass.

### 6.1 Box Component

```
{% def box(title="", width=columns, style="round", padding=1) %}
{%- let b = box_chars[style] -%}
{%- let inner = width - 2 -%}
{{ b.tl }}{{ b.h * inner }}{{ b.tr }}
{% if title %}
{{ b.v }} {{ title | bold | pad(inner - 2) }} {{ b.v }}
{{ b.lj }}{{ b.h * inner }}{{ b.rj }}
{% end %}
{% for line in caller() | split("\n") %}
{{ b.v }}{{ " " * padding }}{{ line | pad(inner - padding * 2) }}{{ " " * padding }}{{ b.v }}
{% endfor %}
{{ b.bl }}{{ b.h * inner }}{{ b.br }}
{% end %}
```

**Usage:**
```
{% call box(title="Build Results", width=50) %}
  {{ icons.check | green }} Tests passed: {{ stats.passed }}
  {{ icons.cross | red }} Tests failed: {{ stats.failed }}
{% endcall %}
```

**Output:**
```
╭────────────────────────────────────────────────╮
│ Build Results                                  │
├────────────────────────────────────────────────┤
│ ✓ Tests passed: 42                             │
│ ✗ Tests failed: 3                              │
╰────────────────────────────────────────────────╯
```

### 6.2 Banner Component

```
{% def banner(text, width=columns, char="═", padding=1) %}
{%- let inner = width - 4 -%}
{{ char * width }}
{{ char }} {{ " " * padding }}{{ text | bold | pad(inner - padding * 2) }}{{ " " * padding }} {{ char }}
{{ char * width }}
{% end %}
```

**Usage:**
```
{{ banner("DEPLOYMENT REPORT") }}
```

**Output:**
```
════════════════════════════════════════════════════════════════════════
═  DEPLOYMENT REPORT                                                 ═
════════════════════════════════════════════════════════════════════════
```

### 6.3 Two-Column Layout Component

```
{% def two_col(left_width=None, sep=" │ ") %}
{%- let parts = caller() | split("|||") -%}
{%- let lw = left_width ?? (columns // 2 - sep | length) -%}
{%- let rw = columns - lw - (sep | length) -%}
{%- let left_lines = parts[0] | wrap(lw) | split("\n") -%}
{%- let right_lines = parts[1] | wrap(rw) | split("\n") -%}
{%- let max_lines = [left_lines | length, right_lines | length] | max -%}
{% for i in 0..max_lines %}
{{ (left_lines[i] ?? "") | pad(lw) }}{{ sep }}{{ (right_lines[i] ?? "") | pad(rw) }}
{% endfor %}
{% end %}
```

### 6.4 Definition List Component

```
{% def dl(items, label_width=20, sep=" : ", color="cyan") %}
{% for label, value in items %}
{{ label | attr(color) | pad(label_width, "right") }}{{ sep }}{{ value }}
{% endfor %}
{% end %}
```

**Usage:**
```
{{ dl([
    ("Version", app.version),
    ("Uptime", app.uptime | duration),
    ("Memory", app.memory | filesizeformat),
    ("Status", app.status | badge),
]) }}
```

**Output:**
```
        Version : 2.4.1
         Uptime : 3h 42m
         Memory : 1.2 GiB
         Status : ✓ running
```

### 6.5 Diff Component

```
{% def diff(old, new) %}
{% for line in _diff_lines(old, new) %}
{% if line.type == "add" %}{{ ("+ " + line.text) | green }}
{% elif line.type == "remove" %}{{ ("- " + line.text) | red }}
{% else %}{{ "  " + line.text | dim }}
{% end %}
{% endfor %}
{% end %}
```

## 7. TTY Detection and Degradation

### 7.1 Detection hierarchy

```python
def _detect_terminal_capabilities() -> TerminalCaps:
    """Detect terminal capabilities once at Environment creation."""
    return TerminalCaps(
        is_tty=sys.stdout.isatty(),
        color=_detect_color_support(),   # none | basic | 256 | truecolor
        unicode=_detect_unicode_support(),
        width=os.get_terminal_size(fallback=(80, 24)).columns,
        height=os.get_terminal_size(fallback=(80, 24)).lines,
    )

def _detect_color_support() -> str:
    if os.environ.get("NO_COLOR"):
        return "none"
    if os.environ.get("FORCE_COLOR"):
        return os.environ.get("COLORTERM", "basic")
    if not sys.stdout.isatty():
        return "none"
    colorterm = os.environ.get("COLORTERM", "")
    if colorterm in ("truecolor", "24bit"):
        return "truecolor"
    term = os.environ.get("TERM", "")
    if "256color" in term:
        return "256"
    return "basic"
```

### 7.2 Degradation rules

| Capability | TTY + color | TTY + NO_COLOR | Pipe / non-TTY |
|---|---|---|---|
| Color filters | ANSI codes | Identity (plain text) | Identity (plain text) |
| `bold`, `dim`, etc. | ANSI codes | Identity | Identity |
| `icons.*` | Unicode symbol | Unicode symbol | ASCII fallback |
| `badge` | Icon + color | Text label | `[PASS]`, `[FAIL]` |
| `bar` | `█░` + color | `█░` plain | `[####----]` |
| `table` border | Box-drawing chars | Box-drawing chars | ASCII `+`, `-`, `|` |
| `columns` global | Actual width | Actual width | 80 |

### 7.3 Override mechanism

```python
env = Environment(
    autoescape="terminal",
    # Override detected capabilities:
    terminal_color="truecolor",   # Force color mode
    terminal_width=120,           # Force width
    terminal_unicode=True,        # Force Unicode
)
```

## 8. Streaming Use Cases

Kida's `render_stream()` and `render_stream_async()` are uniquely valuable for terminal output:

### 8.1 Progressive output for long-running commands

```python
template = env.get_template("scan-report.txt")
for chunk in template.render_stream(results=scan_generator()):
    sys.stdout.write(chunk)
    sys.stdout.flush()
```

Template:
```
{{ banner("Security Scan") }}

{% for finding in results %}
{{ finding.severity | badge | pad(12) }} {{ finding.path | dim }}
  {{ finding.message | wrap(columns - 4) | indent(4) }}
{% endfor %}
```

Each finding streams as it's discovered. No buffering the full report.

### 8.2 `{% flush %}` for explicit chunk boundaries

Already exists in Kida. In terminal mode, flush maps to `sys.stdout.flush()` semantics:

```
{% for step in pipeline %}
{{ icons.play }} {{ step.name }}... {% flush %}
{# — appears immediately, before step completes — #}
{{ step.run() | badge }}
{% endfor %}
```

### 8.3 Async streaming from external sources

```python
async for chunk in template.render_stream_async(events=kafka_consumer):
    sys.stdout.write(chunk)
```

```
{% async for event in events %}
{{ event.timestamp | dim }} {{ event.level | badge }} {{ event.message | wrap(columns - 30) }}
{% end %}
```

## 9. Implementation Plan

### Phase 1: Foundation (core escape + globals + style filters)

| File | Change | Lines |
|---|---|---|
| `src/kida/utils/terminal_escape.py` | New: `ansi_sanitize()`, `Styled` class | ~120 |
| `src/kida/utils/ansi_width.py` | New: `visible_len()`, ANSI-aware pad/truncate/wrap | ~150 |
| `src/kida/template/core.py` | Escape function selection based on `autoescape` | ~15 |
| `src/kida/environment/core.py` | Terminal globals injection, capability detection | ~40 |
| `src/kida/environment/filters/_terminal.py` | New: style filters (colors, bold, dim, etc.) | ~200 |
| `src/kida/environment/filters/_impl.py` | Register terminal filters conditionally | ~10 |
| `tests/terminal/` | New: tests for escape, width, style filters | ~300 |

**Deliverable**: `autoescape="terminal"` works. Templates can use color/style filters, `columns` global, and ANSI-safe escaping.

### Phase 2: Data filters + icons

| File | Change | Lines |
|---|---|---|
| `src/kida/utils/terminal_icons.py` | New: `IconSet`, `_ICONS` dict | ~80 |
| `src/kida/utils/terminal_boxes.py` | New: `BoxChars`, `_BOX_SETS` dict | ~60 |
| `src/kida/environment/filters/_terminal.py` | Add: `badge`, `bar`, `kv`, `table`, `tree` filters | ~400 |
| `tests/terminal/` | Tests for data filters, icons, boxes | ~400 |

**Deliverable**: Full filter set. Icons and box-drawing characters available as globals.

### Phase 3: Components + degradation

| File | Change | Lines |
|---|---|---|
| `src/kida/terminal/components.txt` | New: box, banner, two_col, dl, diff components | ~120 |
| `src/kida/environment/core.py` | TTY detection, degradation dispatch | ~60 |
| `src/kida/environment/filters/_terminal.py` | Degradation paths for all filters | ~100 |
| `tests/terminal/` | Degradation tests (pipe, NO_COLOR, dumb term) | ~200 |

**Deliverable**: Components importable from templates. Full graceful degradation.

### Phase 4: Documentation + examples

| File | Change |
|---|---|
| `examples/terminal_basic/` | Simple CLI output example |
| `examples/terminal_dashboard/` | Multi-section status dashboard |
| `examples/terminal_report/` | Streaming scan report |
| `examples/terminal_interactive/` | Progressive output with flush |

## 10. API Surface Summary

### Filters added (terminal mode only)

**Style (16):** `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`, `bright_red`, `bright_green`, `bright_yellow`, `bright_blue`, `bright_magenta`, `bright_cyan`, `fg`, `bg`

**Decoration (7):** `bold`, `dim`, `italic`, `underline`, `strike`, `inverse`, `blink`

**Layout (2):** `pad`, `wrap` (existing `truncate`, `indent`, `center`, `wordwrap` made ANSI-aware)

**Data (5):** `badge`, `bar`, `kv`, `table`, `tree`

**Total: 30 new filters, 4 existing filters enhanced**

### Globals added (terminal mode only)

`columns`, `rows`, `tty`, `icons`, `box`, `hr`

### New utilities

`ansi_sanitize()`, `Styled`, `visible_len()`, `ansi_ljust()`, `ansi_rjust()`, `ansi_center()`, `ansi_truncate()`, `ansi_wrap()`, `IconSet`, `BoxChars`

## 11. Non-Goals

- **Interactive TUI**: Kida renders strings. It does not manage cursor position, handle keyboard input, or replace `curses`/`textual`. It produces the text; the caller writes it to stdout.
- **Animation**: No built-in spinner or animation loop. `render_stream()` enables progressive output, but frame-by-frame animation is the caller's responsibility.
- **Replacing rich**: Kida terminal mode is for declarative templates. `rich` is for imperative rendering. They complement each other — you could even use `rich` Console to print Kida's rendered output.
- **Windows legacy console**: ANSI support requires Windows 10+ or Windows Terminal. No Win32 console API fallback.

## 12. Open Questions

1. **Filter namespace pollution**: 30 new filters is significant. Should terminal filters be prefixed (e.g., `t_red`, `t_bold`) or only registered in terminal mode? Current proposal: only registered when `autoescape="terminal"`.

2. **`table` filter vs `{% table %}` block**: The filter handles simple cases (list of dicts). Should we eventually add a `{% table %}` block statement for complex column definitions, or is `{% def %}` sufficient for custom layouts?

3. **Color theme support**: Should there be a way to define a color theme (e.g., `error=red+bold`, `success=green`, `muted=dim`) that semantic filters reference? e.g., `{{ msg | style("error") }}` instead of `{{ msg | red | bold }}`.

4. **Template file extension**: Should terminal templates use `.txt`, `.term`, `.cli`, or just `.html` with the environment deciding? Recommendation: no convention enforced — the environment's `autoescape` setting controls behavior, not the filename.

5. **`Styled` interop with `Markup`**: If a `Markup` object is rendered in terminal mode, should it be stripped of HTML tags? Or treated as plain text? Recommendation: `str()` conversion — HTML entities are meaningless in a terminal.
