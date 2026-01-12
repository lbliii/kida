"""Tests for worker auto-tuning utilities."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from kida.utils.workers import (
    Environment,
    WorkloadProfile,
    WorkloadType,
    detect_environment,
    get_optimal_workers,
    get_profile,
    is_free_threading_enabled,
    should_parallelize,
)


class TestEnvironmentDetection:
    """Tests for detect_environment()."""

    def test_default_is_local(self) -> None:
        """Without CI indicators, default to LOCAL."""
        with mock.patch.dict(os.environ, {}, clear=True):
            # Clear all CI indicators
            for key in ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "KIDA_ENV"]:
                os.environ.pop(key, None)
            assert detect_environment() == Environment.LOCAL

    def test_explicit_kida_env_ci(self) -> None:
        """KIDA_ENV=ci overrides all."""
        with mock.patch.dict(os.environ, {"KIDA_ENV": "ci"}):
            assert detect_environment() == Environment.CI

    def test_explicit_kida_env_production(self) -> None:
        """KIDA_ENV=production overrides all."""
        with mock.patch.dict(os.environ, {"KIDA_ENV": "production"}):
            assert detect_environment() == Environment.PRODUCTION

    def test_explicit_kida_env_local(self) -> None:
        """KIDA_ENV=local overrides CI detection."""
        with mock.patch.dict(os.environ, {"KIDA_ENV": "local", "CI": "true"}):
            assert detect_environment() == Environment.LOCAL

    def test_github_actions_detection(self) -> None:
        """GITHUB_ACTIONS triggers CI environment."""
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            os.environ.pop("KIDA_ENV", None)
            assert detect_environment() == Environment.CI

    def test_gitlab_ci_detection(self) -> None:
        """GITLAB_CI triggers CI environment."""
        with mock.patch.dict(os.environ, {"GITLAB_CI": "true"}, clear=True):
            os.environ.pop("KIDA_ENV", None)
            assert detect_environment() == Environment.CI

    def test_generic_ci_detection(self) -> None:
        """CI=true triggers CI environment."""
        with mock.patch.dict(os.environ, {"CI": "true"}, clear=True):
            os.environ.pop("KIDA_ENV", None)
            assert detect_environment() == Environment.CI


class TestGetOptimalWorkers:
    """Tests for get_optimal_workers()."""

    def test_user_override_takes_precedence(self) -> None:
        """config_override bypasses all auto-tuning."""
        result = get_optimal_workers(100, config_override=16)
        assert result == 16

    def test_zero_override_is_ignored(self) -> None:
        """config_override=0 falls back to auto-tuning."""
        result = get_optimal_workers(100, config_override=0)
        assert result != 0  # Auto-tuned value

    def test_negative_override_is_ignored(self) -> None:
        """Negative override falls back to auto-tuning."""
        result = get_optimal_workers(100, config_override=-1)
        assert result >= 1

    def test_ci_caps_workers(self) -> None:
        """CI environment caps worker count."""
        result = get_optimal_workers(
            1000,
            workload_type=WorkloadType.RENDER,
            environment=Environment.CI,
        )
        assert result <= 2  # CI profile caps at 2

    def test_never_more_workers_than_tasks(self) -> None:
        """Worker count capped at task count."""
        result = get_optimal_workers(2, environment=Environment.PRODUCTION)
        assert result <= 2

    def test_always_at_least_one_worker(self) -> None:
        """Always returns at least 1 worker."""
        result = get_optimal_workers(0)
        assert result >= 1

    def test_task_weight_increases_effective_tasks(self) -> None:
        """task_weight multiplies task count for scheduling."""
        # With 3 tasks and weight 2.0, effective = 6 tasks
        light = get_optimal_workers(3, task_weight=1.0, environment=Environment.LOCAL)
        heavy = get_optimal_workers(3, task_weight=2.0, environment=Environment.LOCAL)
        # Heavy should allow more workers (but both capped by task count)
        assert heavy >= light

    def test_render_workload_uses_render_profile(self) -> None:
        """RENDER workload uses appropriate profile."""
        profile = get_profile(WorkloadType.RENDER, Environment.LOCAL)
        assert profile.parallel_threshold == 10
        assert profile.max_workers >= 2

    def test_compile_workload_more_conservative(self) -> None:
        """COMPILE workload is more conservative than RENDER."""
        render_profile = get_profile(WorkloadType.RENDER, Environment.LOCAL)
        compile_profile = get_profile(WorkloadType.COMPILE, Environment.LOCAL)
        assert compile_profile.parallel_threshold >= render_profile.parallel_threshold

    def test_io_bound_allows_more_workers(self) -> None:
        """IO_BOUND workload allows more concurrent workers."""
        io_profile = get_profile(WorkloadType.IO_BOUND, Environment.PRODUCTION)
        render_profile = get_profile(WorkloadType.RENDER, Environment.PRODUCTION)
        assert io_profile.max_workers >= render_profile.max_workers


class TestShouldParallelize:
    """Tests for should_parallelize()."""

    def test_below_threshold_returns_false(self) -> None:
        """Tasks below parallel_threshold return False."""
        # Render threshold is 10
        assert should_parallelize(5, workload_type=WorkloadType.RENDER) is False
        assert should_parallelize(9, workload_type=WorkloadType.RENDER) is False

    def test_above_threshold_returns_true(self) -> None:
        """Tasks above parallel_threshold return True."""
        assert should_parallelize(15, workload_type=WorkloadType.RENDER) is True
        assert should_parallelize(100, workload_type=WorkloadType.RENDER) is True

    def test_work_estimate_overrides_task_count(self) -> None:
        """Small work estimates disable parallelization."""
        # Even with many tasks, small work estimate → False
        assert should_parallelize(100, total_work_estimate=1000) is False

    def test_large_work_estimate_allows_parallel(self) -> None:
        """Large work estimates allow parallelization."""
        assert should_parallelize(100, total_work_estimate=50000) is True


class TestGetProfile:
    """Tests for get_profile()."""

    def test_returns_workload_profile(self) -> None:
        """Returns WorkloadProfile dataclass."""
        profile = get_profile(WorkloadType.RENDER)
        assert isinstance(profile, WorkloadProfile)
        assert profile.parallel_threshold > 0
        assert profile.min_workers >= 1
        assert profile.max_workers >= profile.min_workers

    def test_profiles_exist_for_all_combinations(self) -> None:
        """All workload/environment combinations have profiles."""
        for workload in WorkloadType:
            for env in Environment:
                profile = get_profile(workload, env)
                assert profile is not None


class TestIsFreeThreadingEnabled:
    """Tests for is_free_threading_enabled()."""

    def test_returns_bool(self) -> None:
        """Returns a boolean value."""
        result = is_free_threading_enabled()
        assert isinstance(result, bool)

    def test_consistent_result(self) -> None:
        """Multiple calls return same result (cached)."""
        first = is_free_threading_enabled()
        second = is_free_threading_enabled()
        assert first == second


class TestFreeThreadingIntegration:
    """Integration tests for free-threading behavior."""

    @pytest.mark.skipif(
        not is_free_threading_enabled(),
        reason="Requires free-threaded Python",
    )
    def test_free_threading_increases_workers(self) -> None:
        """Free-threading multiplier increases worker count."""
        # This test only runs on Python 3.14t with GIL disabled
        profile = get_profile(WorkloadType.RENDER, Environment.LOCAL)
        assert profile.free_threading_multiplier > 1.0

    def test_profiles_have_free_threading_multiplier(self) -> None:
        """All profiles have free_threading_multiplier defined."""
        for workload in WorkloadType:
            for env in Environment:
                profile = get_profile(workload, env)
                assert hasattr(profile, "free_threading_multiplier")
                assert profile.free_threading_multiplier >= 1.0


class TestEdgeCases:
    """Edge case tests."""

    def test_single_task(self) -> None:
        """Single task returns 1 worker."""
        result = get_optimal_workers(1)
        assert result == 1

    def test_large_task_count(self) -> None:
        """Large task count doesn't exceed max_workers."""
        profile = get_profile(WorkloadType.RENDER, Environment.PRODUCTION)
        result = get_optimal_workers(
            10000,
            workload_type=WorkloadType.RENDER,
            environment=Environment.PRODUCTION,
        )
        assert result <= profile.max_workers

    def test_fractional_cpu_count(self) -> None:
        """Handles fractional CPU calculations correctly."""
        # Mock 3 CPUs with 0.5 fraction = 1.5 → 1 (but min_workers overrides)
        with mock.patch("os.cpu_count", return_value=3):
            result = get_optimal_workers(
                100,
                workload_type=WorkloadType.RENDER,
                environment=Environment.LOCAL,
            )
            assert result >= 2  # min_workers is 2
