"""Tests for markdown escape utilities."""

from __future__ import annotations

from kida.utils.markdown_escape import Marked, markdown_escape


class TestMarkdownEscape:
    """Test markdown_escape() function."""

    def test_plain_text_unchanged(self):
        assert markdown_escape("hello world") == "hello world"

    def test_escapes_asterisks(self):
        assert markdown_escape("**bold**") == "\\*\\*bold\\*\\*"

    def test_escapes_underscores(self):
        assert markdown_escape("_italic_") == "\\_italic\\_"

    def test_escapes_brackets(self):
        assert markdown_escape("[link](url)") == "\\[link\\]\\(url\\)"

    def test_escapes_hash(self):
        assert markdown_escape("# heading") == "\\# heading"

    def test_escapes_backtick(self):
        assert markdown_escape("`code`") == "\\`code\\`"

    def test_escapes_pipe(self):
        assert markdown_escape("a | b") == "a \\| b"

    def test_escapes_tilde(self):
        assert markdown_escape("~~strike~~") == "\\~\\~strike\\~\\~"

    def test_non_string_converted(self):
        result = markdown_escape(42)
        assert result == "42"

    def test_markdown_protocol(self):
        """Objects with __markdown__ bypass escaping."""

        class SafeObj:
            def __markdown__(self):
                return "**already safe**"

        result = markdown_escape(SafeObj())
        assert result == "**already safe**"


class TestMarked:
    """Test Marked safe-string class."""

    def test_create_from_string(self):
        m = Marked("**bold**")
        assert str(m) == "**bold**"

    def test_markdown_protocol(self):
        m = Marked("safe")
        assert m.__markdown__() is m

    def test_bypasses_escaping(self):
        result = markdown_escape(Marked("**bold**"))
        assert result == "**bold**"

    def test_repr(self):
        m = Marked("hello")
        assert repr(m) == "Marked('hello')"

    def test_add_escapes_non_marked(self):
        m = Marked("safe ") + "**unsafe**"
        assert "\\*\\*unsafe\\*\\*" in str(m)
        assert isinstance(m, Marked)

    def test_add_preserves_marked(self):
        m = Marked("a") + Marked("**b**")
        assert str(m) == "a**b**"

    def test_radd_escapes(self):
        m = "**unsafe** " + Marked("safe")
        assert "\\*\\*unsafe\\*\\*" in str(m)
        assert isinstance(m, Marked)

    def test_mul(self):
        m = Marked("-") * 3
        assert str(m) == "---"
        assert isinstance(m, Marked)

    def test_mod_escapes(self):
        m = Marked("Hello %s") % "**world**"
        assert "\\*\\*world\\*\\*" in str(m)

    def test_mod_preserves_marked(self):
        m = Marked("Hello %s") % Marked("**world**")
        assert str(m) == "Hello **world**"

    def test_format_escapes(self):
        m = Marked("Hello {}").format("**world**")
        assert "\\*\\*world\\*\\*" in str(m)

    def test_join_escapes(self):
        m = Marked(", ").join(["**a**", Marked("**b**")])
        assert "\\*\\*a\\*\\*" in str(m)
        assert "**b**" in str(m)

    def test_new_with_markdown_protocol(self):
        """Marked constructor calls __markdown__ if available."""

        class SafeObj:
            def __markdown__(self):
                return "safe content"

        m = Marked(SafeObj())
        assert str(m) == "safe content"
