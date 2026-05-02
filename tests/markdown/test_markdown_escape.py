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

    def test_escapes_brackets_only(self):
        # Square brackets are inline-special; parentheses are not — once
        # the link's `[` is escaped the trailing `(...)` cannot form a link.
        assert markdown_escape("[link](url)") == "\\[link\\](url)"

    def test_escapes_backtick(self):
        assert markdown_escape("`code`") == "\\`code\\`"

    def test_escapes_angle_bracket(self):
        # `<` is escaped to prevent autolinks/raw HTML smuggling.
        assert markdown_escape("<script>") == "\\<script>"

    def test_escapes_backslash(self):
        assert markdown_escape("foo\\bar") == "foo\\\\bar"

    def test_pipe_not_escaped(self):
        # Pipe is only special in tables; the table filter handles its own.
        assert markdown_escape("a | b") == "a | b"

    def test_tilde_not_escaped(self):
        # Tildes are rare and noisy to escape; left to the markdown source.
        assert markdown_escape("~~strike~~") == "~~strike~~"

    def test_inline_hyphen_unchanged(self):
        # Dates, identifiers, prose — hyphens mid-line render fine raw.
        assert markdown_escape("2026-04-24") == "2026-04-24"
        assert markdown_escape("K-PAR-001 end-tag") == "K-PAR-001 end-tag"

    def test_inline_hash_unchanged(self):
        assert markdown_escape("issue #123") == "issue #123"

    def test_inline_paren_unchanged(self):
        assert markdown_escape("note (see ref)") == "note (see ref)"

    def test_block_lead_hash_escaped(self):
        assert markdown_escape("# heading") == "\\# heading"
        assert markdown_escape("### h3") == "\\### h3"

    def test_block_lead_hash_after_newline(self):
        assert markdown_escape("intro\n## Summary\nbody") == "intro\n\\## Summary\nbody"

    def test_block_lead_blockquote_escaped(self):
        assert markdown_escape("> quoted") == "\\> quoted"

    def test_block_lead_unordered_list_escaped(self):
        assert markdown_escape("- item") == "\\- item"
        assert markdown_escape("+ item") == "\\+ item"

    def test_block_lead_ordered_list_escaped(self):
        assert markdown_escape("1. first") == "\\1. first"
        assert markdown_escape("42) forty-two") == "\\42) forty-two"

    def test_block_lead_with_indent_escaped(self):
        assert markdown_escape("  - item") == "  \\- item"

    def test_block_lead_requires_marker_followed_by_space(self):
        # `#word` is not a heading; should pass through unchanged.
        assert markdown_escape("#hashtag") == "#hashtag"
        # Hyphen with no trailing space is mid-word, not a list marker.
        assert markdown_escape("-1") == "-1"

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
