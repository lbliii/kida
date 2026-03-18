"""Tests for the regions example."""


class TestRegionsApp:
    """Verify regions work as blocks and callables with simple and complex defaults."""

    def test_full_render_contains_sidebar(self, example_app) -> None:
        assert "API" in example_app.full_output
        assert "Products" in example_app.full_output

    def test_full_render_contains_stats_with_complex_default(self, example_app) -> None:
        """count=items | length resolves to 3."""
        assert "3 items" in example_app.full_output

    def test_full_render_contains_header_with_optional_default(self, example_app) -> None:
        """title=page?.title ?? Default when page exists."""
        assert "Products" in example_app.full_output

    def test_render_block_sidebar(self, example_app) -> None:
        assert "API" in example_app.sidebar_output
        assert "Products" in example_app.sidebar_output

    def test_render_block_stats(self, example_app) -> None:
        """Stats region uses count=items | length default."""
        assert "3 items" in example_app.stats_output

    def test_render_block_header(self, example_app) -> None:
        assert "Products" in example_app.header_output

    def test_regions_listed_in_metadata(self, example_app) -> None:
        regions = example_app.regions
        assert "sidebar" in regions
        assert "stats" in regions
        assert "header" in regions

    def test_depends_on_captures_complex_defaults(self, example_app) -> None:
        meta = example_app.meta
        sidebar = meta.get_block("sidebar")
        stats = meta.get_block("stats")
        assert sidebar is not None
        assert stats is not None
        assert "page" in sidebar.depends_on or "page.title" in sidebar.depends_on
        assert "items" in stats.depends_on
