"""Tests for the bytecode cache example."""


class TestBytecodeCacheApp:
    """Verify bytecode caching produces identical output."""

    def test_output_is_valid_html(self, example_app) -> None:
        assert "<html>" in example_app.output
        assert "Cached Page" in example_app.output

    def test_output_contains_all_items(self, example_app) -> None:
        assert "alpha" in example_app.output
        assert "beta" in example_app.output
        assert "gamma" in example_app.output

    def test_cache_has_files_after_first_load(self, example_app) -> None:
        stats = example_app.stats_after_first
        assert stats["file_count"] > 0
        assert stats["total_bytes"] > 0

    def test_second_load_produces_same_output(self, example_app) -> None:
        assert example_app.output_first == example_app.output_second

    def test_cache_stats_stable_after_second_load(self, example_app) -> None:
        """Second load should use existing cache, not add new files."""
        assert (
            example_app.stats_after_second["file_count"]
            == example_app.stats_after_first["file_count"]
        )
