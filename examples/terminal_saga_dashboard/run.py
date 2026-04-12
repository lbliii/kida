"""Milo saga dashboard — concurrent service fetches with live Kida rendering.

Demonstrates the full Milo + Kida integration pattern:
  - Frozen dataclass state (thread-safe by design)
  - Saga system for concurrent side effects (Fork/Call/All/Put)
  - Kida terminal template with static_context optimization
  - LiveRenderer for in-place re-rendering

Usage:
    python examples/terminal_saga_dashboard/run.py
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, replace
from pathlib import Path

from milo._types import Action, All, Call, Put
from milo.state import Store

from kida.terminal import LiveRenderer, terminal_env

# ---------------------------------------------------------------------------
# State — frozen dataclasses, thread-safe by design
# ---------------------------------------------------------------------------

SERVICES = ("api-gateway", "web-frontend", "postgres", "redis-cache", "task-queue")


@dataclass(frozen=True, slots=True)
class Service:
    name: str
    status: str  # "healthy" | "degraded" | "down"
    latency: str  # formatted, e.g. "12.3ms"


@dataclass(frozen=True, slots=True)
class DashboardState:
    services: tuple[Service, ...] = ()
    cycle_count: int = 0
    loading: bool = True


# ---------------------------------------------------------------------------
# Saga — concurrent service fetches
# ---------------------------------------------------------------------------

_rng = random.Random()


def _fetch_service(name: str) -> Service:
    """Simulate an HTTP health check (5-50ms latency)."""
    latency_ms = _rng.uniform(5.0, 50.0)
    time.sleep(latency_ms / 1000)  # simulate network
    status = _rng.choices(
        ("healthy", "degraded", "down"),
        weights=(85, 10, 5),
    )[0]
    return Service(name=name, status=status, latency=f"{latency_ms:.1f}ms")


def _fetch_one(name: str):
    """Single-service fetch saga."""
    result = yield Call(fn=_fetch_service, args=(name,))
    return result


def refresh_saga():
    """Fetch all services concurrently, dispatch results."""
    results = yield All(sagas=tuple(_fetch_one(n) for n in SERVICES))
    yield Put(action=Action(type="services_loaded", payload=results))


# ---------------------------------------------------------------------------
# Reducer — pure function, no side effects
# ---------------------------------------------------------------------------


def dashboard_reducer(state: DashboardState, action: object) -> DashboardState:
    if isinstance(action, Action) and action.type == "services_loaded":
        return replace(
            state,
            services=action.payload,
            loading=False,
            cycle_count=state.cycle_count + 1,
        )
    return state


# ---------------------------------------------------------------------------
# Template setup — static_context folds app config at compile time
# ---------------------------------------------------------------------------

STATIC_CTX = {
    "app_title": "Service Dashboard",
    "app_icon": "⚙",
    "version": "1.0.0",
    "separator": "│",
}

TEMPLATE_DIR = Path(__file__).parent / "templates"


def main() -> None:
    env = terminal_env()
    template_source = (TEMPLATE_DIR / "dashboard.txt").read_text()
    tpl = env.from_string(template_source, name="dashboard.txt", static_context=STATIC_CTX)

    store = Store(reducer=dashboard_reducer, initial_state=DashboardState())

    print("Starting saga dashboard (Ctrl+C to stop)\n")

    try:
        with LiveRenderer(tpl) as live:
            for _ in range(10):  # 10 refresh cycles
                # Run saga — fetches all services concurrently
                store.run_saga(refresh_saga())

                # Wait for saga to complete
                deadline = time.monotonic() + 2.0
                while store.pool_active > 0 and time.monotonic() < deadline:
                    time.sleep(0.01)

                # Render with new state
                state = store.state
                live.update(
                    **STATIC_CTX,
                    services=state.services,
                    cycle_count=state.cycle_count,
                    loading=state.loading,
                )

                time.sleep(2.0)  # refresh interval
    except KeyboardInterrupt:
        pass
    finally:
        store.shutdown()

    print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
