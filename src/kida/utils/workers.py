"""
Worker pool auto-tuning utilities for free-threaded Python.

Provides workload-aware worker count calculation for ThreadPoolExecutor usage.
Calibrated for Python 3.14t (free-threading) where CPU-bound template rendering
can achieve true parallelism without GIL contention.

Key Features:
- Environment detection (CI vs local vs production)
- Free-threading detection (GIL status)
- Workload type profiles calibrated for no-GIL execution
- Template complexity estimation for optimal scheduling

Example:
    >>> from kida.utils.workers import get_optimal_workers, should_parallelize
    >>> contexts = [{"name": f"User {i}"} for i in range(100)]
    >>> if should_parallelize(len(contexts)):
    ...     workers = get_optimal_workers(len(contexts))
    ...     with ThreadPoolExecutor(max_workers=workers) as executor:
    ...         results = list(executor.map(template.render, contexts))

Note:
Profiles are calibrated for free-threaded Python (3.14t+).
On GIL-enabled Python, CPU-bound parallelism is limited.

"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.template import Template


class WorkloadType(Enum):
    """Workload characteristics for auto-tuning.

    On free-threaded Python, CPU-bound work can now parallelize effectively.
    This changes optimal worker counts compared to GIL-enabled Python.

    Attributes:
        RENDER: Template rendering (CPU-bound, string operations).
            Primary workload for Kida. Benefits significantly from free-threading.
        COMPILE: Template compilation/parsing (CPU-bound, AST operations).
            Moderate parallelism benefit due to shared cache access.
        IO_BOUND: File loading, network operations.
            Can use more workers as threads wait on I/O.

    """

    RENDER = "render"
    COMPILE = "compile"
    IO_BOUND = "io_bound"


class Environment(Enum):
    """Execution environment for tuning profiles.

    Different environments have different resource constraints:

    Attributes:
        CI: Constrained CI runner (typically 2-4 vCPU).
            Use minimal workers to avoid resource contention.
        LOCAL: Developer machine (typically 8-16 cores).
            Use moderate workers for good performance.
        PRODUCTION: Server deployment (16+ cores).
            Can use more workers for high throughput.

    """

    CI = "ci"
    LOCAL = "local"
    PRODUCTION = "production"


@dataclass(frozen=True)
class WorkloadProfile:
    """Tuning profile for a workload type.

    Attributes:
        parallel_threshold: Minimum tasks before parallelizing.
            Below this, thread overhead exceeds benefit.
        min_workers: Floor for worker count.
        max_workers: Ceiling for worker count.
        cpu_fraction: Fraction of cores to use (0.0-1.0).
        free_threading_multiplier: Extra scaling when GIL is disabled.

    """

    parallel_threshold: int
    min_workers: int
    max_workers: int
    cpu_fraction: float
    free_threading_multiplier: float = 1.0


# Calibrated profiles for free-threaded Python 3.14t
# Based on benchmark data: Kida scales well to 4 workers, degrades at 8
# These profiles are more aggressive than Bengal's GIL-constrained profiles
_PROFILES: dict[tuple[WorkloadType, Environment], WorkloadProfile] = {
    # Rendering workloads (CPU-bound but parallelizable on free-threaded)
    # Kida benchmarks show best scaling at 2-4 workers
    (WorkloadType.RENDER, Environment.CI): WorkloadProfile(
        parallel_threshold=10,
        min_workers=2,
        max_workers=2,
        cpu_fraction=1.0,
        free_threading_multiplier=1.0,
    ),
    (WorkloadType.RENDER, Environment.LOCAL): WorkloadProfile(
        parallel_threshold=10,
        min_workers=2,
        max_workers=4,
        cpu_fraction=0.5,
        free_threading_multiplier=1.5,  # Free-threading allows more parallelism
    ),
    (WorkloadType.RENDER, Environment.PRODUCTION): WorkloadProfile(
        parallel_threshold=10,
        min_workers=2,
        max_workers=8,
        cpu_fraction=0.5,
        free_threading_multiplier=1.5,
    ),
    # Compilation workloads (less parallelizable due to shared template cache)
    (WorkloadType.COMPILE, Environment.CI): WorkloadProfile(
        parallel_threshold=20,
        min_workers=1,
        max_workers=2,
        cpu_fraction=0.5,
        free_threading_multiplier=1.0,
    ),
    (WorkloadType.COMPILE, Environment.LOCAL): WorkloadProfile(
        parallel_threshold=20,
        min_workers=2,
        max_workers=4,
        cpu_fraction=0.5,
        free_threading_multiplier=1.0,
    ),
    (WorkloadType.COMPILE, Environment.PRODUCTION): WorkloadProfile(
        parallel_threshold=20,
        min_workers=2,
        max_workers=6,
        cpu_fraction=0.5,
        free_threading_multiplier=1.0,
    ),
    # I/O-bound workloads (template loading from disk/network)
    (WorkloadType.IO_BOUND, Environment.CI): WorkloadProfile(
        parallel_threshold=20,
        min_workers=2,
        max_workers=4,
        cpu_fraction=1.0,
        free_threading_multiplier=1.0,
    ),
    (WorkloadType.IO_BOUND, Environment.LOCAL): WorkloadProfile(
        parallel_threshold=20,
        min_workers=2,
        max_workers=8,
        cpu_fraction=0.75,
        free_threading_multiplier=1.0,
    ),
    (WorkloadType.IO_BOUND, Environment.PRODUCTION): WorkloadProfile(
        parallel_threshold=20,
        min_workers=2,
        max_workers=12,
        cpu_fraction=0.75,
        free_threading_multiplier=1.0,
    ),
}


@lru_cache(maxsize=1)
def is_free_threading_enabled() -> bool:
    """Check if Python is running with the GIL disabled.

    Returns:
        True if running on free-threaded Python with GIL disabled.

    Example:
            >>> is_free_threading_enabled()
        True  # On Python 3.14t with PYTHON_GIL=0

    """
    # sys._is_gil_enabled() returns False when GIL is disabled
    return hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled()


def detect_environment() -> Environment:
    """
    Auto-detect execution environment for tuning.

    Detection order:
        1. Explicit KIDA_ENV environment variable
        2. CI environment variables (GitHub Actions, GitLab CI, etc.)
        3. Default to LOCAL

    Returns:
        Detected Environment enum value

    Examples:
            >>> import os
            >>> os.environ["CI"] = "true"
            >>> detect_environment()
        <Environment.CI: 'ci'>

            >>> os.environ["KIDA_ENV"] = "production"
            >>> detect_environment()
        <Environment.PRODUCTION: 'production'>

    """
    # Explicit override takes highest priority
    env_value = os.environ.get("KIDA_ENV", "").lower()
    if env_value == "ci":
        return Environment.CI
    if env_value == "production":
        return Environment.PRODUCTION
    if env_value == "local":
        return Environment.LOCAL

    # CI detection (common CI environment variables)
    ci_indicators = [
        "CI",  # Generic CI
        "GITHUB_ACTIONS",  # GitHub Actions
        "GITLAB_CI",  # GitLab CI
        "CIRCLECI",  # CircleCI
        "TRAVIS",  # Travis CI
        "JENKINS_URL",  # Jenkins
        "BUILDKITE",  # Buildkite
        "CODEBUILD_BUILD_ID",  # AWS CodeBuild
        "AZURE_PIPELINES",  # Azure Pipelines
        "TF_BUILD",  # Azure DevOps
    ]
    for indicator in ci_indicators:
        if os.environ.get(indicator):
            return Environment.CI

    return Environment.LOCAL


def get_optimal_workers(
    task_count: int,
    *,
    workload_type: WorkloadType = WorkloadType.RENDER,
    environment: Environment | None = None,
    config_override: int | None = None,
    task_weight: float = 1.0,
) -> int:
    """
    Calculate optimal worker count based on workload characteristics.

    Auto-scales based on:
        - Workload type (render vs compile vs I/O)
        - Environment (CI vs local vs production)
        - Free-threading status (GIL enabled/disabled)
        - Available CPU cores (fraction based on workload)
        - Task count (no point having more workers than tasks)
        - Optional task weight for heavy/light work estimation

    Args:
        task_count: Number of tasks to process (e.g., contexts to render)
        workload_type: Type of work (RENDER, COMPILE, IO_BOUND)
        environment: Execution environment (auto-detected if None)
        config_override: User-configured value (bypasses auto-tune if > 0)
        task_weight: Multiplier for task count (>1 for heavy templates)

    Returns:
        Optimal number of worker threads (always >= 1)

    Examples:
            >>> get_optimal_workers(100, workload_type=WorkloadType.RENDER)
        4  # Local environment with free-threading

            >>> get_optimal_workers(100, workload_type=WorkloadType.COMPILE)
        2  # Compilation is less parallelizable

            >>> get_optimal_workers(5, config_override=16)
        16  # User override respected

            >>> import os
            >>> os.environ["CI"] = "true"
            >>> get_optimal_workers(100)
        2  # CI mode caps workers

    """
    # User override takes precedence
    if config_override is not None and config_override > 0:
        return config_override

    # Auto-detect environment if not specified
    if environment is None:
        environment = detect_environment()

    # Get profile for workload type + environment
    profile = _PROFILES[(workload_type, environment)]

    # Calculate CPU-based optimal
    cpu_count = os.cpu_count() or 2
    cpu_optimal = max(profile.min_workers, int(cpu_count * profile.cpu_fraction))

    # Apply free-threading multiplier if GIL is disabled
    if is_free_threading_enabled():
        cpu_optimal = int(cpu_optimal * profile.free_threading_multiplier)

    cpu_optimal = min(cpu_optimal, profile.max_workers)

    # Adjust for task count (weighted)
    effective_tasks = int(task_count * task_weight)

    # Don't use more workers than tasks, but always at least 1
    return min(cpu_optimal, max(1, effective_tasks))


def should_parallelize(
    task_count: int,
    *,
    workload_type: WorkloadType = WorkloadType.RENDER,
    environment: Environment | None = None,
    total_work_estimate: int | None = None,
) -> bool:
    """
    Determine if parallelization is worthwhile for this workload.

    Thread pool overhead (~1-2ms per task) only pays off above threshold.
    This function helps avoid the overhead for small workloads.

    Args:
        task_count: Number of tasks to process
        workload_type: Type of work
        environment: Execution environment (auto-detected if None)
        total_work_estimate: Optional size estimate (bytes of template output)

    Returns:
        True if parallelization is recommended

    Examples:
            >>> should_parallelize(5)
        False  # Below threshold

            >>> should_parallelize(100)
        True  # Above threshold

            >>> should_parallelize(100, total_work_estimate=500)
        False  # Work estimate too small (< 5KB)

    """
    if environment is None:
        environment = detect_environment()

    profile = _PROFILES[(workload_type, environment)]

    # Fast path: below task threshold
    if task_count < profile.parallel_threshold:
        return False

    # Optional: check work size estimate
    # 5KB is the threshold where thread overhead pays off
    return not (total_work_estimate is not None and total_work_estimate < 5000)


def estimate_template_weight(template: Template) -> float:
    """
    Estimate relative complexity of a template for worker scheduling.

    Heavy templates (many blocks, macros, filters) get higher weights,
    causing them to be scheduled earlier to avoid straggler effect.

    Weight factors:
        - Source size: +0.5 per 5KB above 5KB threshold
        - Block count: +0.1 per block above 3
        - Macro count: +0.2 per macro
        - Inheritance: +0.5 if extends another template

    Args:
        template: Template instance to estimate

    Returns:
        Weight multiplier (1.0 = average, >1 = heavy, <1 = light).
        Capped at 5.0 to avoid outlier distortion.

    Examples:
            >>> estimate_template_weight(simple_template)
        1.0

            >>> estimate_template_weight(complex_template)
        2.5  # Many blocks + inheritance

    """
    weight = 1.0

    # Source size factor
    source = getattr(template, "source", "")
    source_len = len(source) if source else 0

    if source_len > 5000:
        weight += (source_len - 5000) / 10000  # +0.5 per 5KB above threshold

    # Block count factor (each adds render overhead)
    block_count = source.count("{% block")
    if block_count > 3:
        weight += (block_count - 3) * 0.1

    # Macro count factor (more expensive than blocks)
    macro_count = source.count("{% macro")
    weight += macro_count * 0.2

    # Inheritance adds complexity
    if "{% extends" in source:
        weight += 0.5

    # Include statements add I/O + render overhead
    include_count = source.count("{% include")
    weight += include_count * 0.15

    return min(weight, 5.0)  # Cap at 5x to avoid outlier distortion


def order_by_complexity(
    templates: list[Template],
    *,
    descending: bool = True,
) -> list[Template]:
    """
    Order templates by estimated complexity for optimal worker utilization.

    Scheduling heavy templates first reduces the "straggler effect" where
    one slow render delays overall completion.

    Args:
        templates: List of templates to order
        descending: If True, heaviest first (default for parallel execution)

    Returns:
        Sorted list of templates (new list, does not mutate input)

    Examples:
            >>> ordered = order_by_complexity(templates)
            >>> # Heavy templates with inheritance now at front

            >>> ordered = order_by_complexity(templates, descending=False)
            >>> # Light templates first (for testing/debugging)

    """
    return sorted(
        templates,
        key=estimate_template_weight,
        reverse=descending,
    )


def get_profile(
    workload_type: WorkloadType,
    environment: Environment | None = None,
) -> WorkloadProfile:
    """
    Get the workload profile for inspection or testing.

    Args:
        workload_type: Type of work
        environment: Execution environment (auto-detected if None)

    Returns:
        WorkloadProfile with threshold and worker settings

    Examples:
            >>> profile = get_profile(WorkloadType.RENDER)
            >>> profile.parallel_threshold
        10
            >>> profile.max_workers
        4

    """
    if environment is None:
        environment = detect_environment()
    return _PROFILES[(workload_type, environment)]
