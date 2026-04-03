# Kida Terminal API Contract

Stability guarantees for downstream consumers (Milo, CLI tools, dashboards).

**Status**: Stable since v0.3.0. No breaking changes without major version bump.

---

## Import Surface

```python
# Factory
from kida.terminal import terminal_env

# Live rendering
from kida.terminal import LiveRenderer, Spinner, stream_to_terminal

# Types (for type hints only)
from kida.environment.terminal import TerminalCaps
from kida.utils.terminal_escape import Styled
from kida.utils.terminal_boxes import BoxChars, BoxSet
from kida.utils.terminal_icons import IconSet
```

---

## `terminal_env(**kwargs) -> Environment`

Creates a terminal-configured Environment. Sets `autoescape="terminal"`, registers terminal filters/globals, chains user loader with built-in component templates.

**Accepted kwargs** (in addition to all `Environment` params):
- `loader` — User's template loader (chained before built-in components)
- `terminal_color` — `"none"` | `"basic"` | `"256"` | `"truecolor"` (auto-detected)
- `terminal_width` — Override terminal width in columns (auto-detected)
- `terminal_unicode` — Override Unicode support (auto-detected)
- `ambiguous_width` — `1` (narrow) or `2` (wide) for CJK (auto-detected)

**Guaranteed behavior**:
- Returns a fully configured `Environment` with all terminal filters and globals
- Auto-detects terminal capabilities (color depth, width, Unicode)
- Respects `NO_COLOR` and `FORCE_COLOR` environment variables
- Thread-safe: returned Environment is safe for concurrent use

---

## `LiveRenderer`

Context manager for in-place terminal re-rendering.

```python
LiveRenderer(
    template: Template,
    *,
    refresh_rate: float = 0.1,
    file: TextIO | None = None,
    transient: bool = False,
)
```

**Public methods**:
- `update(**context)` — Re-render with merged context. Thread-safe.
- `start_auto(**context)` — Start background auto-refresh loop (for spinners)
- `stop_auto()` — Stop background auto-refresh

**Guaranteed behavior**:
- Hides cursor on enter, restores on exit (including Ctrl+C)
- TTY: in-place re-rendering via ANSI cursor movement
- Non-TTY: appends each render separated by blank line (log-safe)
- Handles terminal resize
- Thread-safe context updates via internal lock

---

## `Spinner`

Animated frame cycler for use in templates.

```python
spinner = Spinner()          # Default: Braille frames
spinner = Spinner(Spinner.LINE)  # Custom frames
frame = spinner()            # Returns current frame, advances
spinner.reset()              # Reset to first frame
```

**Built-in frame sequences**: `BRAILLE` (alias: `DOTS`), `LINE`, `ARROW`

**Thread-safe**: Yes (internal lock on frame index)

---

## `stream_to_terminal(template, context, *, delay=0.02, file=None)`

Progressive chunk-by-chunk rendering with typewriter effect.

**Guaranteed behavior**:
- Uses `template.render_stream()` for chunked output
- Skips delay when output is piped (non-TTY)

---

## Template Globals

Available in all templates rendered with `autoescape="terminal"`:

| Global | Type | Description |
|--------|------|-------------|
| `columns` | `int` | Terminal width |
| `rows` | `int` | Terminal height |
| `tty` | `bool` | Is stdout a TTY |
| `icons` | `IconSet` | Unicode/ASCII icon proxy |
| `box` | `BoxSet` | Box-drawing character sets |
| `hr(w, char, title)` | `Callable` | Horizontal rule generator |

---

## Terminal Filters

### Color & Decoration
`red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`, `black`, `bright_red`, `bright_green`, `bright_yellow`, `bright_blue`, `bright_magenta`, `bright_cyan`, `bold`, `dim`, `italic`, `underline`, `blink`, `inverse`, `strike`, `fg(color)`, `bg(color)`

### Layout
`pad(width, align, fill)`, `truncate(length)`, `wrap(width)`, `wordwrap(width)`, `center(width)`

### Data
`badge(value, icon, color)`, `bar(value, width, show_pct)`, `kv(label, value, width, sep, fill)`, `table(data, headers, border, align, max_width)`, `tree(data, indent)`, `diff(old, new, context)`

**All filters**:
- ANSI-aware (respect invisible escape code width)
- Return `Styled` instances (bypass sanitization)
- Degrade gracefully when color is disabled

---

## Built-in Component Templates

Import via `{% from "components.txt" import ... %}`:

| Component | Purpose |
|-----------|---------|
| `row(content, width, border)` | Bordered line |
| `cols(cells, sep)` | Multi-column layout |
| `rule(width, title, char)` | Horizontal rule |
| `box(title, width, style, padding)` | Bordered box |
| `panel(title, width, style, padding)` | Panel with inline title |
| `header(width, style)` | Top banner |
| `footer(width, style)` | Bottom banner |
| `connector(indent)` | Vertical pipe between panels |
| `banner(text, width, char, padding)` | Centered banner |
| `two_col(left_width, sep)` | Two-column split |
| `stack(threshold, sep)` | Responsive stacking |
| `dl(items, label_width, sep, color)` | Definition list |

**Box styles**: `"round"`, `"light"`, `"heavy"`, `"double"`, `"ascii"`

---

## Color Depth Fallback

Kida detects terminal capabilities and falls back gracefully:

```
truecolor → 256-color → basic (8-color) → none
```

Detection order:
1. Explicit override via `terminal_color=` parameter
2. `NO_COLOR` env var → forces `"none"`
3. `FORCE_COLOR` env var → forces `"truecolor"`
4. `COLORTERM=truecolor` → `"truecolor"`
5. `TERM` value → heuristic mapping
6. Default → `"basic"`

---

## Thread Safety Guarantees

All terminal APIs are safe for Python 3.14t free-threading (`PYTHON_GIL=0`):

- `terminal_env()` returns an immutable-after-construction Environment
- `LiveRenderer.update()` uses an internal lock for safe concurrent updates
- `Spinner()` uses an internal lock for frame advancement
- All filters are pure functions returning new `Styled` instances
- Template globals (`columns`, `rows`, etc.) are read-only after construction

---

## Versioning Policy

- **Patch releases** (0.3.x): Bug fixes only. No API changes.
- **Minor releases** (0.x.0): New filters/components may be added. Existing APIs unchanged.
- **Major releases** (x.0.0): May contain breaking changes (with migration guide).

This contract applies to all APIs listed above starting from kida v0.3.0.
