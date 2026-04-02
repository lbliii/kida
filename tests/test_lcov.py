"""Tests for LCOV converter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kida.utils.lcov import lcov_to_dict

if TYPE_CHECKING:
    from pathlib import Path

# =============================================================================
# Fixtures
# =============================================================================

BASIC_LCOV = """\
TN:Test Suite
SF:src/app.py
DA:1,1
DA:2,1
DA:3,0
DA:4,1
LF:4
LH:3
end_of_record
SF:src/utils.py
DA:1,1
DA:2,1
DA:3,1
DA:4,1
DA:5,1
LF:5
LH:5
end_of_record
SF:src/models.py
DA:1,0
DA:2,0
LF:2
LH:0
end_of_record
"""

EMPTY_LCOV = """\
TN:
SF:src/empty.py
LF:0
LH:0
end_of_record
"""

SINGLE_FILE_LCOV = """\
SF:main.go
DA:1,5
DA:2,3
DA:3,0
DA:4,0
LF:4
LH:2
end_of_record
"""

MISSING_END_OF_RECORD_LCOV = """\
SF:src/app.py
LF:4
LH:3
"""


@pytest.fixture
def lcov_file(tmp_path):
    """Return a helper that writes LCOV data to a temp file."""

    def _write(content: str) -> Path:
        path = tmp_path / "input.info"
        path.write_text(content, encoding="utf-8")
        return path

    return _write


# =============================================================================
# Tests
# =============================================================================


class TestBasicLCOV:
    """Test parsing standard LCOV output."""

    def test_totals(self, lcov_file):
        result = lcov_to_dict(lcov_file(BASIC_LCOV))
        t = result["totals"]
        assert t["lines_found"] == 11
        assert t["lines_hit"] == 8
        assert t["percent_covered"] == 72.73

    def test_file_count(self, lcov_file):
        result = lcov_to_dict(lcov_file(BASIC_LCOV))
        assert len(result["files"]) == 3

    def test_full_coverage_file(self, lcov_file):
        result = lcov_to_dict(lcov_file(BASIC_LCOV))
        f = result["files"]["src/utils.py"]["summary"]
        assert f["percent_covered"] == 100.0
        assert f["lines_found"] == 5
        assert f["lines_hit"] == 5

    def test_partial_coverage_file(self, lcov_file):
        result = lcov_to_dict(lcov_file(BASIC_LCOV))
        f = result["files"]["src/app.py"]["summary"]
        assert f["percent_covered"] == 75.0
        assert f["lines_found"] == 4
        assert f["lines_hit"] == 3

    def test_zero_coverage_file(self, lcov_file):
        result = lcov_to_dict(lcov_file(BASIC_LCOV))
        f = result["files"]["src/models.py"]["summary"]
        assert f["percent_covered"] == 0.0
        assert f["lines_found"] == 2
        assert f["lines_hit"] == 0


class TestEmptyLCOV:
    """Test edge cases."""

    def test_zero_lines(self, lcov_file):
        result = lcov_to_dict(lcov_file(EMPTY_LCOV))
        assert result["totals"]["percent_covered"] == 100.0
        assert result["totals"]["lines_found"] == 0

    def test_empty_file_coverage(self, lcov_file):
        result = lcov_to_dict(lcov_file(EMPTY_LCOV))
        f = result["files"]["src/empty.py"]["summary"]
        assert f["percent_covered"] == 100.0


class TestSingleFileLCOV:
    """Test single file LCOV."""

    def test_single_file(self, lcov_file):
        result = lcov_to_dict(lcov_file(SINGLE_FILE_LCOV))
        assert result["totals"]["percent_covered"] == 50.0
        assert "main.go" in result["files"]

    def test_schema_compatibility(self, lcov_file):
        """Verify output matches coverage-report.md template expectations."""
        result = lcov_to_dict(lcov_file(SINGLE_FILE_LCOV))
        assert "totals" in result
        assert "percent_covered" in result["totals"]
        assert "files" in result
        for fdata in result["files"].values():
            assert "summary" in fdata
            assert "percent_covered" in fdata["summary"]


class TestMissingEndOfRecord:
    """Test LCOV input without trailing end_of_record."""

    def test_flushes_last_file(self, lcov_file):
        result = lcov_to_dict(lcov_file(MISSING_END_OF_RECORD_LCOV))
        assert "src/app.py" in result["files"]
        assert result["totals"]["lines_found"] == 4
        assert result["totals"]["lines_hit"] == 3
