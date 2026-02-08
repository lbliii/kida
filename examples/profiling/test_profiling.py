"""Tests for the profiling example."""

from kida import get_accumulator


class TestProfilingApp:
    """Verify RenderAccumulator collects meaningful metrics."""

    def test_summary_has_total_ms(self, example_app) -> None:
        summary = example_app.summary
        assert "total_ms" in summary
        assert summary["total_ms"] >= 0

    def test_summary_has_blocks(self, example_app) -> None:
        summary = example_app.summary
        assert "blocks" in summary
        blocks = summary["blocks"]
        # Template has header, content, footer blocks
        assert len(blocks) > 0

    def test_block_entries_have_timing(self, example_app) -> None:
        for _name, data in example_app.summary["blocks"].items():
            assert "ms" in data
            assert "calls" in data
            assert data["ms"] >= 0
            assert data["calls"] >= 1

    def test_summary_has_filters(self, example_app) -> None:
        summary = example_app.summary
        assert "filters" in summary

    def test_normal_and_profiled_output_match(self, example_app) -> None:
        assert example_app.normal_output == example_app.profiled_output

    def test_no_accumulator_outside_profiled_render(self) -> None:
        """Verify zero overhead: no accumulator active outside profiled_render."""
        assert get_accumulator() is None

    def test_output_contains_template_content(self, example_app) -> None:
        assert "Quarterly Report" in example_app.output
