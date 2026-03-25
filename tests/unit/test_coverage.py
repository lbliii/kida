"""Unit tests for kida.coverage — template coverage collection and reporting."""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

from kida.coverage import CoverageCollector, CoverageResult
from kida.render_context import RenderContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simulate_render(
    cov: CoverageCollector,
    template_name: str,
    lines: list[int],
) -> None:
    """Simulate template rendering by setting template_name and line numbers."""
    rc = RenderContext()
    rc.template_name = template_name
    for n in lines:
        rc.line = n


# ---------------------------------------------------------------------------
# CoverageResult
# ---------------------------------------------------------------------------


class TestCoverageResult:
    def test_hit_count(self) -> None:
        r = CoverageResult("t.html", frozenset({1, 2, 3}), frozenset({1, 2, 3, 4, 5}))
        assert r.hit_count == 3

    def test_total_count(self) -> None:
        r = CoverageResult("t.html", frozenset({1}), frozenset({1, 2, 3}))
        assert r.total_count == 3

    def test_missed_count(self) -> None:
        r = CoverageResult("t.html", frozenset({1}), frozenset({1, 2, 3}))
        assert r.missed_count == 2

    def test_percentage_full_coverage(self) -> None:
        r = CoverageResult("t.html", frozenset({1, 2}), frozenset({1, 2}))
        assert r.percentage == 100.0

    def test_percentage_partial_coverage(self) -> None:
        r = CoverageResult("t.html", frozenset({1}), frozenset({1, 2}))
        assert r.percentage == 50.0

    def test_percentage_no_total_lines(self) -> None:
        r = CoverageResult("t.html", frozenset(), frozenset())
        assert r.percentage == 100.0

    def test_executed_not_in_total_ignored(self) -> None:
        """Lines executed but not in total_lines don't count as hits."""
        r = CoverageResult("t.html", frozenset({99}), frozenset({1, 2}))
        assert r.hit_count == 0
        assert r.percentage == 0.0


# ---------------------------------------------------------------------------
# CoverageCollector — start / stop / context manager
# ---------------------------------------------------------------------------


class TestCoverageCollectorLifecycle:
    def test_start_and_stop(self) -> None:
        cov = CoverageCollector()
        cov.start()
        try:
            _simulate_render(cov, "a.html", [1, 2])
        finally:
            cov.stop()
        assert "a.html" in cov.data
        assert cov.data["a.html"] == {1, 2}

    def test_context_manager(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "b.html", [3, 4])
        assert cov.data["b.html"] == {3, 4}

    def test_double_start_is_idempotent(self) -> None:
        cov = CoverageCollector()
        cov.start()
        cov.start()  # should not raise or double-count
        try:
            _simulate_render(cov, "c.html", [1])
        finally:
            cov.stop()
        assert cov.data["c.html"] == {1}

    def test_stop_without_start_is_noop(self) -> None:
        cov = CoverageCollector()
        cov.stop()  # should not raise

    def test_setattr_removed_after_stop(self) -> None:
        """After all collectors stop, RenderContext.__setattr__ is restored."""
        cov = CoverageCollector()
        cov.start()
        cov.stop()
        # The patched __setattr__ should be removed from the class __dict__
        assert "__setattr__" not in RenderContext.__dict__

    def test_nested_collectors(self) -> None:
        """Nested collectors share the setattr patch; last one restores it."""
        cov1 = CoverageCollector()
        cov2 = CoverageCollector()
        cov1.start()
        cov2.start()
        _simulate_render(cov1, "a.html", [1])
        _simulate_render(cov2, "b.html", [2])
        cov2.stop()
        # __setattr__ should still be patched (cov1 is still active)
        assert "__setattr__" in RenderContext.__dict__
        cov1.stop()
        assert "__setattr__" not in RenderContext.__dict__

    def test_clear(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "x.html", [1, 2])
        cov.clear()
        assert cov.data == {}


# ---------------------------------------------------------------------------
# CoverageCollector — data collection
# ---------------------------------------------------------------------------


class TestCoverageCollectorData:
    def test_collects_multiple_templates(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "a.html", [1, 2])
            _simulate_render(cov, "b.html", [5, 10])
        assert set(cov.data.keys()) == {"a.html", "b.html"}

    def test_duplicate_lines_deduplicated(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "a.html", [1, 1, 1, 2])
        assert cov.data["a.html"] == {1, 2}

    def test_no_data_when_not_started(self) -> None:
        cov = CoverageCollector()
        # simulate without starting — should not record
        rc = RenderContext()
        rc.template_name = "a.html"
        rc.line = 5
        assert cov.data == {}


# ---------------------------------------------------------------------------
# CoverageCollector — get_results
# ---------------------------------------------------------------------------


class TestCoverageCollectorResults:
    def test_get_results_without_source_map(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "a.html", [1, 3])
        results = cov.get_results()
        assert len(results) == 1
        r = results[0]
        assert r.template_name == "a.html"
        assert r.executed_lines == frozenset({1, 3})
        # Without source_map, total == executed
        assert r.total_lines == r.executed_lines
        assert r.percentage == 100.0

    def test_get_results_with_source_map(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "a.html", [1, 3])
        source_map = {"a.html": frozenset({1, 2, 3, 4, 5})}
        results = cov.get_results(source_map)
        r = results[0]
        assert r.total_lines == frozenset({1, 2, 3, 4, 5})
        assert r.hit_count == 2  # lines 1 and 3
        assert r.percentage == 40.0

    def test_results_sorted_by_name(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "z.html", [1])
            _simulate_render(cov, "a.html", [1])
        results = cov.get_results()
        assert results[0].template_name == "a.html"
        assert results[1].template_name == "z.html"


# ---------------------------------------------------------------------------
# CoverageCollector — summary
# ---------------------------------------------------------------------------


class TestCoverageCollectorSummary:
    def test_summary_no_templates(self) -> None:
        cov = CoverageCollector()
        assert cov.summary() == "No templates rendered."

    def test_summary_has_header_and_total(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "page.html", [1, 2, 3])
        text = cov.summary()
        assert "Template" in text
        assert "TOTAL" in text
        assert "page.html" in text

    def test_summary_with_source_map(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "page.html", [1, 2])
        source_map = {"page.html": frozenset({1, 2, 3, 4})}
        text = cov.summary(source_map)
        assert "50.0%" in text


# ---------------------------------------------------------------------------
# CoverageCollector — LCOV format
# ---------------------------------------------------------------------------


class TestCoverageCollectorLcov:
    def test_format_lcov_empty(self) -> None:
        cov = CoverageCollector()
        assert cov.format_lcov() == ""

    def test_format_lcov_structure(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "t.html", [1, 5])
        lcov = cov.format_lcov()
        assert "SF:t.html" in lcov
        assert "DA:1,1" in lcov
        assert "DA:5,1" in lcov
        assert "LH:2" in lcov
        assert "LF:2" in lcov
        assert "end_of_record" in lcov

    def test_write_lcov(self, tmp_path: pathlib.Path) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "t.html", [1])
        path = str(tmp_path / "coverage.lcov")
        cov.write_lcov(path)
        with open(path) as f:
            content = f.read()
        assert "SF:t.html" in content


# ---------------------------------------------------------------------------
# CoverageCollector — Cobertura XML format
# ---------------------------------------------------------------------------


class TestCoverageCollectorCobertura:
    def test_format_cobertura_empty(self) -> None:
        cov = CoverageCollector()
        xml_str = cov.format_cobertura()
        root = ET.fromstring(xml_str)
        assert root.tag == "coverage"
        assert root.get("line-rate") == "1.0"

    def test_format_cobertura_structure(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "page.html", [2, 4, 6])
        xml_str = cov.format_cobertura()
        root = ET.fromstring(xml_str)
        assert root.get("version") == "1.0"

        classes = root.findall(".//class")
        assert len(classes) == 1
        cls = classes[0]
        assert cls.get("name") == "page.html"
        assert cls.get("filename") == "page.html"

        lines = cls.findall(".//line")
        assert len(lines) == 3
        line_numbers = sorted(int(el.get("number", "0")) for el in lines)
        assert line_numbers == [2, 4, 6]
        for el in lines:
            assert el.get("hits") == "1"

    def test_format_cobertura_multiple_templates(self) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "a.html", [1])
            _simulate_render(cov, "b.html", [2, 3])
        xml_str = cov.format_cobertura()
        root = ET.fromstring(xml_str)
        classes = root.findall(".//class")
        assert len(classes) == 2
        names = sorted(c.get("name", "") for c in classes)
        assert names == ["a.html", "b.html"]

    def test_write_cobertura(self, tmp_path: pathlib.Path) -> None:
        with CoverageCollector() as cov:
            _simulate_render(cov, "t.html", [1])
        path = str(tmp_path / "coverage.xml")
        cov.write_cobertura(path)
        with open(path) as f:
            content = f.read()
        root = ET.fromstring(content)
        assert root.tag == "coverage"
