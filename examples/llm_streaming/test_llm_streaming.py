"""Tests for the LLM streaming example."""


class TestLlmStreamingApp:
    """Verify async LLM token stream renders progressively."""

    def test_all_tokens_in_output(self, example_app) -> None:
        assert "Kida is a modern template engine built for Python 3.14t." in example_app.output

    def test_prompt_in_output(self, example_app) -> None:
        assert "What is Kida?" in example_app.output

    def test_yields_multiple_chunks(self, example_app) -> None:
        assert len(example_app.chunks) > 1

    def test_chunks_are_strings(self, example_app) -> None:
        for chunk in example_app.chunks:
            assert isinstance(chunk, str)

    def test_template_is_async(self, example_app) -> None:
        assert example_app.template.is_async is True

    def test_chat_structure(self, example_app) -> None:
        assert '<div class="chat">' in example_app.output
        assert '<div class="message assistant">' in example_app.output
        assert '<div class="message user">' in example_app.output
