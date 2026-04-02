"""Tests for SARIF converter."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from kida.utils.sarif import sarif_to_dict

if TYPE_CHECKING:
    from pathlib import Path

# =============================================================================
# Fixtures
# =============================================================================

BASIC_SARIF = {
    "version": "2.1.0",
    "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
    "runs": [
        {
            "tool": {"driver": {"name": "semgrep", "version": "1.50.0"}},
            "results": [
                {
                    "ruleId": "python.lang.security.audit.exec-detected",
                    "level": "error",
                    "message": {"text": "Detected use of exec()"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/app.py"},
                                "region": {"startLine": 42},
                            }
                        }
                    ],
                },
                {
                    "ruleId": "python.lang.best-practice.open-never-closed",
                    "level": "warning",
                    "message": {"text": "File opened but never closed"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/utils.py"},
                                "region": {"startLine": 10},
                            }
                        }
                    ],
                },
                {
                    "ruleId": "python.lang.style.long-line",
                    "level": "note",
                    "message": {"text": "Line exceeds 120 characters"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/models.py"},
                                "region": {"startLine": 88},
                            }
                        }
                    ],
                },
            ],
        }
    ],
}

EMPTY_SARIF = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "eslint"}},
            "results": [],
        }
    ],
}

NO_RUNS_SARIF = {
    "version": "2.1.0",
    "runs": [],
}

MISSING_LOCATION_SARIF = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "codeql"}},
            "results": [
                {
                    "ruleId": "js/xss",
                    "level": "error",
                    "message": {"text": "XSS vulnerability"},
                    "locations": [],
                }
            ],
        }
    ],
}

MULTI_RUN_SARIF = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "semgrep"}},
            "results": [
                {
                    "ruleId": "rule-1",
                    "level": "error",
                    "message": {"text": "Error from semgrep"},
                    "locations": [],
                }
            ],
        },
        {
            "tool": {"driver": {"name": "codeql"}},
            "results": [
                {
                    "ruleId": "rule-2",
                    "level": "warning",
                    "message": {"text": "Warning from codeql"},
                    "locations": [],
                }
            ],
        },
    ],
}

NONE_LEVEL_SARIF = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "tool"}},
            "results": [
                {
                    "ruleId": "info-only",
                    "level": "none",
                    "message": {"text": "Informational only"},
                    "locations": [],
                }
            ],
        }
    ],
}


@pytest.fixture
def sarif_file(tmp_path):
    """Return a helper that writes SARIF data to a temp file."""

    def _write(data: dict) -> Path:
        path = tmp_path / "input.sarif"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return _write


# =============================================================================
# Tests
# =============================================================================


class TestBasicSARIF:
    """Test parsing standard SARIF output."""

    def test_tool_name(self, sarif_file):
        result = sarif_to_dict(sarif_file(BASIC_SARIF))
        assert result["tool"] == "semgrep"

    def test_version(self, sarif_file):
        result = sarif_to_dict(sarif_file(BASIC_SARIF))
        assert result["version"] == "2.1.0"

    def test_summary(self, sarif_file):
        result = sarif_to_dict(sarif_file(BASIC_SARIF))
        s = result["summary"]
        assert s["total"] == 3
        assert s["errors"] == 1
        assert s["warnings"] == 1
        assert s["notes"] == 1

    def test_results(self, sarif_file):
        result = sarif_to_dict(sarif_file(BASIC_SARIF))
        assert len(result["results"]) == 3

    def test_error_result(self, sarif_file):
        result = sarif_to_dict(sarif_file(BASIC_SARIF))
        r = result["results"][0]
        assert r["rule_id"] == "python.lang.security.audit.exec-detected"
        assert r["level"] == "error"
        assert r["file"] == "src/app.py"
        assert r["line"] == 42
        assert "exec()" in r["message"]

    def test_warning_result(self, sarif_file):
        result = sarif_to_dict(sarif_file(BASIC_SARIF))
        r = result["results"][1]
        assert r["level"] == "warning"
        assert r["file"] == "src/utils.py"

    def test_note_result(self, sarif_file):
        result = sarif_to_dict(sarif_file(BASIC_SARIF))
        r = result["results"][2]
        assert r["level"] == "note"
        assert r["line"] == 88


class TestEmptySARIF:
    """Test empty results."""

    def test_empty_results(self, sarif_file):
        result = sarif_to_dict(sarif_file(EMPTY_SARIF))
        assert result["summary"]["total"] == 0
        assert result["results"] == []
        assert result["tool"] == "eslint"


class TestNoRunsSARIF:
    """Test SARIF with no runs."""

    def test_no_runs(self, sarif_file):
        result = sarif_to_dict(sarif_file(NO_RUNS_SARIF))
        assert result["summary"]["total"] == 0
        assert result["tool"] == "unknown"


class TestMissingLocationSARIF:
    """Test results with missing location data."""

    def test_missing_location(self, sarif_file):
        result = sarif_to_dict(sarif_file(MISSING_LOCATION_SARIF))
        r = result["results"][0]
        assert r["file"] == ""
        assert r["line"] == 0
        assert r["level"] == "error"


class TestMultiRunSARIF:
    """Test SARIF with multiple runs."""

    def test_aggregates_results(self, sarif_file):
        result = sarif_to_dict(sarif_file(MULTI_RUN_SARIF))
        assert result["summary"]["total"] == 2
        assert result["summary"]["errors"] == 1
        assert result["summary"]["warnings"] == 1

    def test_multiple_tool_names(self, sarif_file):
        result = sarif_to_dict(sarif_file(MULTI_RUN_SARIF))
        assert result["tool"] == "semgrep, codeql"


class TestNoneLevelSARIF:
    """Test SARIF results with level=none."""

    def test_none_not_counted_as_note(self, sarif_file):
        result = sarif_to_dict(sarif_file(NONE_LEVEL_SARIF))
        assert result["summary"]["total"] == 1
        assert result["summary"]["notes"] == 0
        assert result["summary"]["errors"] == 0
        assert result["summary"]["warnings"] == 0
