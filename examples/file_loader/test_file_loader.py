"""Tests for the file-loader example."""


class TestFileLoaderApp:
    """Verify file-based template loading with inheritance and includes."""

    def test_home_has_title(self, example_app) -> None:
        assert "<title>Welcome | My Site</title>" in example_app.home_output

    def test_home_has_content(self, example_app) -> None:
        assert "<h1>Welcome</h1>" in example_app.home_output
        assert "kida-powered site" in example_app.home_output

    def test_about_has_title(self, example_app) -> None:
        assert "<title>About Us | My Site</title>" in example_app.about_output

    def test_about_has_content(self, example_app) -> None:
        assert "<h1>About Us</h1>" in example_app.about_output
        assert "free-threaded Python" in example_app.about_output

    def test_nav_included_in_both(self, example_app) -> None:
        for output in [example_app.home_output, example_app.about_output]:
            assert "<nav>" in output
            assert 'href="/"' in output
            assert 'href="/about"' in output

    def test_footer_inherited(self, example_app) -> None:
        for output in [example_app.home_output, example_app.about_output]:
            assert "Powered by kida" in output
