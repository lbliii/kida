# Milo

**Template-driven terminal applications for free-threaded Python.**

Milo is a CLI application framework that separates what your tool *looks like* (templates) from what it *does* (Python). Built on [kida](https://github.com/lbliii/kida) for rendering, it brings the template-engine model to terminal applications — interactive forms, animated dashboards, themed help screens — with one dependency and zero compromise.

```
pip install milo
```

```
milo → kida → nothing
```

---

## Why

CLI tools have a rendering problem. The options today are:

- **argparse / Click / Typer** — good at parsing arguments, bad at output. You end up fighting `HelpFormatter` or scattering `print()` calls everywhere. The output is an afterthought.
- **Rich** — good at making things pretty, but every style decision lives in Python code. `rich.print("[bold red]Error[/]")` is markup-in-code. You can't swap the look without rewriting the logic.
- **Textual** — powerful TUI framework, but it's a widget system with a CSS engine. Overkill for a deploy script that needs a progress bar and a status table.

The result: most CLI tools have inconsistent, hard-to-customize output. And the ones that look good took weeks of styling work that's tangled into the business logic.

Milo fixes this by applying a principle the web figured out twenty years ago: **templates render, code computes.**

Your CLI's entire visual layer is a `.txt` template file. Swap the template, change the look. The Python code is a pure function from state to data. The framework connects them.

---

## Principles

### Templates are the UI

Every screen, form, help page, and error message renders through a kida template. No `print()` calls, no inline ANSI codes, no style objects constructed in Python. The template is the single source of truth for how your CLI looks.

```
{# status.txt #}
{% from "components.txt" import panel, header %}

{% call header(width=w) %}
{{ icons.gear | fg("#00ccff") }} {{ app | bold }} {{ version | dim }}
{% endcall %}

{% for svc in services %}
{% call panel(title=svc.name, width=w) %}
  {{ svc.status | badge | pad(12) }} {{ svc.latency | dim }}
{% endcall %}
{% endfor %}
```

### Frozen state, pure transitions

Application state is a frozen dataclass. State transitions are pure functions that take old state + action and return new state. No mutable objects, no shared state, no locks.

```python
@dataclass(frozen=True, slots=True)
class AppState:
    services: tuple[Service, ...] = ()
    selected: int = 0
    loading: bool = True

def reducer(state: AppState, action: Action) -> AppState:
    match action.type:
        case "loaded":
            return AppState(services=action.payload, selected=0, loading=False)
        case "select_next":
            return AppState(services=state.services, selected=state.selected + 1)
```

This is the Elm architecture applied to terminal apps. It's simple, testable, and inherently thread-safe for Python 3.14t's free-threading model.

### One dependency

Milo depends on kida. Kida depends on nothing. The entire stack — argument parsing, interactive input, animated rendering, color fallback, responsive layout — installs one package.

Compare:

| Stack | Dependencies |
|---|---|
| Click + Rich + Inquirer | 8+ packages, native extensions |
| Typer + Rich | 6+ packages |
| **Milo + argparse** | **1 package (kida), pure Python** |

### Free-threading native

Every data structure is frozen. State is replaced atomically, never mutated. Reads require no synchronization. Milo doesn't bolt thread-safety onto a mutable architecture — it eliminates the problem structurally.

---

## Architecture

```
┌─────────────────────────────────────────┐
│              Your CLI app               │
├──────────┬──────────┬───────────────────┤
│ argparse │   milo   │  kida templates   │
│ (stdlib) │  (input, │  (rendering,      │
│          │   state, │   components,     │
│          │   forms) │   live updates)   │
└──────────┴──────────┴───────────────────┘
```

Milo owns three things:

1. **Input** — raw keypress reading, escape sequence parsing, terminal raw mode
2. **State** — frozen dataclass state management with reducers
3. **Lifecycle** — the event loop that connects input → state → render

Kida owns rendering. Argparse owns argument parsing. Milo is the bridge.

---

## What it looks like

### A simple status command

```python
import argparse
from milo import run
from kida.terminal import terminal_env

parser = argparse.ArgumentParser()
parser.add_argument("--env", default="prod")
args = parser.parse_args()

env = terminal_env()
tpl = env.get_template("status.txt")
print(tpl.render(services=get_services(args.env)))
```

No framework overhead. Kida renders, argparse parses, your code is three lines.

### An interactive form

```python
from milo import form, TextField, SelectField, ConfirmField

config = form(
    TextField("name", "Project name"),
    SelectField("lang", "Language", choices=("Python", "Go", "Rust")),
    SelectField("license", "License", choices=("MIT", "Apache-2.0", "GPL-3.0")),
    ConfirmField("ci", "Set up CI pipeline?"),
)

# config = {"name": "myapp", "lang": "Python", "license": "MIT", "ci": True}
```

The form renders through a kida template. Pass `template="my_form.txt"` to completely customize the look.

### An animated deploy pipeline

```python
from milo import App, Action
from kida.terminal import terminal_env

env = terminal_env()
tpl = env.get_template("deploy.txt")

app = App(template=tpl, reducer=deploy_reducer, initial_state=DeployState())
final = app.run()
```

The template uses `{{ spinner() }}` for animation, `{{ stage.status | badge }}` for status icons, `{{ progress | bar }}` for progress bars. The reducer handles state transitions. The `App` event loop connects them.

### Themed help screens

```python
from milo import HelpRenderer

help_renderer = HelpRenderer(template="help.txt")
parser = argparse.ArgumentParser(formatter_class=help_renderer)
```

Your `--help` output renders through a kida template. Same panels, same colors, same responsive layout as the rest of your CLI.

---

## Modules

| Module | Purpose | Key types |
|---|---|---|
| `milo.app` | Event loop, lifecycle | `App`, `Screen`, `Middleware` |
| `milo.state` | State management | `Store`, `Reducer`, `Action`, `Effect` |
| `milo.input` | Terminal input | `KeyReader`, `Key` |
| `milo.form` | Interactive forms | `TextField`, `SelectField`, `ConfirmField`, `form()` |
| `milo.help` | Help screen rendering | `HelpRenderer` |
| `milo.components` | Kida templates | Field widgets, progress indicators |

---

## The b-stack

Milo is part of a vertically integrated toolkit for terminal applications:

| Layer | Library | Role |
|---|---|---|
| Input & lifecycle | **milo** | Forms, state, event loop |
| Template rendering | **kida** | ANSI-aware templates, components, live rendering |
| Markdown rendering | **patitias** | Parse and render markdown in the terminal |
| Syntax highlighting | **rosettes** | Highlight code blocks, error snippets, diffs |
| Argument parsing | **argparse** | stdlib, zero-dep |

Every library in the stack is:
- Pure Python, zero native extensions
- Free-threading ready (`_Py_mod_gil = 0`)
- Built on frozen dataclasses with slots
- Protocol-driven for extensibility
- MIT licensed

The stack has **one** installable dependency chain: `milo → kida`. Patitias and rosettes are optional — kida integrates them when present, ignores them when not.

---

## Design details

### State management

Milo uses the Elm architecture: unidirectional data flow with immutable state.

```
Event → Action → Reducer → New State → Render
  ↑                                        │
  └────────────────────────────────────────┘
```

State is always a frozen dataclass. The reducer is a pure function. Side effects (HTTP calls, file I/O) run in `Effect` handlers that dispatch actions when complete. The render function is a kida template.

This makes every state transition:
- **Testable** — call the reducer with state + action, assert the result
- **Replayable** — log actions, replay them to reproduce bugs
- **Thread-safe** — frozen state means zero shared mutable data

### Input handling

The `KeyReader` enters terminal raw mode and yields `Key` objects:

```python
@dataclass(frozen=True, slots=True)
class Key:
    char: str          # printable character or ""
    name: str = ""     # "enter", "up", "ctrl+c", "backspace"
    ctrl: bool = False
    alt: bool = False
```

Escape sequences (arrow keys, function keys, etc.) are parsed via a frozen lookup table. Platform differences (Unix termios vs Windows msvcrt) are isolated in the input module.

### Rendering

Milo doesn't render anything itself. It calls kida's `LiveRenderer`:

```python
# Inside App.run()
with LiveRenderer(self.template) as live:
    for event in self._reader:
        new_state = self.reducer(self._state, to_action(event))
        self._state = new_state          # atomic swap
        live.update(**asdict(new_state))  # kida re-renders
```

This means every kida feature — color depth fallback, responsive layout, ANSI-safe sanitization, streaming, components — works in milo automatically.

### Graceful degradation

| Condition | Behavior |
|---|---|
| Not a TTY (piped, CI) | Forms fall back to line-buffered `input()`, output has no animation |
| No color support | Templates render plain text via kida's `color="none"` mode |
| Narrow terminal | `stack()` components switch from side-by-side to stacked |
| Windows (legacy cmd) | Best-effort ANSI via VT processing, ASCII box-drawing fallback |

---

## What milo is not

- **Not a TUI framework.** No scrollable widgets, no mouse input, no CSS layout engine. If you need a terminal IDE, use Textual.
- **Not an argument parser.** Use argparse, or Click, or whatever you want. Milo doesn't care where the data comes from.
- **Not a replacement for Rich.** Rich is a rendering library. Kida is a rendering library. Use whichever you prefer. Milo is the application layer on top.

Milo is for people who want their CLI to look great, accept interactive input, and stay under 100 lines of code. Templates handle the complexity. Your code stays clean.

---

## Status

Milo is in design phase. Kida's terminal rendering mode — which milo builds on — is implemented and working:

- ANSI-aware width, padding, truncation
- Color depth detection and fallback (truecolor → 256 → basic → none)
- Built-in components (panel, header, footer, cols, stack, etc.)
- LiveRenderer with in-place re-rendering and spinners
- Progressive streaming output
- CLI render command (`kida render template.txt --data context.json`)
- Responsive layout (side-by-side → stacked based on terminal width)

The foundation is solid. Milo adds the input layer, state management, and application lifecycle on top.

---

## License

MIT

---

*Milo is a [b-stack](https://github.com/lbliii) project.*
