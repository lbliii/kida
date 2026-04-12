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
icon: terminal
---

# Terminal Rendering

Kida templates can render to the terminal with full ANSI color support, responsive layouts, and real-time animation. The same template language you use for HTML works for CLI tools — with a dedicated set of filters and components designed for terminal output.

## Prerequisites

- Python 3.14+
- Kida installed
- A terminal that supports ANSI escape codes (almost all modern terminals)

## Your First Terminal Render

The fastest way to get colored terminal output is the `terminal_env()` factory. It returns a standard Kida `Environment` pre-configured with `autoescape="terminal"` and all terminal filters registered.

```python
from kida.terminal import terminal_env

env = terminal_env()
tpl = env.from_string('{{ "Hello" | bold | cyan }} from Kida!')
print(tpl.render())
```

Run this and you will see "Hello" printed in bold cyan, followed by unstyled text. The `bold`, `cyan`, and other style filters wrap their input in the appropriate ANSI escape sequences. When `autoescape="terminal"` is active, Kida handles the reset codes automatically so styles do not bleed into surrounding text.

You can also use the CLI to render a template file directly. Save a template as `greeting.txt`:

```kida
{{ name | green | bold }}: {{ message | dim }}
```

Then render it from the command line:

```bash
kida render greeting.txt --mode terminal -v name=World -v message="Welcome to Kida"
```

The `--mode terminal` flag tells the CLI to use the terminal rendering environment. You can pass variables with `-v key=value`.

The core style filters available out of the box are: `bold`, `dim`, `italic`, `underline`, `cyan`, `green`, `red`, `yellow`, and `bright_cyan`. These compose naturally — chain them in any order and Kida merges the escape codes into a single sequence.

## Colors and Graceful Degradation

Terminals vary widely in their color support. Kida recognizes four color depth levels and degrades gracefully when a template uses colors that the terminal cannot display.

| Level | Description | Example |
|-------|-------------|---------|
| `none` | No color output | CI logs, piped output |
| `basic` | 16 ANSI colors | Older terminals |
| `256` | 256-color palette | Most modern terminals |
| `truecolor` | 24-bit RGB | iTerm2, Windows Terminal, Kitty |

By default, `terminal_env()` auto-detects the terminal's color depth. You can override this explicitly:

```python
from kida.terminal import terminal_env

# Force basic 16-color mode
env = terminal_env(terminal_color="basic")
tpl = env.from_string('{{ status | fg("#ff6600") | bold }}')
print(tpl.render(status="DEGRADED"))
```

When this template runs with `terminal_color="basic"`, the hex color `#ff6600` is automatically mapped to the nearest basic ANSI color (yellow). No error, no missing output — the template still works, just with reduced fidelity.

For full control over custom colors, use the `fg()` and `bg()` filters. They accept both named colors and hex values:

```python
env = terminal_env(terminal_color="truecolor")
tpl = env.from_string("""
{{ title | fg("#00d4aa") | bold }}
{{ subtitle | fg("yellow") | bg("#1a1a2e") }}
""")
print(tpl.render(title="Deploy Report", subtitle="v2.1.0 — production"))
```

Kida also respects the `NO_COLOR` and `FORCE_COLOR` environment variables. When `NO_COLOR` is set, all color output is suppressed regardless of the `terminal_color` setting. When `FORCE_COLOR` is set, auto-detection is skipped and colors are always emitted. This follows the community convention at [no-color.org](https://no-color.org).

:::note[Testing Tip]
Use `kida render template.txt --mode terminal --color none` to see exactly what your template renders without any ANSI codes. This is useful for verifying layout and content before adding color.
:::

To test how your template looks at different color depths from the CLI:

```bash
# See output with only basic colors
kida render dashboard.txt --mode terminal --color basic

# See output with no colors at all
kida render dashboard.txt --mode terminal --color none
```

## Layout and Built-in Components

Terminal output benefits from structure — headers, dividers, aligned key-value pairs, and status indicators. Kida provides filters and built-in globals for all of these.

The `hr()` global renders a horizontal rule. The `icons` object provides common Unicode glyphs. The `pad()` filter pads a value to a fixed width, and `kv()` formats label-value pairs with aligned separators:

```python
from kida.terminal import terminal_env

env = terminal_env(terminal_width=80)
tpl = env.from_string("""
{{ "Service Status" | bold | underline }}
{{ hr(80) }}
{% for svc in services %}
{{ svc.name | pad(20) | bold }} {{ svc.status | badge() }}  {{ svc.latency | kv("latency", sep=": ") }}
{% end %}
{{ hr(80) }}
{{ summary | dim }}
""")

services = [
    {"name": "api-gateway", "status": "healthy", "latency": "12ms"},
    {"name": "auth-service", "status": "healthy", "latency": "8ms"},
    {"name": "worker-pool", "status": "degraded", "latency": "340ms"},
]
print(tpl.render(services=services, summary="3 services checked"))
```

The `badge()` filter wraps a value in a colored pill-style label — "healthy" renders in green, "degraded" in yellow, "down" in red. The `bar()` filter draws a progress bar of a given width, useful for displaying percentages or resource usage:

```kida
{{ "CPU" | pad(8) }} {{ cpu_pct | bar(40) }} {{ cpu_pct }}%
{{ "Memory" | pad(8) }} {{ mem_pct | bar(40) }} {{ mem_pct }}%
```

The `terminal_width` parameter on `terminal_env()` controls the default width used by `hr()` and other width-aware components. If not specified, Kida reads the actual terminal width at render time.

The `table()` filter formats a list of dictionaries as an aligned table with headers. The `tree()` filter renders nested data as a tree with box-drawing characters. And `syntax()` applies syntax highlighting to code strings:

```kida
{{ "Dependencies" | bold }}
{{ deps | tree() }}

{{ "Recent Queries" | bold }}
{{ queries | table() }}
```

Icons are available through the `icons` global: `icons.check` (checkmark), `icons.cross` (X mark), `icons.warn` (warning triangle), and `icons.gear` (gear). Use `box.round` for rounded box-drawing characters. These degrade to ASCII equivalents when the terminal does not support Unicode.

## LiveRenderer — Animated Output

For CLI tools that run multi-step operations, static output is not enough. `LiveRenderer` re-renders a template in place, replacing the previous output on each update. This is how you build progress displays, deploy trackers, and monitoring dashboards.

`LiveRenderer` works as a context manager. Call `update()` to push new data and trigger a re-render:

```python
import time
from kida.terminal import LiveRenderer, terminal_env

env = terminal_env()
tpl = env.from_string("""
{{ "Deploy Progress" | bold | cyan }}
{{ hr(60) }}
{% for step in steps %}
{% if step.status == "done" %}
  {{ icons.check | green }} {{ step.name | pad(30) }} {{ step.duration }}
{% elif step.status == "running" %}
  {{ spinner() }} {{ step.name | pad(30) | yellow }} ...
{% else %}
  {{ "  " }} {{ step.name | pad(30) | dim }}
{% end %}
{% end %}
{{ hr(60) }}
{{ elapsed | dim }}
""")

steps = [
    {"name": "Pull image", "status": "pending", "duration": ""},
    {"name": "Run migrations", "status": "pending", "duration": ""},
    {"name": "Health check", "status": "pending", "duration": ""},
    {"name": "Switch traffic", "status": "pending", "duration": ""},
]

with LiveRenderer(tpl, refresh_rate=0.1) as live:
    for i, step in enumerate(steps):
        steps[i]["status"] = "running"
        live.update(steps=steps, elapsed=f"{i * 2}s elapsed")

        time.sleep(2)  # Simulate work

        steps[i]["status"] = "done"
        steps[i]["duration"] = "2.0s"
        live.update(steps=steps, elapsed=f"{(i + 1) * 2}s elapsed")

print("Deploy complete!")
```

The `LiveRenderer` constructor accepts several options:

- `refresh_rate` — minimum seconds between screen updates (default `0.1`). Prevents flickering when `update()` is called rapidly.
- `file` — output file object (default `sys.stderr`). Useful for redirecting live output.
- `transient` — if `True`, the live display is cleared when the context manager exits. Use this for progress indicators that should disappear when done.

The `spinner()` global produces an animated spinner character that cycles on each re-render. It works automatically inside `LiveRenderer` — no extra threading needed.

For operations where you want continuous animation without explicit `update()` calls, use `start_auto()` and `stop_auto()`:

```python
with LiveRenderer(tpl) as live:
    live.start_auto(status="Connecting...", progress=0)
    # Spinner animates while we wait
    result = long_running_operation()
    live.stop_auto()
    live.update(status="Complete", progress=100, result=result)
```

`LiveRenderer` is thread-safe. Each call to `update()` atomically swaps the render context, so background threads can push updates without locks. The renderer freezes the context snapshot before each render pass to avoid tearing.

## Optimize with static_context

When building CLI tools, some template values are known at startup and never change — the application name, version string, feature flags, environment label. Passing these through `static_context` lets Kida fold them at compile time, eliminating branches and lookups at render time.

```python
from kida.terminal import terminal_env

env = terminal_env()

TEMPLATE = """
{{ app_name | bold | cyan }} {{ version | dim }}
{{ hr(60) }}
{% if debug %}
{{ "DEBUG MODE" | bold | red }}
{{ hr(60) }}
{% end %}
{% for svc in services %}
  {{ svc.name | pad(20) }} {{ svc.status | badge() }}
{% end %}
"""

# Values known at app startup — fold at compile time
static = {"app_name": "deployer", "version": "2.1.0", "debug": False}

tpl = env.from_string(TEMPLATE, name="dashboard", static_context=static)

# Only pass dynamic data at render time
print(tpl.render(services=[
    {"name": "api", "status": "healthy"},
    {"name": "worker", "status": "degraded"},
]))
```

:::note[How it works]
With `debug: False` in `static_context`, the entire `{% if debug %}` block is removed from the compiled template. Zero runtime cost for that branch — it does not exist in the compiled AST.
:::

Note that `static_context` is only available on `env.from_string()`, not on `env.get_template()`. This is intentional — file-loaded templates are cached globally, but static context specializes a template for particular values.

Use the `--explain` flag to inspect what the compiler optimized:

```bash
kida render dashboard.txt --mode terminal --explain
```

The explain output shows the compiled AST and highlights which nodes were constant-folded. This is helpful for verifying that your static values are actually being used by the optimizer.

Good candidates for `static_context`:

- Application name and version
- Environment label (production, staging)
- Feature flags
- Terminal width (if you want a fixed layout)
- Configuration that does not change per render

## Streaming Output

For templates that produce long output — log formatters, report generators, file listings — streaming renders chunks progressively instead of buffering the entire result.

```python
from kida.terminal import terminal_env, stream_to_terminal

env = terminal_env()
tpl = env.from_string("""
{{ "Build Log" | bold | underline }}
{{ hr(60) }}
{% for entry in log_entries %}
{{ entry.timestamp | dim }} {{ entry.level | badge() }} {{ entry.message }}
{% end %}
""")

context = {"log_entries": build_log}
stream_to_terminal(tpl, context, delay=0.02)
```

The `delay` parameter controls the pause between chunks in seconds. Set it to `0` for maximum speed, or increase it for a typewriter effect that is easier to follow visually.

From the CLI, use the `--stream` flag:

```bash
kida render build-log.txt --mode terminal --stream --stream-delay 0.05
```

When should you use streaming versus `LiveRenderer`? Streaming is for output that grows — each line appears and stays. `LiveRenderer` is for output that changes in place — the same region is re-rendered with updated data. Use streaming for logs and reports. Use `LiveRenderer` for dashboards and progress displays.

## Complete Example — Service Dashboard

Here is a full working example that ties together `terminal_env`, `static_context`, `LiveRenderer`, colors, and components. Create the following file structure:

```
my-cli/
  dashboard.py
  templates/
    dashboard.txt
```

`templates/dashboard.txt`:

```kida
{{ app_name | bold | cyan }} {{ version | dim }}  {{ env_label | badge() }}
{{ hr(width) }}

{% for svc in services %}
{% if svc.status == "healthy" %}
  {{ icons.check | green }} {{ svc.name | pad(20) | bold }} {{ svc.latency | kv("latency") }}
{% elif svc.status == "degraded" %}
  {{ icons.warn | yellow }} {{ svc.name | pad(20) | bold }} {{ svc.latency | kv("latency") }}
{% else %}
  {{ icons.cross | red }} {{ svc.name | pad(20) | bold }} {{ svc.latency | kv("latency") }}
{% end %}
{% end %}

{{ hr(width) }}
{{ "CPU" | pad(8) }} {{ cpu | bar(40) }} {{ cpu }}%
{{ "Mem" | pad(8) }} {{ mem | bar(40) }} {{ mem }}%
{{ hr(width) }}
{{ updated_at | dim }}
```

`dashboard.py`:

```python
import time
import random
from kida import FileSystemLoader
from kida.terminal import LiveRenderer, terminal_env

env = terminal_env(loader=FileSystemLoader("templates/"), terminal_width=72)

static = {"app_name": "myapp", "version": "2.1.0", "env_label": "production", "width": 72}
tpl = env.from_string(
    open("templates/dashboard.txt").read(),
    name="dashboard",
    static_context=static,
)

services = [
    {"name": "api-gateway", "status": "healthy", "latency": "12ms"},
    {"name": "auth-service", "status": "healthy", "latency": "8ms"},
    {"name": "search-index", "status": "healthy", "latency": "45ms"},
    {"name": "worker-pool", "status": "healthy", "latency": "120ms"},
]

with LiveRenderer(tpl, refresh_rate=0.5, transient=False) as live:
    for tick in range(30):
        # Simulate changing metrics
        for svc in services:
            latency = random.randint(5, 500)
            svc["latency"] = f"{latency}ms"
            svc["status"] = "healthy" if latency < 200 else "degraded" if latency < 400 else "down"

        live.update(
            services=services,
            cpu=random.randint(10, 95),
            mem=random.randint(30, 85),
            updated_at=f"Updated {tick + 1}s ago",
        )
        time.sleep(1)
```

Run it with `python dashboard.py` and watch the service statuses, latencies, and resource bars update in real time.

## Next Steps

You now have the tools to build rich terminal output with Kida. Here are some directions to explore:

- [[docs/reference/terminal-filters|Terminal Filter Reference]] — full list of terminal filters with examples
- [[docs/reference/terminal-components|Built-in Components]] — panels, headers, columns, and other layout components
- The `--explain` flag for inspecting compiled templates and verifying optimizations
- `examples/terminal_dashboard/` and `examples/terminal_deploy/` in the Kida repository for more patterns
- [Milo](https://github.com/kida-lang/milo) for building fully interactive terminal applications on top of Kida's rendering layer
