"""Tests for the design system example."""


class TestDesignSystemApp:
    """Verify component composition with def/slot/call."""

    def test_button_renders_with_variant(self, example_app) -> None:
        assert "btn-danger" in example_app.output
        assert "btn-secondary" in example_app.output

    def test_button_default_variant(self, example_app) -> None:
        assert "btn-primary" in example_app.output

    def test_button_size_parameter(self, example_app) -> None:
        assert "btn-sm" in example_app.output
        assert "btn-md" in example_app.output

    def test_disabled_button(self, example_app) -> None:
        assert "disabled" in example_app.output

    def test_button_slot_content(self, example_app) -> None:
        assert "Delete Account" in example_app.output
        assert "Edit Profile" in example_app.output
        assert "Save" in example_app.output
        assert "Cancel" in example_app.output

    def test_card_renders_with_title(self, example_app) -> None:
        assert "Alice" in example_app.output
        assert "Actions" in example_app.output

    def test_card_slot_content_projected(self, example_app) -> None:
        assert "alice@example.com" in example_app.output

    def test_card_footer(self, example_app) -> None:
        assert "Member since 2024" in example_app.output
        assert "card-footer" in example_app.output

    def test_alert_with_level(self, example_app) -> None:
        assert "alert-success" in example_app.output

    def test_alert_slot_content(self, example_app) -> None:
        assert "Welcome back, Alice!" in example_app.output

    def test_nested_composition(self, example_app) -> None:
        """Buttons should render inside cards (nested def/call)."""
        output = example_app.output
        # Card body should contain buttons
        assert "card-body" in output
        assert "btn" in output

    def test_page_title(self, example_app) -> None:
        assert "User Dashboard" in example_app.output
