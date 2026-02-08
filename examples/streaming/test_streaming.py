"""Tests for the streaming example."""


class TestStreamingApp:
    """Verify render_stream() yields multiple chunks with correct content."""

    def test_yields_multiple_chunks(self, example_app) -> None:
        assert len(example_app.chunks) > 1

    def test_joined_output_has_all_sections(self, example_app) -> None:
        assert "Revenue" in example_app.output
        assert "Users" in example_app.output
        assert "Churn" in example_app.output

    def test_output_has_title(self, example_app) -> None:
        assert "Quarterly Report" in example_app.output

    def test_chunks_are_strings(self, example_app) -> None:
        for chunk in example_app.chunks:
            assert isinstance(chunk, str)
