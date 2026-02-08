"""Tests for the HTMX partials example."""


class TestHtmxPartialsApp:
    """Verify render_block() extracts individual blocks correctly."""

    def test_full_render_contains_all_blocks(self, example_app) -> None:
        assert "<nav>" in example_app.full_output
        assert "<main>" in example_app.full_output
        assert "<aside>" in example_app.full_output

    def test_nav_partial_contains_tabs(self, example_app) -> None:
        assert "Overview" in example_app.nav_output
        assert "Analytics" in example_app.nav_output
        assert "Settings" in example_app.nav_output

    def test_nav_partial_excludes_other_blocks(self, example_app) -> None:
        assert "<main>" not in example_app.nav_output
        assert "<aside>" not in example_app.nav_output

    def test_content_partial_has_items(self, example_app) -> None:
        assert "Revenue" in example_app.content_output
        assert "$1.2M" in example_app.content_output

    def test_content_partial_excludes_other_blocks(self, example_app) -> None:
        assert "<nav>" not in example_app.content_output
        assert "<aside>" not in example_app.content_output

    def test_sidebar_partial_has_stats(self, example_app) -> None:
        assert "Uptime" in example_app.sidebar_output
        assert "99.9%" in example_app.sidebar_output

    def test_sidebar_partial_excludes_other_blocks(self, example_app) -> None:
        assert "<nav>" not in example_app.sidebar_output
        assert "<main>" not in example_app.sidebar_output

    def test_active_tab_marked(self, example_app) -> None:
        assert 'class="active"' in example_app.nav_output

    def test_partials_share_context(self, example_app) -> None:
        """All partials receive the same context dict."""
        assert "Dashboard" in example_app.content_output
