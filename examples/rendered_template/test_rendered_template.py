"""Tests for the rendered_template example."""


class TestRenderedTemplateApp:
    """Verify the rendered_template example works correctly."""

    def test_full_render_equals_template_render(self, example_app) -> None:
        expected = example_app.template.render(**example_app.context)
        assert example_app.full_output == expected

    def test_streamed_equals_full(self, example_app) -> None:
        assert example_app.streamed_output == example_app.full_output

    def test_str_equals_join_iteration(self, example_app) -> None:
        rt = example_app.rt
        assert str(rt) == "".join(rt)
