"""Tests for the dict_loader example."""


class TestDictLoaderApp:
    """Verify the dict_loader example renders correctly."""

    def test_output_contains_expected_content(self, example_app) -> None:
        assert "In-Memory Templates" in example_app.output
        assert "No filesystem required" in example_app.output
        assert "DictLoader Demo" in example_app.output

    def test_nav_items_rendered(self, example_app) -> None:
        assert 'href="/"' in example_app.output
        assert "Home" in example_app.output
        assert 'href="/about"' in example_app.output
        assert "About" in example_app.output
