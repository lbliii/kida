"""Tests for the list_comprehensions example."""


class TestListComprehensions:
    """Verify list comprehension examples render correctly."""

    def test_basic_transform(self, example_app) -> None:
        assert example_app.output_basic == "[2, 4, 6, 8, 10]"

    def test_with_filter(self, example_app) -> None:
        result = example_app.output_filter
        assert "Alice" in result
        assert "Bob" in result
        assert "Charlie" in result

    def test_with_condition(self, example_app) -> None:
        result = example_app.output_condition
        assert "Widget" in result
        assert "Doohickey" in result
        assert "Gadget" not in result

    def test_select_options(self, example_app) -> None:
        result = example_app.output_select
        assert '<option value="bold">Bold</option>' in result
        assert '<option value="italic">Italic</option>' in result

    def test_tuple_unpacking(self, example_app) -> None:
        result = example_app.output_unpacking
        assert "b" in result
        assert "c" in result
        assert "a" not in result
