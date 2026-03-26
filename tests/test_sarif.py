"""Tests for SARIF converter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from kida.utils.sarif import sarif_to_dict

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


def _write_sarif(data: dict) -> Path:
    """Write SARIF JSON to a temp file and return path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
        json.dump(data, f)
    return Path(f.name)


# =============================================================================
# Tests
# =============================================================================


class TestBasicSARIF:
    """Test parsing standard SARIF output."""

    def test_tool_name(self):
        path = _write_sarif(BASIC_SARIF)
        result = sarif_to_dict(path)
        assert result["tool"] == "semgrep"

    def test_version(self):
        path = _write_sarif(BASIC_SARIF)
        result = sarif_to_dict(path)
        assert result["version"] == "2.1.0"

    def test_summary(self):
        path = _write_sarif(BASIC_SARIF)
        result = sarif_to_dict(path)
        s = result["summary"]
        assert s["total"] == 3
        assert s["errors"] == 1
        assert s["warnings"] == 1
        assert s["notes"] == 1

    def test_results(self):
        path = _write_sarif(BASIC_SARIF)
        result = sarif_to_dict(path)
        assert len(result["results"]) == 3

    def test_error_result(self):
        path = _write_sarif(BASIC_SARIF)
        result = sarif_to_dict(path)
        r = result["results"][0]
        assert r["rule_id"] == "python.lang.security.audit.exec-detected"
        assert r["level"] == "error"
        assert r["file"] == "src/app.py"
        assert r["line"] == 42
        assert "exec()" in r["message"]

    def test_warning_result(self):
        path = _write_sarif(BASIC_SARIF)
        result = sarif_to_dict(path)
        r = result["results"][1]
        assert r["level"] == "warning"
        assert r["file"] == "src/utils.py"

    def test_note_result(self):
        path = _write_sarif(BASIC_SARIF)
        result = sarif_to_dict(path)
        r = result["results"][2]
        assert r["level"] == "note"
        assert r["line"] == 88


class TestEmptySARIF:
    """Test empty results."""

    def test_empty_results(self):
        path = _write_sarif(EMPTY_SARIF)
        result = sarif_to_dict(path)
        assert result["summary"]["total"] == 0
        assert result["results"] == []
        assert result["tool"] == "eslint"


class TestNoRunsSARIF:
    """Test SARIF with no runs."""

    def test_no_runs(self):
        path = _write_sarif(NO_RUNS_SARIF)
        result = sarif_to_dict(path)
        assert result["summary"]["total"] == 0
        assert result["tool"] == "unknown"


class TestMissingLocationSARIF:
    """Test results with missing location data."""

    def test_missing_location(self):
        path = _write_sarif(MISSING_LOCATION_SARIF)
        result = sarif_to_dict(path)
        r = result["results"][0]
        assert r["file"] == ""
        assert r["line"] == 0
        assert r["level"] == "error"
