from __future__ import annotations

import json
import os
import platform
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from jinja2 import Environment as Jinja2Environment
from jinja2 import FileSystemLoader as Jinja2FileSystemLoader

from benchmarks.fixtures.context_complex import COMPLEX_CONTEXT
from benchmarks.fixtures.context_large import LARGE_CONTEXT
from benchmarks.fixtures.context_medium import MEDIUM_CONTEXT
from benchmarks.fixtures.context_small import SMALL_CONTEXT
from kida import Environment as KidaEnvironment
from kida import FileSystemLoader as KidaFileSystemLoader
from kida.bytecode_cache import BytecodeCache

try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:  # pragma: no cover
    import importlib_metadata  # type: ignore


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
JINJA2_TEMPLATE_DIR = TEMPLATE_DIR / "jinja2"
BENCHMARK_OUTPUT_DIR = BASE_DIR.parent / ".benchmarks"
BENCHMARK_OUTPUT_DIR.mkdir(exist_ok=True)


def _version(dist: str) -> str:
    try:
        return importlib_metadata.version(dist)
    except importlib_metadata.PackageNotFoundError:
        return "unknown"


def collect_environment_metadata() -> dict[str, object]:
    """Capture reproducibility metadata for each benchmark run."""
    return {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "cpu": {
            "processor": platform.processor(),
            "count": os.cpu_count(),
        },
        "kida": _version("kida"),
        "jinja2": _version("jinja2"),
    }


@pytest.fixture(scope="session")
def environment_metadata() -> dict[str, object]:
    """Write environment metadata to .benchmarks for ingestion."""
    metadata = collect_environment_metadata()
    (BENCHMARK_OUTPUT_DIR / "environment.json").write_text(json.dumps(metadata, indent=2))
    return metadata


@pytest.fixture(scope="session")
def template_loader() -> Callable[[str, str], str]:
    """Load template source for the requested engine."""

    def _load(name: str, engine: str = "kida") -> str:
        base = TEMPLATE_DIR if engine == "kida" else JINJA2_TEMPLATE_DIR
        path = base / name
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {path}")
        return path.read_text()

    return _load


@pytest.fixture(scope="session")
def kida_env(tmp_path_factory: pytest.TempPathFactory) -> KidaEnvironment:
    cache_dir = tmp_path_factory.mktemp("kida-bytecode-cache")
    loader = KidaFileSystemLoader(str(TEMPLATE_DIR))
    # Benchmarks should avoid per-render mtime/hash checks on parent templates.
    # Use auto_reload=False to prevent repeated get_source() calls under inheritance.
    return KidaEnvironment(
        loader=loader,
        bytecode_cache=BytecodeCache(cache_dir),
        auto_reload=False,
    )


@pytest.fixture(scope="session")
def jinja2_env() -> Jinja2Environment:
    loader = Jinja2FileSystemLoader(str(JINJA2_TEMPLATE_DIR))
    return Jinja2Environment(loader=loader, autoescape=True)


@pytest.fixture(scope="session")
def small_context() -> dict[str, object]:
    return SMALL_CONTEXT


@pytest.fixture(scope="session")
def medium_context() -> dict[str, object]:
    return MEDIUM_CONTEXT


@pytest.fixture(scope="session")
def large_context() -> dict[str, object]:
    return LARGE_CONTEXT


@pytest.fixture(scope="session")
def complex_context() -> dict[str, object]:
    return COMPLEX_CONTEXT
