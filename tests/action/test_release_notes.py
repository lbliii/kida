"""Offline tests for the composite Action release-note collector."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from action_support.release_notes import (
    CollectorConfig,
    CollectorError,
    CommandResult,
    ReleaseData,
    _resolve_base_ref,
    collect_release_data,
    validate_release_data,
)

FIXTURES = Path(__file__).parent / "fixtures"


class FixtureRunner:
    """Deterministic command boundary backed by checked-in fixtures."""

    def __init__(self, *, malformed_github: bool = False, divergent: bool = False) -> None:
        self.pages = json.loads((FIXTURES / "github_pr_pages.json").read_text(encoding="utf-8"))
        self.malformed_github = malformed_github
        self.divergent = divergent
        self.graphql_cursors: list[str] = []

    def __call__(self, args) -> CommandResult:
        command = tuple(args)
        if command[:3] == ("gh", "repo", "view"):
            return CommandResult(0, '{"defaultBranchRef":{"name":"main"}}')
        if command[:3] == ("gh", "api", "graphql"):
            if self.malformed_github:
                malformed = (FIXTURES / "malformed_github_response.txt").read_text(encoding="utf-8")
                return CommandResult(0, malformed)
            cursor = next(
                (value.removeprefix("after=") for value in command if value.startswith("after=")),
                "",
            )
            self.graphql_cursors.append(cursor)
            page = self.pages[1] if cursor else self.pages[0]
            return CommandResult(0, json.dumps(page))
        if command[:4] == ("git", "log", "-1", "--format=%aI"):
            ref = command[4]
            dates = {
                "v1.0.0": "2026-07-01T00:00:00+00:00\n",
                "v1.1.0": "2026-07-10T00:00:00+00:00\n",
                "root-sha": "2026-06-01T00:00:00+00:00\n",
            }
            if ref not in dates:
                return CommandResult(128, stderr=f"unknown revision {ref}")
            return CommandResult(0, dates[ref])
        if command[:3] == ("git", "merge-base", "--is-ancestor"):
            return CommandResult(1 if self.divergent else 0)
        if command[:3] == ("git", "log", "--format=%H%x09%s%x09%an"):
            return CommandResult(
                0,
                "merge-10\tfeat: merged\tAlice\n"
                "merge-11\tdeps: merged\tDependabot\n"
                "merge-12\tdocs: merged\tBob\n"
                "direct-1\tdocs: direct note\tDana\n",
            )
        if command[:3] == ("git", "diff", "--shortstat"):
            return CommandResult(0, " 4 files changed, 20 insertions(+), 3 deletions(-)\n")
        if command[:3] == ("git", "diff", "--diff-filter=A"):
            return CommandResult(0, "docs/new.md\n")
        if command[:2] == ("git", "tag"):
            return CommandResult(0, "v1.1.0\nv1.0.0\n")
        if command[:3] == ("git", "rev-list", "--max-parents=0"):
            return CommandResult(0, "root-sha\n")
        raise AssertionError(f"unexpected command: {command}")


def test_collect_release_data_matches_report_contract_fixture(tmp_path: Path) -> None:
    """Markers, issues, dependencies, direct commits, and placeholders survive extraction."""
    baseline = tmp_path / "benchmarks" / "render" / "linux_baseline.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text("{}", encoding="utf-8")
    runner = FixtureRunner()

    data = collect_release_data(
        CollectorConfig(
            repository="owner/repo",
            base_ref="v1.0.0",
            head_ref="v1.1.0",
            repository_root=tmp_path,
        ),
        runner=runner,
        today=lambda: date(2026, 7, 8),
    )
    expected = cast(
        "ReleaseData",
        json.loads((FIXTURES / "expected_release_data.json").read_text(encoding="utf-8")),
    )

    assert data == expected
    assert runner.graphql_cursors == ["", "cursor-2"]


def test_malformed_github_json_fails_with_actionable_context(tmp_path: Path) -> None:
    """A successful command with malformed JSON is never treated as an empty release."""
    with pytest.raises(CollectorError, match="gh api graphql returned malformed JSON"):
        collect_release_data(
            CollectorConfig(
                repository="owner/repo",
                base_ref="v1.0.0",
                head_ref="v1.1.0",
                repository_root=tmp_path,
            ),
            runner=FixtureRunner(malformed_github=True),
        )


def test_report_contract_validation_rejects_nested_shape_drift() -> None:
    """Collector output is checked before a report template can consume it."""
    payload = json.loads((FIXTURES / "expected_release_data.json").read_text(encoding="utf-8"))
    payload["pull_requests"][0].pop("release_note")

    with pytest.raises(CollectorError, match="keys do not match the report contract"):
        validate_release_data(cast("ReleaseData", payload))


def test_missing_ref_and_divergent_range_fail_before_github_access(tmp_path: Path) -> None:
    """Bad release ranges identify the offending refs and exit unambiguously."""
    with pytest.raises(CollectorError, match="unknown revision missing"):
        collect_release_data(
            CollectorConfig("owner/repo", "v1.1.0", "missing", tmp_path),
            runner=FixtureRunner(),
        )

    with pytest.raises(CollectorError, match="is not an ancestor"):
        collect_release_data(
            CollectorConfig("owner/repo", "v1.1.0", "v1.0.0", tmp_path),
            runner=FixtureRunner(divergent=True),
        )


def test_base_ref_auto_detection_and_root_fallback_are_diagnosable() -> None:
    """Tag selection skips the head tag and missing tags emit a stable warning."""
    config = CollectorConfig("owner/repo", "v1.1.0")
    runner = FixtureRunner()
    warnings: list[str] = []

    assert _resolve_base_ref(config, runner, warnings.append) == "v1.0.0"
    assert warnings == []

    class NoTagsRunner(FixtureRunner):
        def __call__(self, args) -> CommandResult:
            if tuple(args)[:2] == ("git", "tag"):
                return CommandResult(0, "")
            return super().__call__(args)

    assert _resolve_base_ref(config, NoTagsRunner(), warnings.append) == "root-sha"
    assert warnings == ["Could not auto-detect a previous version tag; using the first commit."]
