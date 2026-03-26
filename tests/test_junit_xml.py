"""Tests for JUnit XML converter."""

from __future__ import annotations

import tempfile
from pathlib import Path

from kida.utils.junit_xml import junit_to_dict

# =============================================================================
# Fixtures
# =============================================================================

PYTEST_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="4" failures="1" errors="0" skipped="1" time="2.345">
    <testcase classname="tests.test_foo" name="test_pass" time="0.1" />
    <testcase classname="tests.test_foo" name="test_also_pass" time="0.2" />
    <testcase classname="tests.test_foo" name="test_fail" time="0.5">
      <failure message="AssertionError: expected 1 got 2">
Traceback:
  File "test_foo.py", line 10
    assert 1 == 2
AssertionError
      </failure>
    </testcase>
    <testcase classname="tests.test_foo" name="test_skip" time="0.0">
      <skipped message="not implemented yet" />
    </testcase>
  </testsuite>
</testsuites>
"""

TY_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuite name="ty" tests="2" failures="1" errors="0" skipped="0" time="1.0">
  <testcase name="type_check_main" classname="src.kida" time="0.5" />
  <testcase name="type_check_utils" classname="src.kida" time="0.5">
    <failure message="Type error in utils.py:10">
Expected int, got str
    </failure>
  </testcase>
</testsuite>
"""

EMPTY_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
</testsuites>
"""

ERROR_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuite name="errors" tests="1" failures="0" errors="1" skipped="0" time="0.1">
  <testcase classname="tests.test_err" name="test_boom" time="0.1">
    <error message="RuntimeError: boom">
Traceback:
  RuntimeError: boom
    </error>
  </testcase>
</testsuite>
"""


def _write_xml(content: str) -> Path:
    """Write XML content to a temp file and return path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(content)
    return Path(f.name)


# =============================================================================
# Tests
# =============================================================================


class TestPytestXML:
    """Test parsing pytest JUnit XML."""

    def test_summary(self):
        path = _write_xml(PYTEST_XML)
        result = junit_to_dict(path)
        s = result["summary"]
        assert s["total"] == 4
        assert s["passed"] == 2
        assert s["failed"] == 1
        assert s["errors"] == 0
        assert s["skipped"] == 1
        assert s["time"] == 2.345

    def test_testsuites(self):
        path = _write_xml(PYTEST_XML)
        result = junit_to_dict(path)
        assert len(result["testsuites"]) == 1
        suite = result["testsuites"][0]
        assert suite["name"] == "pytest"
        assert len(suite["testcases"]) == 4

    def test_passed_testcase(self):
        path = _write_xml(PYTEST_XML)
        result = junit_to_dict(path)
        tc = result["testsuites"][0]["testcases"][0]
        assert tc["name"] == "test_pass"
        assert tc["status"] == "passed"
        assert tc["message"] is None

    def test_failed_testcase(self):
        path = _write_xml(PYTEST_XML)
        result = junit_to_dict(path)
        tc = result["testsuites"][0]["testcases"][2]
        assert tc["name"] == "test_fail"
        assert tc["status"] == "failed"
        assert "AssertionError" in tc["message"]
        assert tc["text"] is not None

    def test_skipped_testcase(self):
        path = _write_xml(PYTEST_XML)
        result = junit_to_dict(path)
        tc = result["testsuites"][0]["testcases"][3]
        assert tc["name"] == "test_skip"
        assert tc["status"] == "skipped"
        assert "not implemented" in tc["message"]


class TestTyXML:
    """Test parsing ty JUnit XML (bare testsuite root)."""

    def test_summary(self):
        path = _write_xml(TY_XML)
        result = junit_to_dict(path)
        s = result["summary"]
        assert s["total"] == 2
        assert s["passed"] == 1
        assert s["failed"] == 1

    def test_bare_testsuite_root(self):
        path = _write_xml(TY_XML)
        result = junit_to_dict(path)
        assert len(result["testsuites"]) == 1
        assert result["testsuites"][0]["name"] == "ty"


class TestEmptyXML:
    """Test empty/minimal XML."""

    def test_empty_testsuites(self):
        path = _write_xml(EMPTY_XML)
        result = junit_to_dict(path)
        assert result["summary"]["total"] == 0
        assert result["testsuites"] == []


class TestErrorXML:
    """Test error testcases."""

    def test_error_status(self):
        path = _write_xml(ERROR_XML)
        result = junit_to_dict(path)
        tc = result["testsuites"][0]["testcases"][0]
        assert tc["status"] == "error"
        assert "boom" in tc["message"]

    def test_error_summary(self):
        path = _write_xml(ERROR_XML)
        result = junit_to_dict(path)
        assert result["summary"]["errors"] == 1
