"""Tests for the components example."""


class TestComponentsApp:
    """Verify def/call/slot component pattern works end-to-end."""

    def test_card_components_rendered(self, example_app) -> None:
        assert example_app.output.count("card-header") == 3
        assert "AST-native" in example_app.output
        assert "Free-threading" in example_app.output
        assert "Zero deps" in example_app.output

    def test_card_body_has_slot_content(self, example_app) -> None:
        assert "Compiles to Python AST directly" in example_app.output
        assert "Safe for concurrent execution" in example_app.output

    def test_alert_component_rendered(self, example_app) -> None:
        assert "alert-warning" in example_app.output
        assert "alpha release" in example_app.output

    def test_page_title(self, example_app) -> None:
        assert "<h1>Component Demo</h1>" in example_app.output
