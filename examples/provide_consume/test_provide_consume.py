"""Tests for the provide/consume example."""


class TestProvideConsumeApp:
    """Verify provide/consume state passing works end-to-end."""

    def test_table_renders_all_members(self, example_app) -> None:
        assert "Alice" in example_app.output
        assert "Bob" in example_app.output
        assert "Carol" in example_app.output

    def test_table_alignment_applied(self, example_app) -> None:
        assert 'class="align-left"' in example_app.output
        assert 'class="align-right"' in example_app.output

    def test_dark_theme_button(self, example_app) -> None:
        assert "btn-dark" in example_app.output

    def test_nested_theme_overrides(self, example_app) -> None:
        assert "btn-accent" in example_app.output

    def test_theme_restores_after_nesting(self, example_app) -> None:
        # Cancel button is outside the accent provider, should be dark
        output = example_app.output
        cancel_pos = output.index("Cancel")
        # Find the nearest btn class before "Cancel"
        btn_before_cancel = output.rfind("btn-", 0, cancel_pos)
        assert output[btn_before_cancel : btn_before_cancel + 8] == "btn-dark"
