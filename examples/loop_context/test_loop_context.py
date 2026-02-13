"""Tests for the loop_context example."""


class TestLoopContextApp:
    """Verify loop.first, loop.last, loop.index, loop.length work correctly."""

    def test_first_row_has_first_class(self, example_app) -> None:
        assert 'class="first' in example_app.output

    def test_last_row_has_last_class(self, example_app) -> None:
        assert 'last"' in example_app.output or "last " in example_app.output

    def test_loop_index_rendered(self, example_app) -> None:
        assert "1</td>" in example_app.output
        assert "4</td>" in example_app.output

    def test_loop_length_rendered(self, example_app) -> None:
        assert "4</td>" in example_app.output
        assert "/4" in example_app.output

    def test_all_items_present(self, example_app) -> None:
        assert "Alpha" in example_app.output
        assert "Beta" in example_app.output
        assert "Gamma" in example_app.output
        assert "Delta" in example_app.output
