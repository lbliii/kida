"""SARIF (Static Analysis Results Interchange Format) to dict converter.

Stdlib-only converter for SARIF v2.1.0 JSON files. Handles output from
CodeQL, ESLint, Semgrep, Trivy, and other SARIF-producing tools.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def sarif_to_dict(path: str | Path) -> dict[str, Any]:
    """Parse a SARIF JSON file and return a normalized dict.

    Args:
        path: Path to the SARIF JSON file.

    Returns:
        Dict with ``tool``, ``version``, ``summary``, and ``results`` keys::

            {
                "tool": str,
                "version": str,
                "summary": {
                    "total": int,
                    "errors": int,
                    "warnings": int,
                    "notes": int,
                },
                "results": [
                    {
                        "rule_id": str,
                        "level": str,
                        "message": str,
                        "file": str,
                        "line": int,
                    },
                    ...
                ],
            }
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    version = raw.get("version", "")
    runs = raw.get("runs", [])

    if not runs:
        return _empty_result(version)

    results: list[dict[str, Any]] = []
    errors = 0
    warnings = 0
    notes = 0
    tool_names: dict[str, None] = {}

    for run in runs:
        name = run.get("tool", {}).get("driver", {}).get("name")
        if name:
            tool_names.setdefault(name, None)

        for r in run.get("results", []):
            level = r.get("level", "warning")
            message = r.get("message", {}).get("text", "")
            rule_id = r.get("ruleId", "")

            # Extract first physical location
            file = ""
            line = 0
            locations = r.get("locations", [])
            if locations:
                phys = locations[0].get("physicalLocation", {})
                artifact = phys.get("artifactLocation", {})
                file = artifact.get("uri", "")
                region = phys.get("region", {})
                line = region.get("startLine", 0)

            if level == "error":
                errors += 1
            elif level == "warning":
                warnings += 1
            elif level == "note":
                notes += 1
            # "none" level results are counted in total but not as problems

            results.append(
                {
                    "rule_id": rule_id,
                    "level": level,
                    "message": message,
                    "file": file,
                    "line": line,
                }
            )

    if not tool_names:
        tool_name = "unknown"
    elif len(tool_names) == 1:
        tool_name = next(iter(tool_names))
    else:
        tool_name = ", ".join(tool_names)

    total = len(results)

    return {
        "tool": tool_name,
        "version": version,
        "summary": {
            "total": total,
            "errors": errors,
            "warnings": warnings,
            "notes": notes,
        },
        "results": results,
    }


def _empty_result(version: str = "") -> dict[str, Any]:
    """Return an empty result structure."""
    return {
        "tool": "unknown",
        "version": version,
        "summary": {
            "total": 0,
            "errors": 0,
            "warnings": 0,
            "notes": 0,
        },
        "results": [],
    }


__all__ = [
    "sarif_to_dict",
]
