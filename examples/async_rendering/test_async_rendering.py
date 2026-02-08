"""Tests for the async-rendering example."""


class TestAsyncRenderingApp:
    """Verify async for and await render correctly."""

    def test_await_resolved_in_heading(self, example_app) -> None:
        assert "Kida Features" in example_app.output

    def test_await_resolved_count(self, example_app) -> None:
        assert "Total: 3 features" in example_app.output

    def test_async_for_rendered_all_items(self, example_app) -> None:
        assert "#1: AST-native compilation" in example_app.output
        assert "#2: Free-threading support" in example_app.output
        assert "#3: Zero dependencies" in example_app.output

    def test_template_is_async(self, example_app) -> None:
        assert example_app.template.is_async is True
