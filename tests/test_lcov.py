"""Tests for LCOV converter."""

from __future__ import annotations

import tempfile
from pathlib import Path

from kida.utils.lcov import lcov_to_dict

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


def _write_lcov(content: str) -> Path:
    """Write LCOV content to a temp file and return path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".info", delete=False) as f:
        f.write(content)
    return Path(f.name)


# =============================================================================
# Tests
# =============================================================================


class TestBasicLCOV:
    """Test parsing standard LCOV output."""

    def test_totals(self):
        path = _write_lcov(BASIC_LCOV)
        result = lcov_to_dict(path)
        t = result["totals"]
        assert t["lines_found"] == 11
        assert t["lines_hit"] == 8
        assert t["percent_covered"] == 72.73

    def test_file_count(self):
        path = _write_lcov(BASIC_LCOV)
        result = lcov_to_dict(path)
        assert len(result["files"]) == 3

    def test_full_coverage_file(self):
        path = _write_lcov(BASIC_LCOV)
        result = lcov_to_dict(path)
        f = result["files"]["src/utils.py"]["summary"]
        assert f["percent_covered"] == 100.0
        assert f["lines_found"] == 5
        assert f["lines_hit"] == 5

    def test_partial_coverage_file(self):
        path = _write_lcov(BASIC_LCOV)
        result = lcov_to_dict(path)
        f = result["files"]["src/app.py"]["summary"]
        assert f["percent_covered"] == 75.0
        assert f["lines_found"] == 4
        assert f["lines_hit"] == 3

    def test_zero_coverage_file(self):
        path = _write_lcov(BASIC_LCOV)
        result = lcov_to_dict(path)
        f = result["files"]["src/models.py"]["summary"]
        assert f["percent_covered"] == 0.0
        assert f["lines_found"] == 2
        assert f["lines_hit"] == 0


class TestEmptyLCOV:
    """Test edge cases."""

    def test_zero_lines(self):
        path = _write_lcov(EMPTY_LCOV)
        result = lcov_to_dict(path)
        assert result["totals"]["percent_covered"] == 100.0
        assert result["totals"]["lines_found"] == 0

    def test_empty_file_coverage(self):
        path = _write_lcov(EMPTY_LCOV)
        result = lcov_to_dict(path)
        f = result["files"]["src/empty.py"]["summary"]
        assert f["percent_covered"] == 100.0


class TestSingleFileLCOV:
    """Test single file LCOV."""

    def test_single_file(self):
        path = _write_lcov(SINGLE_FILE_LCOV)
        result = lcov_to_dict(path)
        assert result["totals"]["percent_covered"] == 50.0
        assert "main.go" in result["files"]

    def test_schema_compatibility(self):
        """Verify output matches coverage-report.md template expectations."""
        path = _write_lcov(SINGLE_FILE_LCOV)
        result = lcov_to_dict(path)
        # coverage-report.md expects these exact paths
        assert "totals" in result
        assert "percent_covered" in result["totals"]
        assert "files" in result
        for fdata in result["files"].values():
            assert "summary" in fdata
            assert "percent_covered" in fdata["summary"]
