"""Tests for the hello example."""


class TestHelloApp:
    """Verify the hello example renders correctly."""

    def test_output(self, example_app) -> None:
        assert example_app.output == "Hello, World!"

    def test_rerender_with_different_context(self, example_app) -> None:
        result = example_app.template.render(name="Kida")
        assert result == "Hello, Kida!"
