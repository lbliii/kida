"""Tests for the caching example."""


class TestCachingApp:
    """Verify fragment caching avoids recomputation."""

    def test_first_render_has_content(self, example_app) -> None:
        assert "Dashboard" in example_app.first_output
        assert "computed 1 time" in example_app.first_output

    def test_cache_hit_on_second_render(self, example_app) -> None:
        # The expensive_computation should only have been called once total
        assert example_app.count_after_first == 1
        assert example_app.count_after_second == 1

    def test_non_cached_content_updates(self, example_app) -> None:
        # The stats block is NOT cached, so it should reflect the new data
        assert "9999" in example_app.second_output
        assert "$99K" in example_app.second_output

    def test_cached_block_same_in_both(self, example_app) -> None:
        # The cached block output should be identical in both renders
        assert "computed 1 time" in example_app.first_output
        assert "computed 1 time" in example_app.second_output
