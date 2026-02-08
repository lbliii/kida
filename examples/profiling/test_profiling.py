"""Tests for the profiling example."""

from kida import get_accumulator


class TestProfilingApp:
    """Verify RenderAccumulator collects meaningful metrics."""

    def test_summary_has_total_ms(self, example_app) -> None:
        summary = example_app.summary
        assert "total_ms" in summary
        assert summary["total_ms"] >= 0

    def test_summary_has_expected_keys(self, example_app) -> None:
        summary = example_app.summary
        assert "blocks" in summary
        assert "macros" in summary
        assert "includes" in summary
        assert "filters" in summary

    def test_summary_tracks_includes(self, example_app) -> None:
        includes = example_app.summary["includes"]
        # Template includes header.html and footer.html
        assert "header.html" in includes
        assert "footer.html" in includes

    def test_header_included_once(self, example_app) -> None:
        includes = example_app.summary["includes"]
        assert includes["header.html"] == 1

    def test_normal_and_profiled_output_match(self, example_app) -> None:
        assert example_app.normal_output == example_app.profiled_output

    def test_no_accumulator_outside_profiled_render(self) -> None:
        """Verify zero overhead: no accumulator active outside profiled_render."""
        assert get_accumulator() is None

    def test_output_contains_template_content(self, example_app) -> None:
        assert "Quarterly Report" in example_app.output
