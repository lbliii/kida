"""Seeded no-GIL stress across supported shared runtime operations."""

from __future__ import annotations

import concurrent.futures
import io
import os
import random
import threading
from collections import Counter

import pytest

from kida import DictLoader, Environment
from kida.terminal import LiveRenderer, Spinner, terminal_env
from kida.utils.workers import Environment as WorkerEnvironment
from kida.utils.workers import WorkloadType, get_optimal_workers, should_parallelize


def _configured_seeds() -> tuple[object, ...]:
    """Build reproducible seed parameters from the CI stress window."""
    base_seed = int(os.environ.get("KIDA_STRESS_SEED", "0"))
    run_count = int(os.environ.get("KIDA_STRESS_RUNS", "1"))
    if not 1 <= run_count <= 100:
        raise ValueError("KIDA_STRESS_RUNS must be between 1 and 100")
    return tuple(
        pytest.param(base_seed + offset, id=f"seed-{base_seed + offset}")
        for offset in range(run_count)
    )


@pytest.mark.parametrize("seed", _configured_seeds())
def test_randomized_supported_operations(seed: int) -> None:
    """Randomize roles, keys, invalidation, and submission order without sleeps."""
    print(f"KIDA thread stress seed: {seed}")

    operations = (
        "render",
        "stream",
        "block",
        "introspection",
        "template_cache",
        "fragment_cache",
        "live",
        "spinner",
        "workers",
        "clear",
    )
    worker_count = len(operations)
    rounds = 40
    rng = random.Random(seed)

    sources = {
        "shared.html": (
            "{% def badge(label: str) %}[{{ label }}]{% end %}"
            "{% block content %}B:{{ value }}:{{ badge(label) }}{% end %}"
            "|F:{{ value }}"
        ),
        **{
            f"cache-{template_id}.html": f"cache-{template_id}:{{{{ marker }}}}"
            for template_id in range(8)
        },
    }
    env = Environment(
        loader=DictLoader(sources),
        autoescape=False,
        cache_size=4,
        fragment_cache_size=4,
        fragment_ttl=300,
    )
    shared_template = env.get_template("shared.html")
    fragment_template = env.from_string(
        "{% cache key %}fragment:{{ key }}{% endcache %}",
        name="fragment.html",
    )

    terminal_environment = terminal_env(terminal_color="none")
    live_template = terminal_environment.from_string(
        "{{ marker }}|{{ spinner() }}",
        name="randomized-live",
    )
    terminal_output = io.StringIO()
    spinner_frames = ("A", "B", "C", "D")
    spinner = Spinner(frames=spinner_frames)

    workloads = tuple(WorkloadType)
    worker_environments = tuple(WorkerEnvironment)
    plans: list[tuple[tuple[str, int, str, int, WorkloadType, WorkerEnvironment], ...]] = []
    for _round_id in range(rounds):
        shuffled_operations = list(operations)
        rng.shuffle(shuffled_operations)
        plans.append(
            tuple(
                (
                    operation,
                    rng.randrange(8),
                    f"fragment-{rng.randrange(8)}",
                    rng.randrange(3),
                    rng.choice(workloads),
                    rng.choice(worker_environments),
                )
                for operation in shuffled_operations
            )
        )

    submission_order = list(range(worker_count))
    rng.shuffle(submission_order)
    phase = threading.Barrier(worker_count)

    def exercise(worker_id: int, live: LiveRenderer) -> list[str]:
        direct_spinner_frames: list[str] = []
        try:
            for round_id, round_plan in enumerate(plans):
                operation, template_id, fragment_key, clear_kind, workload, worker_env = round_plan[
                    worker_id
                ]
                marker = f"seed-{seed}:round-{round_id}:worker-{worker_id}:{operation}"
                phase.wait(timeout=30)

                if operation == "render":
                    assert shared_template.render(value=marker, label=marker) == (
                        f"B:{marker}:[{marker}]|F:{marker}"
                    )
                elif operation == "stream":
                    assert (
                        "".join(shared_template.render_stream(value=marker, label=marker))
                        == f"B:{marker}:[{marker}]|F:{marker}"
                    )
                elif operation == "block":
                    assert (
                        shared_template.render_block("content", value=marker, label=marker)
                        == f"B:{marker}:[{marker}]"
                    )
                elif operation == "introspection":
                    assert shared_template.list_blocks() == ["content"]
                    assert shared_template.list_defs() == ["badge"]
                    assert shared_template.template_metadata() is not None
                elif operation == "template_cache":
                    name = f"cache-{template_id}.html"
                    assert env.get_template(name).render(marker=marker) == (
                        f"cache-{template_id}:{marker}"
                    )
                elif operation == "fragment_cache":
                    assert fragment_template.render(key=fragment_key) == (
                        f"fragment:{fragment_key}"
                    )
                elif operation == "live":
                    live.update(marker=marker, spinner=spinner)
                elif operation == "spinner":
                    direct_spinner_frames.append(str(spinner()))
                elif operation == "workers":
                    workers = get_optimal_workers(
                        100,
                        workload_type=workload,
                        environment=worker_env,
                    )
                    assert 1 <= workers <= 100
                    assert should_parallelize(
                        100,
                        workload_type=workload,
                        environment=worker_env,
                        total_work_estimate=10_000,
                    )
                else:
                    if clear_kind == 0:
                        env.clear_template_cache()
                    elif clear_kind == 1:
                        env.clear_template_cache([f"cache-{template_id}.html"])
                    else:
                        env.clear_fragment_cache()

                phase.wait(timeout=30)
        except BaseException:
            phase.abort()
            raise
        return direct_spinner_frames

    with (
        LiveRenderer(live_template, file=terminal_output) as live,
        concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor,
    ):
        futures = [executor.submit(exercise, worker_id, live) for worker_id in submission_order]
        direct_frames = [frame for future in futures for frame in future.result()]

    live_lines = [line for line in terminal_output.getvalue().splitlines() if line]
    expected_live_markers = {
        f"seed-{seed}:round-{round_id}:worker-{worker_id}:live"
        for round_id, round_plan in enumerate(plans)
        for worker_id, plan in enumerate(round_plan)
        if plan[0] == "live"
    }
    live_markers: list[str] = []
    live_frames: list[str] = []
    for line in live_lines:
        marker, frame = line.split("|", maxsplit=1)
        live_markers.append(marker)
        live_frames.append(frame)

    assert len(live_markers) == rounds
    assert set(live_markers) == expected_live_markers
    assert Counter([*direct_frames, *live_frames]) == {
        frame: rounds * 2 // len(spinner_frames) for frame in spinner_frames
    }
