"""LCOV coverage data to dict converter.

Stdlib-only parser for LCOV ``.info`` files produced by lcov, geninfo,
nyc/istanbul, go tool cover, and similar tools.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def lcov_to_dict(path: str | Path) -> dict[str, Any]:
    """Parse an LCOV file and return a dict matching coverage-report.md's schema.

    Args:
        path: Path to the LCOV ``.info`` file.

    Returns:
        Dict with ``totals`` and ``files`` keys, compatible with the
        existing ``coverage-report.md`` template::

            {
                "totals": {
                    "percent_covered": float,
                    "lines_found": int,
                    "lines_hit": int,
                },
                "files": {
                    "path/to/file.py": {
                        "summary": {
                            "percent_covered": float,
                            "lines_found": int,
                            "lines_hit": int,
                        }
                    }
                }
            }
    """
    text = Path(path).read_text(encoding="utf-8")

    files: dict[str, dict[str, Any]] = {}
    total_found = 0
    total_hit = 0

    current_file: str | None = None
    file_found = 0
    file_hit = 0

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("SF:"):
            current_file = line[3:]
            file_found = 0
            file_hit = 0
        elif line.startswith("LF:"):
            file_found = int(line[3:])
        elif line.startswith("LH:"):
            file_hit = int(line[3:])
        elif line == "end_of_record":
            if current_file is not None:
                pct = (file_hit / file_found * 100) if file_found > 0 else 100.0
                files[current_file] = {
                    "summary": {
                        "percent_covered": round(pct, 2),
                        "lines_found": file_found,
                        "lines_hit": file_hit,
                    }
                }
                total_found += file_found
                total_hit += file_hit
            current_file = None

    # Flush the last file if the LCOV input is missing a trailing end_of_record.
    if current_file is not None:
        pct = (file_hit / file_found * 100) if file_found > 0 else 100.0
        files[current_file] = {
            "summary": {
                "percent_covered": round(pct, 2),
                "lines_found": file_found,
                "lines_hit": file_hit,
            }
        }
        total_found += file_found
        total_hit += file_hit

    total_pct = (total_hit / total_found * 100) if total_found > 0 else 100.0

    return {
        "totals": {
            "percent_covered": round(total_pct, 2),
            "lines_found": total_found,
            "lines_hit": total_hit,
        },
        "files": files,
    }


__all__ = [
    "lcov_to_dict",
]
