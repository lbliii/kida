"""Tests for the custom_filters example."""


class TestCustomFiltersApp:
    """Verify the custom_filters example renders correctly."""

    def test_money_filter_formatting(self, example_app) -> None:
        assert "$1,234.56" in example_app.output
        assert "€1,234.56" in example_app.output

    def test_pluralize_filter(self, example_app) -> None:
        assert "3 items" in example_app.output

    def test_prime_test(self, example_app) -> None:
        assert "Item count is prime" in example_app.output

    def test_item_totals(self, example_app) -> None:
        assert "$39.98" in example_app.output
        assert "$5.00" in example_app.output
