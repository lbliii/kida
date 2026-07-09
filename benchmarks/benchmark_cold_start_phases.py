"""Measure Kida's cold-start contract as explicit, isolated phases.

This runner is measurement-only. It does not set thresholds or update the
published performance comparison. Official baseline candidates must be
captured on Linux CPython 3.14t with the GIL disabled::

    PYTHON_GIL=0 uv run python benchmarks/benchmark_cold_start_phases.py \
        --require-linux-3-14t --output /tmp/kida-cold-start-linux.json

Runs on other hosts are marked ``development-only`` in the JSON output and
must not be used as public competitive claims.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import sysconfig
import tempfile
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
TEMPLATE_NAME = "cold-start-phase.html"
TEMPLATE_SOURCE = "<h1>{{ title }}</h1><ul>{% for item in items %}<li>{{ item }}</li>{% end %}</ul>"
RENDER_CONTEXT = {
    "title": "Cold start",
    "items": ["alpha", "beta", "gamma"],
}
EXPECTED_OUTPUT = "<h1>Cold start</h1><ul><li>alpha</li><li>beta</li><li>gamma</li></ul>"
PHASES = (
    "process_startup",
    "import_kida",
    "import_environment",
    "environment_construction",
    "first_source_render",
    "first_bytecode_cache_render",
    "warm_render",
)
DEFAULT_WARMUPS = 3
DEFAULT_SAMPLES = 20
DEFAULT_MEMORY_SAMPLES = 5


def _peak_rss_bytes() -> int | None:
    """Return process peak RSS in bytes on POSIX hosts."""
    try:
        import resource
    except ImportError:  # pragma: no cover - the official Linux runner has resource
        return None

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Darwin reports bytes; Linux and the other supported POSIX benchmark
    # hosts report KiB.
    return int(value if sys.platform == "darwin" else value * 1024)


def _kida_module_closure() -> tuple[list[str], int, list[str]]:
    """Return loaded Kida modules, physical source LOC, and missing sources."""
    modules: list[str] = []
    source_paths: set[Path] = set()
    missing_sources: set[str] = set()

    for name, module in sorted(sys.modules.items()):
        if name != "kida" and not name.startswith("kida."):
            continue
        modules.append(name)
        raw_path = getattr(module, "__file__", None)
        if raw_path is None:
            missing_sources.add(name)
            continue
        path = Path(raw_path)
        if path.suffix != ".py" or not path.is_file():
            missing_sources.add(name)
            continue
        source_paths.add(path.resolve())

    physical_loc = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in source_paths)
    return modules, physical_loc, sorted(missing_sources)


def _profile_action(action: Callable[[], object], *, measure_memory: bool) -> dict[str, Any]:
    """Time one isolated phase and capture its post-phase resource facts."""
    rss_before = _peak_rss_bytes()
    if measure_memory:
        tracemalloc.start()
    started_ns = time.perf_counter_ns()
    result = action()
    elapsed_ns = time.perf_counter_ns() - started_ns
    if measure_memory:
        python_current_bytes, python_peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    else:
        python_current_bytes = None
        python_peak_bytes = None
    rss_after = _peak_rss_bytes()

    modules, physical_loc, missing_sources = _kida_module_closure()
    return {
        "elapsed_ms": elapsed_ns / 1_000_000,
        "python_current_bytes": python_current_bytes,
        "python_peak_bytes": python_peak_bytes,
        "process_peak_rss_before_bytes": rss_before,
        "process_peak_rss_after_bytes": rss_after,
        "process_peak_rss_growth_bytes": (
            None if rss_before is None or rss_after is None else max(0, rss_after - rss_before)
        ),
        "kida_module_count": len(modules),
        "kida_source_loc": physical_loc,
        "kida_modules": modules,
        "kida_modules_missing_source": missing_sources,
        "result_type": type(result).__name__,
    }


def _worker_phase(
    phase: str,
    *,
    template_dir: Path | None,
    cache_dir: Path | None,
    measure_memory: bool,
) -> dict[str, Any]:
    """Run one phase inside a fresh worker process."""
    if phase == "import_kida":
        return _profile_action(lambda: __import__("kida"), measure_memory=measure_memory)

    if phase == "import_environment":
        return _profile_action(
            lambda: __import__("kida", fromlist=("Environment",)).Environment,
            measure_memory=measure_memory,
        )

    if phase == "environment_construction":
        from kida import Environment

        return _profile_action(Environment, measure_memory=measure_memory)

    if phase == "first_source_render":
        from kida import Environment

        environment = Environment()

        def render_source() -> str:
            template = environment.from_string(TEMPLATE_SOURCE)
            output = template.render(**RENDER_CONTEXT)
            if output != EXPECTED_OUTPUT:
                raise AssertionError(f"Unexpected source-render output: {output!r}")
            return output

        return _profile_action(render_source, measure_memory=measure_memory)

    if phase == "first_bytecode_cache_render":
        if template_dir is None or cache_dir is None:
            raise ValueError("cache phase requires template and cache directories")
        from kida import Environment, FileSystemLoader
        from kida.bytecode_cache import BytecodeCache

        environment = Environment(
            loader=FileSystemLoader(template_dir),
            bytecode_cache=BytecodeCache(cache_dir),
        )

        def render_cached() -> str:
            output = environment.get_template(TEMPLATE_NAME).render(**RENDER_CONTEXT)
            if output != EXPECTED_OUTPUT:
                raise AssertionError(f"Unexpected bytecode-cache output: {output!r}")
            return output

        return _profile_action(render_cached, measure_memory=measure_memory)

    if phase == "warm_render":
        from kida import Environment

        environment = Environment()
        template = environment.from_string(TEMPLATE_SOURCE)
        preflight_output = template.render(**RENDER_CONTEXT)
        if preflight_output != EXPECTED_OUTPUT:
            raise AssertionError(f"Unexpected warm-render preflight output: {preflight_output!r}")

        def render_warm() -> str:
            output = template.render(**RENDER_CONTEXT)
            if output != EXPECTED_OUTPUT:
                raise AssertionError(f"Unexpected warm-render output: {output!r}")
            return output

        return _profile_action(render_warm, measure_memory=measure_memory)

    raise ValueError(f"Unknown worker phase: {phase}")


def _worker_preflight(template_dir: Path, cache_dir: Path) -> dict[str, Any]:
    """Prove source, cache, and warm outputs before timing begins."""
    from kida import Environment, FileSystemLoader
    from kida.bytecode_cache import BytecodeCache

    source_environment = Environment()
    source_template = source_environment.from_string(TEMPLATE_SOURCE)
    first_output = source_template.render(**RENDER_CONTEXT)
    warm_output = source_template.render(**RENDER_CONTEXT)

    cached_environment = Environment(
        loader=FileSystemLoader(template_dir),
        bytecode_cache=BytecodeCache(cache_dir),
    )
    cached_output = cached_environment.get_template(TEMPLATE_NAME).render(**RENDER_CONTEXT)
    cache_files = sorted(path.name for path in cache_dir.iterdir() if path.is_file())

    for label, output in (
        ("first source", first_output),
        ("warm", warm_output),
        ("bytecode cache population", cached_output),
    ):
        if output != EXPECTED_OUTPUT:
            raise AssertionError(f"Unexpected {label} output: {output!r}")
    if not cache_files:
        raise AssertionError("Bytecode-cache preflight did not create an artifact")

    return {
        "passed": True,
        "expected_output_sha256": hashlib.sha256(EXPECTED_OUTPUT.encode()).hexdigest(),
        "template_source_sha256": hashlib.sha256(TEMPLATE_SOURCE.encode()).hexdigest(),
        "bytecode_cache_artifacts": cache_files,
    }


def _child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONHASHSEED"] = "0"
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{SOURCE_ROOT}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(SOURCE_ROOT)
    )
    return environment


def _run_worker(
    phase: str,
    *,
    template_dir: Path,
    cache_dir: Path,
    measure_memory: bool = False,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        phase,
        "--template-dir",
        str(template_dir),
        "--cache-dir",
        str(cache_dir),
    ]
    if measure_memory:
        command.append("--measure-memory")
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=_child_environment(),
        cwd=ROOT,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Cold-start worker {phase!r} failed with {completed.returncode}:\n{completed.stderr}"
        )
    return json.loads(completed.stdout)


def _run_process_startup() -> dict[str, Any]:
    """Measure isolated interpreter launch plus a minimal RSS probe."""
    probe = "import resource;print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)"
    started_ns = time.perf_counter_ns()
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", probe],
        check=False,
        capture_output=True,
        text=True,
        env=_child_environment(),
        cwd=ROOT,
    )
    elapsed_ns = time.perf_counter_ns() - started_ns
    if completed.returncode != 0:
        raise RuntimeError(f"Process-startup probe failed: {completed.stderr}")
    raw_rss = int(completed.stdout.strip())
    rss_bytes = raw_rss if sys.platform == "darwin" else raw_rss * 1024
    return {
        "elapsed_ms": elapsed_ns / 1_000_000,
        "python_current_bytes": None,
        "python_peak_bytes": None,
        "process_peak_rss_before_bytes": 0,
        "process_peak_rss_after_bytes": rss_bytes,
        "process_peak_rss_growth_bytes": rss_bytes,
        "kida_module_count": 0,
        "kida_source_loc": 0,
        "kida_modules": [],
        "kida_modules_missing_source": [],
        "result_type": "process-exit",
    }


def _nearest_rank_p95(values: Sequence[float | int]) -> float:
    """Return the deterministic nearest-rank 95th percentile."""
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return float(ordered[index])


def _summary(
    timing_samples: Sequence[dict[str, Any]],
    memory_samples: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    metrics = {
        "elapsed_ms": timing_samples,
        "python_current_bytes": memory_samples,
        "python_peak_bytes": memory_samples,
        "process_peak_rss_after_bytes": timing_samples,
        "process_peak_rss_growth_bytes": timing_samples,
        "kida_module_count": timing_samples,
        "kida_source_loc": timing_samples,
    }
    summary: dict[str, Any] = {}
    for metric, source_samples in metrics.items():
        values = [sample[metric] for sample in source_samples if sample.get(metric) is not None]
        summary[metric] = (
            None
            if not values
            else {
                "median": float(statistics.median(values)),
                "p95": _nearest_rank_p95(values),
                "min": float(min(values)),
                "max": float(max(values)),
            }
        )
    return summary


def _free_threading_facts() -> tuple[bool, bool | None]:
    build = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    is_gil_enabled = getattr(sys, "_is_gil_enabled", None)
    gil_enabled = bool(is_gil_enabled()) if is_gil_enabled is not None else None
    return build, gil_enabled


def _environment_metadata() -> dict[str, Any]:
    free_threading_build, gil_enabled = _free_threading_facts()
    try:
        kida_version = importlib.metadata.version("kida-templates")
    except importlib.metadata.PackageNotFoundError:
        kida_version = "unknown"

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_machine": platform.machine(),
        "platform_processor": platform.processor(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_build": platform.python_build(),
        "python_executable": sys.executable,
        "python_cache_tag": sys.implementation.cache_tag,
        "free_threading_build": free_threading_build,
        "gil_enabled": gil_enabled,
        "cpu_count": os.cpu_count(),
        "kida_version": kida_version,
        "git_revision": revision.stdout.strip() if revision.returncode == 0 else None,
    }


def _is_linux_3_14t(environment: dict[str, Any]) -> bool:
    return bool(
        environment["platform_system"] == "Linux"
        and environment["python_implementation"] == "CPython"
        and sys.version_info[:2] == (3, 14)
        and environment["free_threading_build"]
        and environment["gil_enabled"] is False
    )


def build_report(
    *,
    warmups: int,
    samples: int,
    memory_samples: int,
    require_linux_3_14t: bool,
) -> dict[str, Any]:
    """Run all phases and return the versioned machine-readable report."""
    if warmups < 0:
        raise ValueError("warmups must be non-negative")
    if samples < 1:
        raise ValueError("samples must be positive")
    if memory_samples < 1:
        raise ValueError("memory_samples must be positive")

    environment = _environment_metadata()
    claim_eligible = _is_linux_3_14t(environment)
    if require_linux_3_14t and not claim_eligible:
        raise RuntimeError(
            "Official cold-start baselines require Linux CPython 3.14t with the GIL disabled"
        )

    with tempfile.TemporaryDirectory(prefix="kida-cold-start-") as temporary:
        base = Path(temporary)
        template_dir = base / "templates"
        cache_dir = base / "cache"
        template_dir.mkdir()
        cache_dir.mkdir()
        (template_dir / TEMPLATE_NAME).write_text(TEMPLATE_SOURCE, encoding="utf-8")

        # This functional gate deliberately runs before any timed warmup or
        # sample. Each timed render also rechecks its output.
        sanity = _run_worker(
            "preflight",
            template_dir=template_dir,
            cache_dir=cache_dir,
        )

        phase_reports: dict[str, Any] = {}
        for phase in PHASES:
            for _ in range(warmups):
                if phase == "process_startup":
                    _run_process_startup()
                else:
                    _run_worker(phase, template_dir=template_dir, cache_dir=cache_dir)

            raw_samples = [
                (
                    _run_process_startup()
                    if phase == "process_startup"
                    else _run_worker(phase, template_dir=template_dir, cache_dir=cache_dir)
                )
                for _ in range(samples)
            ]
            raw_memory_samples = (
                []
                if phase == "process_startup"
                else [
                    _run_worker(
                        phase,
                        template_dir=template_dir,
                        cache_dir=cache_dir,
                        measure_memory=True,
                    )
                    for _ in range(memory_samples)
                ]
            )
            phase_reports[phase] = {
                "summary": _summary(raw_samples, raw_memory_samples),
                "samples": raw_samples,
                "memory_samples": raw_memory_samples,
            }

    return {
        "schema_version": 1,
        "contract": "kida-cold-start-phases-v1",
        "issue": 247,
        "status": "baseline-candidate" if claim_eligible else "development-only",
        "claim_eligible": claim_eligible,
        "environment": environment,
        "methodology": {
            "warmups_per_phase": warmups,
            "samples_per_phase": samples,
            "memory_samples_per_phase": memory_samples,
            "timer": "time.perf_counter_ns",
            "percentile": "nearest-rank p95",
            "child_environment": {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "PYTHON_GIL": os.environ.get("PYTHON_GIL"),
            },
            "output_sanity": (
                "An untimed source/warm/bytecode-cache preflight passes before any timing; "
                "each timed render rechecks exact output."
            ),
            "memory": (
                "Timing samples run without tracemalloc. Separate memory samples report peak "
                "tracemalloc allocation during the isolated phase; process_peak_rss_after_bytes "
                "is cumulative process peak RSS at phase end."
            ),
            "module_closure": (
                "Loaded kida module names and unique physical Python source LOC are collected "
                "after the timed phase and do not contribute to elapsed_ms."
            ),
            "process_startup": (
                "Parent-observed wall time for an isolated -I -S interpreter executing only "
                "a minimal resource.getrusage RSS probe."
            ),
            "phase_definitions": {
                "import_kida": "Clean-process import kida; excludes process startup.",
                "import_environment": (
                    "Clean-process `from kida import Environment`; excludes process startup."
                ),
                "environment_construction": (
                    "Environment() after imports; excludes import and process startup."
                ),
                "first_source_render": (
                    "Environment.from_string plus first render; excludes imports/environment construction."
                ),
                "first_bytecode_cache_render": (
                    "First get_template/render in a clean process against an untimed prepopulated cache."
                ),
                "warm_render": "Second render of one already compiled in-process template.",
            },
            "legacy_blind_spot": (
                "benchmark_cold_start.py and test_benchmark_cold_start.py start their timers "
                "after importing Kida, so their cold-start figures exclude import cost."
            ),
            "template_source": TEMPLATE_SOURCE,
            "expected_output_sha256": hashlib.sha256(EXPECTED_OUTPUT.encode()).hexdigest(),
        },
        "sanity": sanity,
        "phases": phase_reports,
    }


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--memory-samples", type=int, default=DEFAULT_MEMORY_SAMPLES)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-linux-3-14t",
        action="store_true",
        help="Fail unless running CPython 3.14 free-threaded on Linux with the GIL disabled.",
    )
    parser.add_argument("--worker", choices=(*PHASES[1:], "preflight"), help=argparse.SUPPRESS)
    parser.add_argument("--template-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--cache-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--measure-memory", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.worker is not None:
        if args.worker == "preflight":
            if args.template_dir is None or args.cache_dir is None:
                raise ValueError("preflight requires template and cache directories")
            result = _worker_preflight(args.template_dir, args.cache_dir)
        else:
            result = _worker_phase(
                args.worker,
                template_dir=args.template_dir,
                cache_dir=args.cache_dir,
                measure_memory=args.measure_memory,
            )
        print(json.dumps(result, sort_keys=True))
        return 0

    report = build_report(
        warmups=args.warmups,
        samples=args.samples,
        memory_samples=args.memory_samples,
        require_linux_3_14t=args.require_linux_3_14t,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(args.output)
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
