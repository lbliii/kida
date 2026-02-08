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

    def test_summary_tracks_blocks(self, example_app) -> None:
        """Blocks are auto-instrumented with timing by the compiler."""
        blocks = example_app.summary["blocks"]
        assert "header" in blocks
        assert "content" in blocks
        assert "footer" in blocks
        assert blocks["header"]["calls"] == 1
        assert blocks["header"]["ms"] >= 0

    def test_summary_tracks_filters(self, example_app) -> None:
        """Filter calls are auto-recorded by the compiler."""
        filters = example_app.summary["filters"]
        # title | upper used in template
        assert "upper" in filters
        assert "title" in filters
        assert "truncate" in filters
        assert "length" in filters

    def test_summary_tracks_macros(self, example_app) -> None:
        """Macro ({% def %}) calls are auto-recorded by the compiler."""
        macros = example_app.summary["macros"]
        assert "section_card" in macros
        # Called once per section (2 sections in context)
        assert macros["section_card"] == 2

    def test_normal_and_profiled_output_match(self, example_app) -> None:
        assert example_app.normal_output == example_app.profiled_output

    def test_no_accumulator_outside_profiled_render(self) -> None:
        """Verify zero overhead: no accumulator active outside profiled_render."""
        assert get_accumulator() is None

    def test_output_contains_template_content(self, example_app) -> None:
        assert "Quarterly Report" in example_app.output

    def test_dict_items_key_resolved_correctly(self, example_app) -> None:
        """section.items resolves to the dict key, not dict.items() method.

        This uses the dict-safe attribute resolution (subscript-first for dicts).
        Previously, 'items' had to be renamed to 'entries' because section.items
        resolved to dict.items() method instead of section["items"].
        """
        # Items are uppercased by the | upper filter in the template
        assert "SUBSCRIPTIONS" in example_app.output
        assert "PLATFORM" in example_app.output
        assert "SERVICES" in example_app.output
