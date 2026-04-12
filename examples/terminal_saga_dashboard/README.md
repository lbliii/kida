# Saga Dashboard Example

Demonstrates the full Milo + Kida integration pattern:

- **Frozen dataclass state** — thread-safe by design
- **Saga system** — `All` + `Call` for concurrent service health checks
- **Kida terminal template** — `static_context` folds app config at compile time
- **LiveRenderer** — in-place re-rendering on each state change

## Run

```bash
python examples/terminal_saga_dashboard/run.py
```

Ctrl+C to stop.

## How It Works

1. `refresh_saga()` forks 5 concurrent `Call` effects (one per service)
2. `All` waits for all fetches to complete
3. `Put` dispatches a `services_loaded` action
4. `dashboard_reducer` produces new frozen state
5. `LiveRenderer.update()` re-renders the Kida terminal template in-place

The template uses `static_context` so app config (`app_title`, `version`, etc.) is folded at compile time. Only dynamic data (service status, latency) is resolved at render time.

## Dependencies

- `kida` (terminal rendering)
- `milo-cli>=0.2.1` (saga system, Store)
