"""Template coverage collection and reporting for Kida.

Tracks which template lines execute during rendering and outputs
standard coverage formats (lcov, Cobertura XML).

Leverages the existing ``_rc.line = N`` line tracking that the compiler
emits for error reporting — zero overhead when coverage is disabled,
one ContextVar check per line marker when enabled.

Usage::

    from kida import Environment
    from kida.coverage import CoverageCollector

    env = Environment()
    cov = CoverageCollector()

    with cov:
        template = env.get_template("page.html")
        template.render(title="Hello")

    print(cov.summary())
    cov.write_lcov("coverage.lcov")

"""

from __future__ import annotations

import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

from kida.render_context import RenderContext, _coverage_data

if TYPE_CHECKING:
    from contextvars import Token

# Guards _active_count and RenderContext.__setattr__ patching under
# concurrent start()/stop() calls (e.g. parallel test runners).
_patch_lock = threading.Lock()


@dataclass
class CoverageResult:
    """Coverage data for a single template."""

    template_name: str
    executed_lines: frozenset[int]
    total_lines: frozenset[int]

    @property
    def hit_count(self) -> int:
        return len(self.executed_lines & self.total_lines)

    @property
    def total_count(self) -> int:
        return len(self.total_lines)

    @property
    def missed_count(self) -> int:
        return self.total_count - self.hit_count

    @property
    def percentage(self) -> float:
        if self.total_count == 0:
            return 100.0
        return (self.hit_count / self.total_count) * 100.0


def _coverage_setattr(self: RenderContext, name: str, value: object) -> None:
    """Patched __setattr__ that records line hits for coverage."""
    object.__setattr__(self, name, value)
    if name == "line" and value:
        cov = _coverage_data.get(None)
        if cov is not None and self.template_name:
            cov.setdefault(self.template_name, set()).add(value)  # type: ignore[arg-type]


class CoverageCollector:
    """Collects template line coverage during rendering.

    Dynamically patches ``RenderContext.__setattr__`` while active so
    there is zero overhead when coverage is disabled (the normal case).
    """

    _active_count: int = 0  # ref-count for nested collectors

    def __init__(self) -> None:
        self._data: dict[str, set[int]] = {}
        self._token: Token[dict[str, set[int]] | None] | None = None

    def start(self) -> None:
        """Start collecting coverage data."""
        if self._token is not None:
            return
        self._token = _coverage_data.set(self._data)
        with _patch_lock:
            CoverageCollector._active_count += 1
            if CoverageCollector._active_count == 1:
                RenderContext.__setattr__ = _coverage_setattr  # type: ignore[assignment]

    def stop(self) -> None:
        """Stop collecting coverage data."""
        if self._token is not None:
            _coverage_data.reset(self._token)
            self._token = None
            with _patch_lock:
                CoverageCollector._active_count -= 1
                if CoverageCollector._active_count == 0 and "__setattr__" in RenderContext.__dict__:
                    del RenderContext.__setattr__

    def __enter__(self) -> CoverageCollector:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()

    def clear(self) -> None:
        """Clear all collected data."""
        self._data.clear()

    @property
    def data(self) -> dict[str, set[int]]:
        """Raw coverage data: {template_name: {executed_lines}}."""
        return self._data

    def get_results(
        self,
        source_map: dict[str, frozenset[int]] | None = None,
    ) -> list[CoverageResult]:
        """Get coverage results for all tracked templates.

        Args:
            source_map: Optional mapping of template_name to all trackable
                line numbers. If not provided, total_lines equals executed_lines
                (100% coverage for all touched templates — useful for hit tracking
                even without full line enumeration).

        Returns:
            List of CoverageResult per template, sorted by name.
        """
        results = []
        for name, lines in sorted(self._data.items()):
            executed = frozenset(lines)
            total = source_map.get(name, executed) if source_map else executed
            results.append(
                CoverageResult(
                    template_name=name,
                    executed_lines=executed,
                    total_lines=total,
                )
            )
        return results

    def summary(
        self,
        source_map: dict[str, frozenset[int]] | None = None,
    ) -> str:
        """Generate a text summary of coverage."""
        results = self.get_results(source_map)
        if not results:
            return "No templates rendered."

        lines = []
        lines.append(f"{'Template':<50} {'Lines':>6} {'Hit':>6} {'Cover':>7}")
        lines.append("-" * 71)

        total_hit = 0
        total_lines = 0
        for r in results:
            lines.append(
                f"{r.template_name:<50} {r.total_count:>6} {r.hit_count:>6} {r.percentage:>6.1f}%"
            )
            total_hit += r.hit_count
            total_lines += r.total_count

        lines.append("-" * 71)
        pct = (total_hit / total_lines * 100.0) if total_lines else 100.0
        lines.append(f"{'TOTAL':<50} {total_lines:>6} {total_hit:>6} {pct:>6.1f}%")
        return "\n".join(lines)

    def write_lcov(self, path: str) -> None:
        """Write coverage data in LCOV tracefile format."""
        with Path(path).open("w") as f:
            f.write(self.format_lcov())

    def format_lcov(self) -> str:
        """Format coverage data as LCOV tracefile string."""
        out = StringIO()
        for name, lines in sorted(self._data.items()):
            out.write(f"SF:{name}\n")
            for line in sorted(lines):
                out.write(f"DA:{line},1\n")
            out.write(f"LH:{len(lines)}\n")
            out.write(f"LF:{len(lines)}\n")
            out.write("end_of_record\n")
        return out.getvalue()

    def format_cobertura(self) -> str:
        """Format coverage data as Cobertura XML string."""
        root = ET.Element("coverage")
        root.set("version", "1.0")

        packages = ET.SubElement(root, "packages")
        pkg = ET.SubElement(packages, "package")
        pkg.set("name", "templates")

        classes = ET.SubElement(pkg, "classes")

        total_hit = 0
        total_lines = 0

        for name, lines in sorted(self._data.items()):
            cls = ET.SubElement(classes, "class")
            cls.set("name", name)
            cls.set("filename", name)
            cls.set("line-rate", "1.0")

            cls_lines = ET.SubElement(cls, "lines")
            for line in sorted(lines):
                line_el = ET.SubElement(cls_lines, "line")
                line_el.set("number", str(line))
                line_el.set("hits", "1")

            total_hit += len(lines)
            total_lines += len(lines)

        rate = str(total_hit / total_lines) if total_lines else "1.0"
        root.set("line-rate", rate)

        tree = ET.ElementTree(root)
        buf = StringIO()
        tree.write(buf, encoding="unicode", xml_declaration=True)
        return buf.getvalue()

    def write_cobertura(self, path: str) -> None:
        """Write coverage data in Cobertura XML format."""
        with Path(path).open("w") as f:
            f.write(self.format_cobertura())
