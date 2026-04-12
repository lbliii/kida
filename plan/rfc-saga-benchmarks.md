# RFC: Saga Benchmark Protocol

**Status**: Draft
**Created**: 2026-04-12
**Epic**: `plan/epic-kida-milo-integration.md` — Sprint 0, Task 0.1

---

## Goal

Benchmark the full Milo hot path — saga dispatches action → reducer produces new state → Kida template re-renders — under `PYTHON_GIL=0` with 1/2/4/8 workers. This is the cycle that runs on every user interaction in a Milo app.

---

## State Shape

Frozen dataclass modeling a service dashboard (matches existing `benchmarks/test_benchmark_terminal.py` patterns):

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Service:
    name: str
    status: str          # "healthy" | "degraded" | "down"
    latency_ms: float
    last_checked: float  # time.monotonic()

@dataclass(frozen=True, slots=True)
class DashboardState:
    services: tuple[Service, ...] = ()
    cycle_count: int = 0
    loading: bool = True
```

---

## Static vs Dynamic Context

Follow the three-tier pattern from `test_benchmark_terminal.py` (lines 64–89):

```python
# Known at app init — folded at compile time
STATIC_CTX = {
    "app_title": "Service Dashboard",
    "app_icon": "⚙",
    "version": "1.0.0",
    "show_latency": True,
    "debug": False,
}

# Changes every render cycle
DYNAMIC_CTX = {
    "services": [...],  # from DashboardState
    "cycle_count": 0,
    "loading": False,
}
```

---

## Saga Pattern

Generator-based saga using Milo 0.2.1 primitives:

```python
from milo._types import Fork, Call, Delay, Put, All

def fetch_service(name: str) -> Service:
    """Simulate HTTP fetch — 10ms latency."""
    time.sleep(0.01)
    return Service(
        name=name,
        status="healthy",
        latency_ms=random.uniform(5, 50),
        last_checked=time.monotonic(),
    )

def refresh_saga():
    """Fork 5 concurrent fetches, dispatch results."""
    fetches = tuple(
        Call(fn=fetch_service, args=(name,))
        for name in ("api", "web", "db", "cache", "queue")
    )
    results = yield All(sagas=fetches)
    yield Put(action=Action(type="services_loaded", payload=results))
```

**Why this pattern**: It exercises `Fork`/`Call`/`All`/`Put` — the four most common saga primitives — in a realistic concurrent workload. The 10ms simulated fetch ensures threads actually contend rather than completing instantly.

---

## Reducer

```python
from dataclasses import replace

def dashboard_reducer(state: DashboardState, action: Action) -> DashboardState:
    match action.type:
        case "services_loaded":
            return replace(state, services=action.payload, loading=False,
                          cycle_count=state.cycle_count + 1)
        case _:
            return state
```

---

## Template

Terminal template with `static_context` optimization opportunities:

```kida
{%- set w = 64 -%}
{{ app_icon | bold | bright_cyan }} {{ app_title | bold }} v{{ version | dim }}
{{ hr(w) }}

{% if loading -%}
  {{ spinner() }} Loading services...
{% else -%}
  {% for svc in services -%}
    {% if svc.status == "healthy" -%}
      {{ icons.check | green }}
    {% elif svc.status == "degraded" -%}
      {{ icons.warn | yellow }}
    {% else -%}
      {{ icons.cross | red }}
    {% end -%}
    {{ svc.name | pad(12) }}
    {% if show_latency %}{{ svc.latency_ms | round(1) }}ms{% end %}
  {% end -%}
{% end -%}

{% if debug -%}
  {{ hr(w) }}
  Cycle: {{ cycle_count }}
{% end -%}

{{ hr(w) }}
{{ app_title | dim }} {{ "refresh: 1s" | dim }}
```

With `static_context=STATIC_CTX`:
- `{% if debug %}` block eliminated (dead branch)
- `app_icon | bold | bright_cyan`, `app_title | bold`, `version | dim` folded to constants
- `{% if show_latency %}` resolved to always-true

---

## Measurement Methodology

### What to Measure

**Full cycle**: saga dispatch → reducer → render. Not just rendering.

```python
def full_cycle(store, template, static_ctx, dynamic_ctx):
    """One complete saga→reducer→render cycle."""
    # 1. Run saga (dispatches action internally)
    store.dispatch(Action(type="refresh"))
    # 2. Get new state
    state = store.get_state()
    # 3. Render with new state
    ctx = {**static_ctx, **asdict(state)}
    return template.render(**ctx)
```

### Worker Scaling

Follow `test_benchmark_concurrent.py` pattern (lines 68–96):

| Group | Workers | Iterations/Worker | Total Renders |
|-------|---------|-------------------|---------------|
| `saga:baseline` | 1 | 100 | 100 |
| `saga:2-workers` | 2 | 50 | 100 |
| `saga:4-workers` | 4 | 25 | 100 |
| `saga:8-workers` | 8 | 13 | ~104 |

Each uses `threading.Barrier(workers)` for synchronized start.

### Three Optimization Tiers

1. **No static context** — baseline, all context resolved at render time
2. **With static context** — `env.from_string(template, static_context=STATIC_CTX)`
3. **With static context + inlining** — `Environment(inline_components=True)`

### Isolation

To separate Kida rendering overhead from Milo dispatch overhead:
- **Render-only benchmark**: Same template/context, no saga dispatch (existing pattern)
- **Dispatch-only benchmark**: Saga → reducer, no render
- **Full-cycle benchmark**: Saga → reducer → render (the production path)

### Stability

- `rounds=5, iterations=1` per `benchmark.pedantic()` (matches existing benchmarks)
- GC disabled during measurement via `conftest.py:gc_disabled()` fixture
- Report `sys._is_gil_enabled()` at session start via `pytest_configure()`

---

## File Structure

```
benchmarks/test_benchmark_saga.py
├── Imports (kida, milo, pytest, threading)
├── State types (DashboardState, Service)
├── STATIC_CTX / DYNAMIC_CTX
├── Template source
├── Saga generator + reducer
├── Helper: run_saga_cycle(store, template, workers, iterations_per_worker)
├── TestSagaBaselineBenchmarks (render-only vs full-cycle, 1 worker)
├── TestSagaScalingBenchmarks (1/2/4/8 workers, full-cycle)
├── TestSagaOptimizationBenchmarks (no-static vs static vs inlining)
└── pytest_configure() — session metadata
```

---

## Dependencies

Add to `pyproject.toml` dev group:
```toml
"milo-cli>=0.2.1",
```

This is a dev-only dependency — Kida's runtime stays zero-dep.

---

## Success Criteria

- `uv run pytest benchmarks/test_benchmark_saga.py --benchmark-only -v` runs clean
- Worker scaling shows measurable speedup under `PYTHON_GIL=0` (4 workers > 2x single-threaded)
- Static context tier shows measurable rendering speedup vs baseline
- Results are < 10% variance across 3 consecutive runs
