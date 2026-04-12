# Milo

**Template-driven terminal applications for free-threaded Python.**

Milo is a CLI application framework that separates what your tool *looks like* (templates) from what it *does* (Python). Built on [kida](https://github.com/lbliii/kida) for rendering, it brings the template-engine model to terminal applications — interactive forms, animated dashboards, themed help screens, saga-driven pipelines, and MCP server mode — with one dependency and zero compromise.

**v0.2.1** — shipped 2026-04-12

```
pip install milo
```

```
milo -> kida -> nothing
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

And with MCP server mode, the same CLI that humans use becomes an API that AI agents can discover and call — no separate integration layer.

---

## What Milo Does

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

### Saga orchestration

Side effects — HTTP calls, file I/O, timed delays, concurrent operations — run through a saga system inspired by Redux-Saga. Sagas are generator functions that yield effect descriptors. The saga runner executes them, keeping your business logic pure and testable.

```python
from milo.state import Fork, Call, Delay, Put, Select, Race, All, Retry, TryCall

def deploy_saga(env: str):
    # Run pre-checks and provisioning concurrently
    pre, infra = yield All([
        Call(run_prechecks, env),
        Call(provision_infra, env),
    ])
    yield Put(Action("infra_ready", payload=infra))

    # Deploy services with retry
    for svc in infra.services:
        yield Fork(deploy_service_saga, svc)

    # Wait for all deploys, with a timeout
    result = yield Race(
        done=All([Take(f"deploy_done:{svc.name}") for svc in infra.services]),
        timeout=Delay(300),
    )
    if "timeout" in result:
        yield Put(Action("deploy_timeout"))
    else:
        yield Put(Action("deploy_complete"))
```

Available saga effects: `Fork`, `Call`, `Delay`, `Put`, `Select`, `Race`, `All`, `Retry`, `Take`, `TakeEvery`, `TakeLatest`, `Timeout`, `TryCall`, `Batch`, `Sequence`, `Debounce`.

### One dependency

Milo depends on kida. Kida depends on nothing. The entire stack — CLI definition, argument parsing, interactive input, saga orchestration, pipeline phases, MCP server, animated rendering, color fallback, responsive layout — installs one package.

| Stack | Dependencies |
|---|---|
| Click + Rich + Inquirer | 8+ packages, native extensions |
| Typer + Rich | 6+ packages |
| **Milo** | **1 package (kida), pure Python** |

### Free-threading native

Every data structure is frozen. State is replaced atomically, never mutated. Reads require no synchronization. Milo doesn't bolt thread-safety onto a mutable architecture — it eliminates the problem structurally.

---

## Architecture

```
+-------------------------------------------------------+
|                    Your CLI app                        |
+-------------------------------------------------------+
|  CLI / Commands / Groups     |  kida templates        |
|  (definition, routing)       |  (rendering,           |
|                              |   components,          |
|                              |   live updates)        |
+------------------------------+------------------------+
|         milo core                                     |
|  +----------+  +-----------+  +--------------------+  |
|  | App      |  | Store     |  | Pipeline           |  |
|  | Flow     |  | Sagas     |  | Phase / PhasePolicy|  |
|  | Screen   |  | Reducers  |  |                    |  |
|  +----------+  +-----------+  +--------------------+  |
|  +----------+  +-----------+  +--------------------+  |
|  | Input    |  | Form      |  | MCP Server         |  |
|  | KeyReader|  | Fields    |  | JSON-RPC / Gateway |  |
|  +----------+  +-----------+  +--------------------+  |
|  +----------+  +-----------+  +--------------------+  |
|  | Plugins  |  | Middleware|  | Dev / Hot Reload   |  |
|  | Themes   |  | Streaming |  | Session Recording  |  |
|  +----------+  +-----------+  +--------------------+  |
+-------------------------------------------------------+
```

Milo owns:

1. **CLI definition** — `CLI(name, description)`, `@cli.command`, `cli.group`, command routing
2. **Input** — raw keypress reading, escape sequence parsing, terminal raw mode
3. **State + Sagas** — frozen dataclass state, reducers, full saga effect system
4. **Composable reducers** — `@quit_on()`, `@with_cursor()`, `@with_confirm()` decorators
5. **Forms** — interactive multi-field forms with template-driven rendering
6. **Flows** — multi-screen apps via `Flow` and the `>>` operator
7. **Pipeline orchestration** — `Phase`, `PhasePolicy`, failure handling
8. **MCP server mode** — `--mcp` flag exposes CLI commands as JSON-RPC tools
9. **AI discovery** — `--llms-txt` generates machine-readable tool descriptions
10. **Gateway** — register multiple CLIs behind a single MCP endpoint
11. **Plugins + Middleware** — extension points for the command pipeline
12. **Hot reload** — `milo dev` watches templates and reloads on change
13. **Session recording** — JSONL capture and replay for debugging and CI
14. **Themes + Completions** — color schemes and shell tab completion

Kida owns rendering. Your code owns business logic. Milo is the bridge.

---

## What It Looks Like

### Defining a CLI

```python
from milo import CLI

cli = CLI("deploy", "Ship services to production")

@cli.command
def status(env: str = "prod"):
    """Show service status."""
    from kida.terminal import terminal_env
    env_t = terminal_env()
    tpl = env_t.get_template("status.txt")
    print(tpl.render(services=get_services(env)))

@cli.command
def push(env: str = "prod", dry_run: bool = False):
    """Deploy all services."""
    app = App(template=tpl, reducer=deploy_reducer, initial_state=DeployState(env=env))
    app.saga(deploy_saga, env)
    final = app.run()

cli.run()
```

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

### A saga-driven deploy pipeline

```python
from milo import App, Action
from milo.state import Fork, Call, Put, All, Race, Delay, Retry
from kida.terminal import terminal_env

env = terminal_env()
tpl = env.get_template("deploy.txt")

def deploy_reducer(state, action):
    match action.type:
        case "stage_started":
            return state.with_stage(action.payload, status="running")
        case "stage_done":
            return state.with_stage(action.payload, status="done")
        case "deploy_complete":
            return state.with_done()

def deploy_saga(target_env):
    yield Put(Action("stage_started", "preflight"))
    yield Call(run_preflight, target_env)
    yield Put(Action("stage_done", "preflight"))

    yield Put(Action("stage_started", "deploy"))
    results = yield All([
        Retry(Call(deploy_service, svc), max_retries=3)
        for svc in get_services(target_env)
    ])
    yield Put(Action("stage_done", "deploy"))
    yield Put(Action("deploy_complete"))

app = App(template=tpl, reducer=deploy_reducer, initial_state=DeployState())
app.saga(deploy_saga, "prod")
final = app.run()
```

The template uses `{{ spinner() }}` for animation, `{{ stage.status | badge }}` for status icons, `{{ progress | bar }}` for progress bars. The saga handles orchestration. The reducer handles state transitions. The `App` event loop connects them.

### MCP server mode

Any Milo CLI can serve its commands as tools for AI agents over JSON-RPC:

```bash
# Start as MCP server (stdio transport)
deploy --mcp

# Generate AI-readable tool descriptions
deploy --llms-txt
```

```python
cli = CLI("deploy", "Ship services to production")

@cli.command
def status(env: str = "prod"):
    """Show service status across all regions."""
    ...

@cli.command
def push(env: str = "prod", service: str | None = None):
    """Deploy a service (or all services) to the target environment."""
    ...

# When run with --mcp, each @cli.command becomes a JSON-RPC tool
# that AI agents can discover and invoke.
cli.run()
```

The `--mcp` flag uses `milo.mcp` and `milo._mcp_router` to expose commands via JSON-RPC. The `--llms-txt` flag uses `milo.llms` to generate machine-readable descriptions. The gateway (`milo.gateway`) lets you register multiple CLIs behind a single MCP endpoint.

### Multi-screen flows

```python
from milo import Flow, FlowScreen

setup = FlowScreen("setup", template="setup.txt", reducer=setup_reducer)
confirm = FlowScreen("confirm", template="confirm.txt", reducer=confirm_reducer)
deploy = FlowScreen("deploy", template="deploy.txt", reducer=deploy_reducer)

flow = setup >> confirm >> deploy
result = flow.run()
```

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
| `milo.cli` | CLI definition | `CLI`, `@cli.command`, `@cli.group` |
| `milo.commands` | Command routing | Command dispatch, lazy loading |
| `milo.groups` | Command groups | Nested subcommands |
| `milo.app` | Event loop, lifecycle | `App`, `Screen` |
| `milo.state` | State + saga runner | `Store`, `Reducer`, `Action`, `Fork`, `Call`, `Delay`, `Put`, `Select`, `Race`, `All`, `Retry`, `Take*`, `Batch`, `Sequence`, `Debounce` |
| `milo.reducers` | Composable reducers | `@quit_on()`, `@with_cursor()`, `@with_confirm()` |
| `milo.flow` | Multi-screen flows | `FlowScreen`, `Flow`, `>>` operator |
| `milo.form` | Interactive forms | `TextField`, `SelectField`, `ConfirmField`, `form()` |
| `milo.input` | Terminal input | `KeyReader`, `Key` |
| `milo.pipeline` | Pipeline orchestration | `Phase`, `PhasePolicy` |
| `milo.mcp` | MCP server mode | `--mcp` flag, JSON-RPC |
| `milo.llms` | AI discovery | `--llms-txt` generation |
| `milo.gateway` | Multi-CLI gateway | CLI registration, unified MCP |
| `milo.middleware` | Middleware pipeline | Request/response hooks |
| `milo.plugins` | Plugin system | Extension loading |
| `milo.streaming` | Streaming output | Progress, generator consumption |
| `milo.dev` | Hot reload | `milo dev` file watcher |
| `milo.help` | Help rendering | `HelpRenderer` |
| `milo.theme` | Theming | Color schemes, styles |
| `milo.completions` | CLI completions | Tab completion |
| `milo.testing` | Test utilities | Test helpers |
| `milo.config` | Configuration | Config loading |
| `milo.observability` | Logging/tracing | Structured logging |

---

## The b-stack

Milo is part of a vertically integrated toolkit for terminal applications:

| Layer | Library | Role |
|---|---|---|
| CLI framework | **milo** | CLI definition, forms, state/sagas, pipelines, MCP server, flows |
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

The stack has **one** installable dependency chain: `milo -> kida`. Patitias and rosettes are optional — kida integrates them when present, ignores them when not.

---

## Design Details

### State management + sagas

Milo uses the Elm architecture: unidirectional data flow with immutable state.

```
Event -> Action -> Reducer -> New State -> Render
  ^                                          |
  +------------------------------------------+
```

State is always a frozen dataclass. The reducer is a pure function. Side effects run through the saga system — generator functions that yield declarative effect descriptors:

| Effect | Purpose |
|---|---|
| `Call(fn, *args)` | Call a function and return its result |
| `Fork(fn, *args)` | Spawn a concurrent saga (non-blocking) |
| `Put(action)` | Dispatch an action to the store |
| `Select(selector)` | Read current state |
| `Delay(seconds)` | Wait for a duration |
| `Take(pattern)` | Wait for a specific action |
| `TakeEvery(pattern, saga)` | Run saga on every matching action |
| `TakeLatest(pattern, saga)` | Cancel previous, run saga on latest match |
| `Race(effects)` | Run effects concurrently, return first to finish |
| `All(effects)` | Run effects concurrently, wait for all |
| `Retry(effect, max_retries)` | Retry an effect on failure |
| `TryCall(fn, *args)` | Call with error handling |
| `Timeout(effect, seconds)` | Fail if effect exceeds duration |
| `Batch(actions)` | Dispatch multiple actions atomically |
| `Sequence(effects)` | Run effects in order |
| `Debounce(seconds, effect)` | Debounce rapid-fire effects |

This makes every state transition:
- **Testable** — call the reducer with state + action, assert the result; test sagas by stepping through yields
- **Replayable** — log actions, replay them to reproduce bugs
- **Thread-safe** — frozen state means zero shared mutable data

### Composable reducers

Reducer decorators eliminate boilerplate for common patterns:

```python
from milo.reducers import quit_on, with_cursor, with_confirm

@quit_on("q", "ctrl+c")
@with_cursor(items_key="services")
@with_confirm(action="deploy")
def deploy_reducer(state, action):
    match action.type:
        case "stage_done":
            return state.with_stage(action.payload, status="done")
```

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

### Pipeline orchestration

For multi-phase operations (build, test, deploy), the pipeline module provides structured orchestration:

```python
from milo.pipeline import Phase, PhasePolicy

phases = [
    Phase("preflight", run_preflight, policy=PhasePolicy.FAIL_FAST),
    Phase("build", run_build, policy=PhasePolicy.FAIL_FAST),
    Phase("deploy", run_deploy, policy=PhasePolicy.RETRY),
    Phase("verify", run_verify, policy=PhasePolicy.CONTINUE_ON_FAILURE),
]
```

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

## What Milo Is Not

- **Not a TUI framework.** No scrollable widgets, no mouse input, no CSS layout engine. If you need a terminal IDE, use Textual.
- **Not an argument parser.** Use argparse, or Click, or whatever you want. Milo doesn't care where the data comes from.
- **Not a replacement for Rich.** Rich is a rendering library. Kida is a rendering library. Use whichever you prefer. Milo is the application layer on top.

Milo is for people who want their CLI to look great, accept interactive input, orchestrate complex workflows, and optionally serve as an MCP tool for AI agents — all while staying under 100 lines of code. Templates handle the complexity. Your code stays clean.

---

## Status

Milo v0.2.1 shipped on 2026-04-12. Current capabilities:

- Full saga system (Fork, Call, Delay, Put, Select, Race, All, Retry, Take/TakeEvery/TakeLatest, Timeout, TryCall, Batch, Sequence, Debounce)
- App + Store + Flow (multi-screen via `>>` operator) + form()
- CLI definition with `CLI(name, description)`, `@cli.command`, `cli.group`
- MCP server mode (`--mcp` flag, JSON-RPC transport)
- AI discovery (`--llms-txt`)
- Pipeline orchestration (Phase, PhasePolicy)
- Composable reducer decorators (@quit_on, @with_cursor, @with_confirm)
- Hot reload (`milo dev`)
- Gateway (multi-CLI registration)
- Plugin system, middleware, themes, completions
- Session recording/replay

Kida's terminal rendering mode — which Milo builds on — is implemented and working:

- ANSI-aware width, padding, truncation
- Color depth detection and fallback (truecolor -> 256 -> basic -> none)
- Built-in components (panel, header, footer, cols, stack, etc.)
- LiveRenderer with in-place re-rendering and spinners
- Progressive streaming output
- CLI render command (`kida render template.txt --data context.json`)
- Responsive layout (side-by-side -> stacked based on terminal width)

---

## License

MIT

---

*Milo is a [b-stack](https://github.com/lbliii) project.*
