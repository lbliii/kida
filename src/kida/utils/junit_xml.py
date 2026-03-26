"""JUnit XML to dict converter for Kida CI report templates.

Stdlib-only converter using xml.etree.ElementTree. Handles both pytest
and ty JUnit XML output variants.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def junit_to_dict(path: str | Path) -> dict[str, Any]:
    """Parse a JUnit XML file and return a structured dict.

    Args:
        path: Path to the JUnit XML file.

    Returns:
        Dict with ``summary`` and ``testsuites`` keys::

            {
                "summary": {
                    "total": int,
                    "passed": int,
                    "failed": int,
                    "errors": int,
                    "skipped": int,
                    "time": float,
                },
                "testsuites": [
                    {
                        "name": str,
                        "tests": int,
                        "failures": int,
                        "errors": int,
                        "skipped": int,
                        "time": float,
                        "testcases": [
                            {
                                "name": str,
                                "classname": str,
                                "time": float,
                                "status": "passed" | "failed" | "error" | "skipped",
                                "message": str | None,
                                "text": str | None,
                            },
                            ...
                        ],
                    },
                    ...
                ],
            }
    """
    tree = ET.parse(path)
    root = tree.getroot()

    # Handle both <testsuites> and bare <testsuite> roots
    if root.tag == "testsuites":
        suites = list(root)
    elif root.tag == "testsuite":
        suites = [root]
    else:
        return _empty_result()

    total = 0
    passed = 0
    failed = 0
    errors = 0
    skipped = 0
    total_time = 0.0
    parsed_suites: list[dict[str, Any]] = []

    for suite in suites:
        suite_data = _parse_suite(suite)
        parsed_suites.append(suite_data)

        total += suite_data["tests"]
        failed += suite_data["failures"]
        errors += suite_data["errors"]
        skipped += suite_data["skipped"]
        total_time += suite_data["time"]

    passed = total - failed - errors - skipped

    return {
        "summary": {
            "total": total,
            "passed": max(0, passed),
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "time": round(total_time, 3),
        },
        "testsuites": parsed_suites,
    }


def _parse_suite(suite: ET.Element) -> dict[str, Any]:
    """Parse a single <testsuite> element."""
    tests = int(suite.get("tests", "0"))
    failures = int(suite.get("failures", "0"))
    suite_errors = int(suite.get("errors", "0"))
    suite_skipped = int(suite.get("skipped", "0"))
    time_val = float(suite.get("time", "0"))

    testcases = [_parse_testcase(tc) for tc in suite.findall("testcase")]

    return {
        "name": suite.get("name", ""),
        "tests": tests,
        "failures": failures,
        "errors": suite_errors,
        "skipped": suite_skipped,
        "time": round(time_val, 3),
        "testcases": testcases,
    }


def _parse_testcase(tc: ET.Element) -> dict[str, Any]:
    """Parse a single <testcase> element."""
    name = tc.get("name", "")
    classname = tc.get("classname", "")
    time_val = float(tc.get("time", "0"))

    # Determine status from child elements
    failure = tc.find("failure")
    error = tc.find("error")
    skip = tc.find("skipped")

    if failure is not None:
        status = "failed"
        message = failure.get("message", "")
        text = failure.text
    elif error is not None:
        status = "error"
        message = error.get("message", "")
        text = error.text
    elif skip is not None:
        status = "skipped"
        message = skip.get("message", "")
        text = skip.text
    else:
        status = "passed"
        message = None
        text = None

    return {
        "name": name,
        "classname": classname,
        "time": round(time_val, 3),
        "status": status,
        "message": message,
        "text": text,
    }


def _empty_result() -> dict[str, Any]:
    """Return an empty result structure."""
    return {
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "time": 0.0,
        },
        "testsuites": [],
    }


__all__ = [
    "junit_to_dict",
]
