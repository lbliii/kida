# RFC: Milo Vision Doc — Diff Against 0.2.1

**Status**: Draft
**Created**: 2026-04-12
**Epic**: `plan/epic-kida-milo-integration.md` — Sprint 0, Task 0.3

---

## Summary

`docs/milo-vision.md` was written during Milo's design phase. Milo 0.2.1 shipped on 2026-04-12. This diff catalogs every claim that's wrong, incomplete, or missing so Sprint 2 (Task 2.2) can do a targeted rewrite.

---

## Line-by-Line Assessment

### Accurate (keep as-is)

| Lines | Content | Notes |
|-------|---------|-------|
| 1–14 | Header, tagline, install, dependency chain | Correct |
| 17–30 | "Why" section — CLI rendering problem | Still valid motivation |
| 35–52 | "Templates are the UI" principle | Correct |
| 75–85 | "One dependency" table | Correct |
| 87–89 | "Free-threading native" principle | Correct |
| 136–149 | Interactive form example | `form()` API is accurate |
| 168–177 | Themed help screens example | `HelpRenderer` exists |
| 236–249 | Input handling (KeyReader, Key dataclass) | Correct |
| 266–273 | Graceful degradation table | Correct |
| 279 | "Not a TUI framework" | Still true |
| 280 | "Not an argument parser" | Still true |
| 281 | "Not a replacement for Rich" | Still true |
| 291–300 | Kida terminal rendering status | Correct |

### Wrong or Stale

| Lines | Current Claim | Reality in 0.2.1 | Fix |
|-------|--------------|-------------------|-----|
| 289 | "Milo is in design phase" | Milo 0.2.1 is shipped (note added but body unchanged) | Rewrite entire Status section |
| 301 | "Milo adds the input layer, state management, and application lifecycle on top" | Milo adds: input, state, **saga orchestration**, **pipeline**, **MCP server**, **plugins**, **middleware**, **flows**, **gateway**, **hot reload**, **session recording**, **themes**, **completions** | Expand to reflect actual scope |
| 153–166 | Deploy example uses simple `App(template, reducer, initial_state)` | 0.2.1 apps typically use saga system for async operations | Rewrite with `Fork`/`Call`/`Put` saga pattern |

### Incomplete (needs expansion)

| Lines | Current Content | What's Missing |
|-------|----------------|----------------|
| 54–71 | "Frozen state, pure transitions" | No mention of saga system at all. The saga runner (`Fork`, `Call`, `Delay`, `Put`, `Select`, `Race`, `All`, `Retry`, `Take`/`TakeEvery`/`TakeLatest`, `Timeout`, `TryCall`, `Batch`, `Sequence`, `Debounce`) is the primary orchestration layer. |
| 95–104 | Architecture diagram (argparse + milo + kida) | Missing: MCP router, plugin system, middleware, gateway, pipeline |
| 106–112 | "Milo owns three things" (input, state, lifecycle) | Milo owns 10+ things: input, state, sagas, pipeline, MCP, plugins, middleware, flows, gateway, hot reload, session recording, themes, completions |
| 219–234 | State management (Elm architecture) | Describes reducer pattern but not saga effects. Line 228 mentions "Effect handlers" in passing but the full saga system deserves its own section. |

### Missing Entirely (new sections needed)

| Feature | Milo Module(s) | Priority |
|---------|----------------|----------|
| **Saga System** | `state.py` (Fork, Call, Delay, Put, Select, Race, All, Retry, Take*, Timeout, TryCall, Batch, Sequence, Debounce) | Critical — this is the #1 new feature |
| **MCP Server Mode** | `mcp.py`, `_mcp_router.py`, `_jsonrpc.py` | High — `--mcp` flag, JSON-RPC protocol, AI agent integration |
| **AI Discovery** | `llms.py` | High — `--llms-txt` flag for AI-readable tool descriptions |
| **Pipeline Orchestration** | `pipeline.py` | High — `Phase`, `PhasePolicy`, failure policies, saga integration |
| **Flow API** | `flow.py` | High — `FlowScreen`, `Flow`, `>>` operator for multi-screen apps |
| **Composable Reducers** | `reducers.py` | Medium — `@quit_on()`, `@with_cursor()`, `@with_confirm()` decorators |
| **Hot Reload** | `dev.py` | Medium — `milo dev` watches templates, live reloads |
| **Gateway** | `gateway.py` | Medium — multi-CLI registration behind single MCP endpoint |
| **Plugin System** | `plugins.py` | Medium — pluggable extensions |
| **Middleware** | `middleware.py` | Medium — request/response pipeline |
| **Session Recording** | (in app.py or related) | Low — JSONL recording, replay for debugging/CI |
| **Theme System** | `theme.py` | Low — color schemes, style customization |
| **Completions** | `completions.py` | Low — CLI tab completion |
| **Testing Utilities** | `testing/` | Low — test helpers |
| **Observability** | `observability.py` | Low — logging/tracing |
| **CLI Help** | `_cli_help.py`, `help.py` | Low — help rendering infrastructure |
| **Command Groups** | `groups.py` | Low — subcommand organization |

### Module Table Gap (Lines 183–190)

Current table shows 6 modules:

| Module | Purpose | Key types |
|--------|---------|-----------|
| `milo.app` | Event loop, lifecycle | `App`, `Screen`, `Middleware` |
| `milo.state` | State management | `Store`, `Reducer`, `Action`, `Effect` |
| `milo.input` | Terminal input | `KeyReader`, `Key` |
| `milo.form` | Interactive forms | `TextField`, `SelectField`, `ConfirmField`, `form()` |
| `milo.help` | Help screen rendering | `HelpRenderer` |
| `milo.components` | Kida templates | Field widgets, progress indicators |

Milo 0.2.1 has **40+ modules**. Proposed updated table (public modules only):

| Module | Purpose | Key types |
|--------|---------|-----------|
| `milo.cli` | CLI definition | `CLI`, `@cli.command`, `@cli.group` |
| `milo.commands` | Command routing | Command dispatch, lazy loading |
| `milo.groups` | Command groups | Nested subcommands |
| `milo.app` | Event loop, lifecycle | `App`, `Screen` |
| `milo.state` | State + saga runner | `Store`, `Reducer`, `Action`, `Fork`, `Call`, `Delay`, `Put`, `Select`, `Race`, `All`, `Retry`, `Take*`, `Batch`, `Sequence` |
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
| `milo.streaming` | Streaming output | `Progress`, generator consumption |
| `milo.dev` | Hot reload | `milo dev` file watcher |
| `milo.help` | Help rendering | `HelpRenderer` |
| `milo.theme` | Theming | Color schemes, styles |
| `milo.completions` | CLI completions | Tab completion |
| `milo.testing` | Test utilities | Test helpers |
| `milo.config` | Configuration | Config loading |
| `milo.observability` | Logging/tracing | Structured logging |

---

## Recommended Rewrite Approach

**Don't patch — rewrite**. The document's structure assumes "three things" (input, state, lifecycle). Milo 0.2.1 has at least 10 major capability areas. Patching individual sections will create an incoherent narrative.

Proposed new structure:

1. **Header** — keep tagline, update install
2. **Why** — keep, add MCP/AI angle
3. **What Milo Does** (new) — replace "Principles" with capability overview
4. **Architecture** — new diagram showing all layers
5. **Quick Examples** — update deploy example with saga, add MCP example
6. **Modules** — expanded table (above)
7. **The b-stack** — keep, minor updates
8. **Design Details** — add saga section, update state management
9. **What Milo Is Not** — keep
10. **Status** — "0.2.1 shipped" with feature list

---

## Acceptance Criteria

Sprint 2, Task 2.2 is done when:
- `rg 'design phase' docs/milo-vision.md` returns zero hits
- Module table covers all public modules from `src/milo/`
- Architecture diagram includes MCP, saga, pipeline layers
- At least one saga code example replaces the simple reducer deploy example
- MCP server mode (`--mcp`) documented with example
