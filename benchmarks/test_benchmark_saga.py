"""Saga→Reducer→Render benchmarks: full Milo hot path under free-threading.

Measures the complete cycle that runs on every state change in a Milo app:
  saga dispatches action → reducer produces new state → Kida template re-renders

Three measurement tiers:
  - Render-only: Kida rendering with no saga overhead
  - Full-cycle: saga dispatch → reducer → render (the production path)
  - Optimization: baseline vs static_context vs inlining

Worker scaling: 1/2/4/8 workers under PYTHON_GIL=0.

Run with: pytest benchmarks/test_benchmark_saga.py --benchmark-only -v
"""

from __future__ import annotations

import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import pytest
from milo._types import Action, All, Call, Put
from milo.state import Store

from kida.terminal import terminal_env
from kida.utils.workers import is_free_threading_enabled

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


# ---------------------------------------------------------------------------
# State types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Service:
    name: str
    status: str  # "healthy" | "degraded" | "down"
    latency_ms: float
    last_checked: float


@dataclass(frozen=True, slots=True)
class DashboardState:
    services: tuple[Service, ...] = ()
    cycle_count: int = 0
    loading: bool = True


SERVICE_NAMES = ("api", "web", "db", "cache", "queue")


# ---------------------------------------------------------------------------
# Context splits
# ---------------------------------------------------------------------------

STATIC_CTX: dict[str, object] = {
    "app_title": "Service Dashboard",
    "app_icon": "⚙",
    "version": "1.0.0",
    "show_latency": True,
    "debug": False,
}

_RNG = random.Random(42)  # deterministic for reproducible benchmarks


def _make_dynamic_ctx(services: tuple[Service, ...] = (), cycle: int = 0) -> dict[str, object]:
    return {
        "services": services,
        "cycle_count": cycle,
        "loading": len(services) == 0,
    }


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

DASHBOARD_TEMPLATE = """\
{%- set w = 64 -%}
{{ app_icon | bold | bright_cyan }} {{ app_title | bold }} v{{ version | dim }}
{{ hr(w) }}

{% if loading -%}
  Loading services...
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
"""


# ---------------------------------------------------------------------------
# Saga + reducer
# ---------------------------------------------------------------------------


def _fetch_service(name: str) -> Service:
    """Simulate HTTP fetch with ~1ms latency (fast to keep benchmarks quick)."""
    # Minimal sleep to create real thread contention without dominating runtime.
    time.sleep(0.001)
    return Service(
        name=name,
        status=_RNG.choice(("healthy", "healthy", "healthy", "degraded", "down")),
        latency_ms=_RNG.uniform(5.0, 50.0),
        last_checked=time.monotonic(),
    )


def _fetch_one(name: str):
    """Single-service fetch saga."""
    result = yield Call(fn=_fetch_service, args=(name,))
    return result


def _refresh_saga():
    """Fork 5 concurrent fetches, dispatch results."""
    results = yield All(sagas=tuple(_fetch_one(n) for n in SERVICE_NAMES))
    yield Put(action=Action(type="services_loaded", payload=results))


def _dashboard_reducer(state: DashboardState, action: object) -> DashboardState:
    if isinstance(action, Action) and action.type == "services_loaded":
        return replace(
            state,
            services=action.payload,
            loading=False,
            cycle_count=state.cycle_count + 1,
        )
    return state


def _wait_for_saga(store: Store, timeout: float = 2.0) -> None:
    """Poll until saga pool drains or timeout."""
    deadline = time.monotonic() + timeout
    while store.pool_active > 0 and time.monotonic() < deadline:
        time.sleep(0.001)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_env(*, static: bool = False, inline: bool = False):
    env = terminal_env(
        terminal_color="none",
        terminal_width=80,
        inline_components=inline,
    )
    if static:
        return env, env.from_string(DASHBOARD_TEMPLATE, static_context=STATIC_CTX)
    return env, env.from_string(DASHBOARD_TEMPLATE)


def _render_once(template, services: tuple[Service, ...], cycle: int = 0) -> str:
    ctx = {**STATIC_CTX, **_make_dynamic_ctx(services, cycle)}
    return template.render(**ctx)


def _full_cycle(store: Store, template) -> str:
    """Run one saga→reducer→render cycle and return rendered output."""
    store.run_saga(_refresh_saga())
    _wait_for_saga(store)
    state = store.state
    ctx = {**STATIC_CTX, **_make_dynamic_ctx(state.services, state.cycle_count)}
    return template.render(**ctx)


def _run_concurrent_cycles(
    template,
    workers: int,
    iterations_per_worker: int,
    *,
    static: bool = False,
) -> tuple[float, int]:
    """Run full saga→reducer→render cycles concurrently."""
    barrier = threading.Barrier(workers)
    total_renders = 0
    lock = threading.Lock()

    def worker():
        nonlocal total_renders
        # Each worker gets its own Store (independent state, like separate requests)
        store = Store(
            reducer=_dashboard_reducer,
            initial_state=DashboardState(),
        )
        barrier.wait()
        local_count = 0
        for _ in range(iterations_per_worker):
            _full_cycle(store, template)
            local_count += 1
        store.shutdown()
        with lock:
            total_renders += local_count

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker) for _ in range(workers)]
        for f in futures:
            f.result()
    elapsed = time.perf_counter() - start

    return elapsed, total_renders


# ---------------------------------------------------------------------------
# Baseline: render-only (no saga overhead)
# ---------------------------------------------------------------------------


class TestSagaBaselineBenchmarks:
    """Render-only vs full-cycle to isolate Kida rendering from Milo dispatch."""

    @pytest.mark.benchmark(group="saga:render-only")
    def test_render_only_no_static(self, benchmark: BenchmarkFixture) -> None:
        """Render dashboard template with no saga, no static_context."""
        _env, tpl = _make_env(static=False)
        services = tuple(Service(n, "healthy", 10.0, time.monotonic()) for n in SERVICE_NAMES)

        result = benchmark(_render_once, tpl, services, 1)
        assert "Service Dashboard" in result

    @pytest.mark.benchmark(group="saga:render-only")
    def test_render_only_with_static(self, benchmark: BenchmarkFixture) -> None:
        """Render dashboard template with static_context (no saga)."""
        _env, tpl = _make_env(static=True)
        services = tuple(Service(n, "healthy", 10.0, time.monotonic()) for n in SERVICE_NAMES)

        result = benchmark(_render_once, tpl, services, 1)
        assert "Service Dashboard" in result
        assert "Cycle:" not in result  # debug=False → dead branch eliminated

    @pytest.mark.benchmark(group="saga:full-cycle")
    def test_full_cycle_single(self, benchmark: BenchmarkFixture) -> None:
        """One full saga→reducer→render cycle (single-threaded)."""
        _env, tpl = _make_env(static=True)
        store = Store(reducer=_dashboard_reducer, initial_state=DashboardState())

        def run():
            return _full_cycle(store, tpl)

        result = benchmark.pedantic(run, rounds=5, iterations=1)
        assert "Service Dashboard" in result
        store.shutdown()


# ---------------------------------------------------------------------------
# Worker scaling: 1/2/4/8 concurrent full cycles
# ---------------------------------------------------------------------------


class TestSagaScalingBenchmarks:
    """Measure linear scaling under PYTHON_GIL=0 with increasing workers."""

    @pytest.mark.benchmark(group="saga:scaling")
    def test_1_worker(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: 1 worker, 20 full cycles."""
        _env, tpl = _make_env(static=True)

        def run():
            return _run_concurrent_cycles(tpl, workers=1, iterations_per_worker=20, static=True)

        benchmark.pedantic(run, rounds=5, iterations=1)

    @pytest.mark.benchmark(group="saga:scaling")
    def test_2_workers(self, benchmark: BenchmarkFixture) -> None:
        """2 workers, 10 cycles each (20 total)."""
        _env, tpl = _make_env(static=True)

        def run():
            return _run_concurrent_cycles(tpl, workers=2, iterations_per_worker=10, static=True)

        benchmark.pedantic(run, rounds=5, iterations=1)

    @pytest.mark.benchmark(group="saga:scaling")
    def test_4_workers(self, benchmark: BenchmarkFixture) -> None:
        """4 workers, 5 cycles each (20 total)."""
        _env, tpl = _make_env(static=True)

        def run():
            return _run_concurrent_cycles(tpl, workers=4, iterations_per_worker=5, static=True)

        benchmark.pedantic(run, rounds=5, iterations=1)

    @pytest.mark.benchmark(group="saga:scaling")
    def test_8_workers(self, benchmark: BenchmarkFixture) -> None:
        """8 workers, 3 cycles each (~24 total)."""
        _env, tpl = _make_env(static=True)

        def run():
            return _run_concurrent_cycles(tpl, workers=8, iterations_per_worker=3, static=True)

        benchmark.pedantic(run, rounds=5, iterations=1)


# ---------------------------------------------------------------------------
# Optimization tiers: baseline vs static_context vs inlining
# ---------------------------------------------------------------------------


class TestSagaOptimizationBenchmarks:
    """Measure compiler optimization impact on full saga→render cycle."""

    @pytest.mark.benchmark(group="saga:optimization")
    def test_no_optimization(self, benchmark: BenchmarkFixture) -> None:
        """Full cycle, no static_context, no inlining."""
        _env, tpl = _make_env(static=False, inline=False)
        store = Store(reducer=_dashboard_reducer, initial_state=DashboardState())

        def run():
            return _full_cycle(store, tpl)

        result = benchmark.pedantic(run, rounds=5, iterations=1)
        assert "Service Dashboard" in result
        store.shutdown()

    @pytest.mark.benchmark(group="saga:optimization")
    def test_static_context(self, benchmark: BenchmarkFixture) -> None:
        """Full cycle with static_context (constant folding + dead branch elimination)."""
        _env, tpl = _make_env(static=True, inline=False)
        store = Store(reducer=_dashboard_reducer, initial_state=DashboardState())

        def run():
            return _full_cycle(store, tpl)

        result = benchmark.pedantic(run, rounds=5, iterations=1)
        assert "Service Dashboard" in result
        store.shutdown()

    @pytest.mark.benchmark(group="saga:optimization")
    def test_static_context_with_inlining(self, benchmark: BenchmarkFixture) -> None:
        """Full cycle with static_context + component inlining."""
        _env, tpl = _make_env(static=True, inline=True)
        store = Store(reducer=_dashboard_reducer, initial_state=DashboardState())

        def run():
            return _full_cycle(store, tpl)

        result = benchmark.pedantic(run, rounds=5, iterations=1)
        assert "Service Dashboard" in result
        store.shutdown()


# ---------------------------------------------------------------------------
# Session configuration
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Print free-threading status and saga info at test session start."""
    gil_enabled = sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True
    free_threading = is_free_threading_enabled()

    print(f"\n{'=' * 60}")
    print(f"Saga Benchmark — Python {sys.version}")
    print(f"GIL enabled: {gil_enabled}")
    print(f"Free-threading: {free_threading}")
    print("Milo Store max_workers: default (ThreadPoolExecutor)")
    print(f"Services per cycle: {len(SERVICE_NAMES)}")
    print("Fetch latency: ~1ms (simulated)")
    print(f"{'=' * 60}\n")
